import os
import logging
import threading

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy,
)
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QCloseEvent
from PySide6.QtCore import Qt, QSize, Signal, QObject, QThread

from app.constants import COLORS as C, APP_NAME, PLATFORMS
from app.db.database import Database
from app.ui.sidebar import Sidebar
from app.ui.login_dialog import LoginDialog, CookieConsentDialog
from app.ui.components.animated_stack import AnimatedStackedWidget
from app.browser.manager import BrowserManager


class _QtLogBridge(QObject):
    """Carries log records from any thread to the Qt main thread via signal."""

    record = Signal(str, str)


class _QtLogHandler(logging.Handler):
    """Logging handler that re-emits each record through a Qt signal.

    Used so the per-step ``logger.info`` calls inside the auth / browser
    code show up live in the sidebar's Activity Log instead of vanishing
    into the file log only.
    """

    def __init__(self, bridge: "_QtLogBridge"):
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level_map = {
                "DEBUG": "info",
                "INFO": "info",
                "WARNING": "warning",
                "ERROR": "error",
                "CRITICAL": "error",
            }
            level = level_map.get(record.levelname, "info")
            self._bridge.record.emit(msg, level)
        except Exception:
            pass


class AvatarButton(QPushButton):
    """Circular profile picture button in the header."""

    def __init__(self, size: int = 40, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton {{ background-color: {C.bg_card}; border: 2px solid {C.border_default};"
            f"border-radius: {size // 2}px; }}"
            f"QPushButton:hover {{ border-color: {C.border_strong}; }}"
        )
        self._pixmap = None

    def set_image(self, path: str):
        if path and os.path.isfile(path):
            pm = QPixmap(path).scaled(
                self._size, self._size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._pixmap = self._make_circular(pm)
            self.setIcon(self._pixmap)
            self.setIconSize(QSize(self._size - 4, self._size - 4))
        else:
            self.setIcon(QPixmap())
            self.setText("")

    def _make_circular(self, pixmap: QPixmap) -> QPixmap:
        size = min(pixmap.width(), pixmap.height())
        result = QPixmap(size, size)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        x = (pixmap.width() - size) // 2
        y = (pixmap.height() - size) // 2
        painter.drawPixmap(0, 0, pixmap, x, y, size, size)
        painter.end()
        return result


class CookieConsentBridge(QObject):
    """Thread-safe bridge: worker thread requests cookie consent, main thread shows dialog."""

    request = Signal(str)
    response = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event = threading.Event()
        self._choice = "all"
        self.request.connect(self._on_request, Qt.ConnectionType.QueuedConnection)

    def ask(self, platform_name: str) -> str:
        """Called from the BrowserThread (via execute). Blocks until user answers."""
        self._event.clear()
        self._choice = "all"
        self.request.emit(platform_name)
        self._event.wait(timeout=60)
        return self._choice

    def _on_request(self, platform_name: str):
        """Runs on main thread -- shows the dialog."""
        from PySide6.QtWidgets import QApplication
        parent = QApplication.activeWindow()
        dialog = CookieConsentDialog(platform_name, parent=parent)
        dialog.exec()
        self._choice = dialog.choice
        self._event.set()


class LoginWorker(QObject):
    """Runs platform login in a background thread using BrowserManager."""

    finished = Signal(str, bool, str, str)

    def __init__(self, browser_manager: BrowserManager, platform_id: str,
                 email: str, password: str, cookie_bridge: CookieConsentBridge):
        super().__init__()
        self._bm = browser_manager
        self._platform_id = platform_id
        self._email = email
        self._password = password
        self._cookie_bridge = cookie_bridge

    def run(self):
        from app.auth.session_manager import SessionManager

        platform_name = PLATFORMS.get(self._platform_id, {}).get("display_name", self._platform_id)

        def cookie_cb() -> str:
            return self._cookie_bridge.ask(platform_name)

        manager = SessionManager(self._bm)
        success, msg = manager.login_platform(
            self._platform_id, self._email, self._password,
            cookie_callback=cookie_cb,
        )
        self.finished.emit(self._platform_id, success, msg, self._email)


class MainWindow(QMainWindow):

    def __init__(self, db: Database, data_dir: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.data_dir = data_dir
        self._login_threads: dict[str, QThread] = {}
        self._login_workers: dict[str, LoginWorker] = {}
        self._login_dialogs: dict[str, LoginDialog] = {}

        self._browser_manager = BrowserManager.get_instance(data_dir)
        self._browser_manager.start()

        self._cookie_bridge = CookieConsentBridge(self)

        self._log_bridge = _QtLogBridge(self)
        self._log_handler = _QtLogHandler(self._log_bridge)
        self._log_handler.setLevel(logging.INFO)
        self._log_handler.setFormatter(logging.Formatter("%(message)s"))
        for logger_name in ("app.auth.tiktok", "app.browser.manager"):
            logging.getLogger(logger_name).addHandler(self._log_handler)

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 600)
        self.resize(1280, 800)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar(db=db)
        self.sidebar.platform_connect.connect(self._on_platform_connect)
        root_layout.addWidget(self.sidebar)

        right_side = QVBoxLayout()
        right_side.setContentsMargins(0, 0, 0, 0)
        right_side.setSpacing(0)

        self._header = self._build_header()
        right_side.addWidget(self._header)

        self._stack = AnimatedStackedWidget()
        self._stack.setStyleSheet(f"background-color: {C.bg_app};")
        right_side.addWidget(self._stack, 1)

        root_layout.addLayout(right_side, 1)

        self._pages: dict[str, QWidget] = {}
        self._page_order: list[str] = []
        self._init_pages()

        # Connect the log bridge AFTER the sidebar / log panel exist so the
        # very first ``logger.info`` calls already land in the UI.
        self._log_bridge.record.connect(
            self.sidebar.log_panel.log, Qt.ConnectionType.QueuedConnection,
        )

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setProperty("role", "header")
        header.setFixedHeight(56)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel(APP_NAME)
        title.setProperty("role", "title")
        title.setStyleSheet(
            f"color: {C.text_primary}; font-size: 18px; font-weight: 600; background: transparent;"
        )

        self._avatar_btn = AvatarButton(40)
        self._avatar_btn.clicked.connect(self._show_profile_picture_page)

        pp = self.db.get_profile_picture()
        if pp and pp.file_path:
            self._avatar_btn.set_image(pp.file_path)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self._avatar_btn)

        return header

    def _init_pages(self):
        from app.ui.content_grid import ContentGridPage
        from app.ui.content_detail import ContentDetailPage
        from app.ui.profile_picture import ProfilePicturePage

        self._grid_page = ContentGridPage(db=self.db, data_dir=self.data_dir)
        self._grid_page.content_clicked.connect(self._show_content_detail)
        self._grid_page.log_message.connect(self._log)
        self._add_page("grid", self._grid_page)

        self._detail_page = ContentDetailPage(db=self.db, data_dir=self.data_dir)
        self._detail_page.back_clicked.connect(lambda: self._navigate("grid"))
        self._detail_page.log_message.connect(self._log)
        self._add_page("detail", self._detail_page)

        self._profile_page = ProfilePicturePage(db=self.db, data_dir=self.data_dir)
        self._profile_page.back_clicked.connect(lambda: self._navigate("grid"))
        self._profile_page.avatar_changed.connect(self._on_avatar_changed)
        self._profile_page.log_message.connect(self._log)
        self._profile_page.login_requested.connect(self._on_platform_connect)
        self._add_page("profile", self._profile_page)

        self._stack.setCurrentWidget(self._grid_page)

    def _add_page(self, name: str, widget: QWidget):
        self._pages[name] = widget
        self._page_order.append(name)
        self._stack.addWidget(widget)

    def _navigate(self, name: str):
        page = self._pages.get(name)
        if not page:
            return
        if name == "grid":
            self._grid_page.refresh()

        target_idx = self._stack.indexOf(page)
        current_idx = self._stack.currentIndex()

        if name == "grid":
            self._stack.slide_back(target_idx)
        elif current_idx < target_idx:
            self._stack.slide_forward(target_idx)
        else:
            self._stack.slide_back(target_idx)

    def _show_content_detail(self, content_id: int):
        self._detail_page.load_content(content_id)
        self._navigate("detail")

    def _show_profile_picture_page(self):
        self._profile_page.refresh()
        self._navigate("profile")

    def _on_avatar_changed(self, path: str):
        self._avatar_btn.set_image(path)

    # --- Platform connect flow ---

    def _on_platform_connect(self, platform_id: str):
        # User explicitly clicked Connect / Reconnect / Retry: always show the
        # login dialog. We don't pre-mutate the badge here -- the row already
        # reflects the current DB state (Connected / Not connected / Failed)
        # and we only want to swap to "Connecting..." once the dialog is
        # actually submitted and the worker starts running.
        if platform_id in self._login_threads and self._login_threads[platform_id].isRunning():
            self.sidebar.log_panel.log(
                f"{platform_id}: A login attempt is already in progress.", "warning",
            )
            return
        self._show_login_dialog(platform_id)

    def _show_login_dialog(self, platform_id: str):
        from app.auth.token_store import get_credentials

        pdata = PLATFORMS.get(platform_id, {})
        display_name = pdata.get("display_name", platform_id)

        saved_email, saved_password = "", ""
        creds = get_credentials(platform_id)
        if creds and creds[0]:
            saved_email = creds[0]
            saved_password = creds[1] or ""

        dialog = LoginDialog(
            platform_id, display_name,
            saved_email=saved_email,
            saved_password=saved_password,
            parent=self,
        )
        dialog.login_submitted.connect(self._do_login)
        self._login_dialogs[platform_id] = dialog
        dialog.exec()
        self._login_dialogs.pop(platform_id, None)

    def _do_login(self, platform_id: str, email: str, password: str, remember: bool):
        from app.auth.token_store import save_credentials, delete_credentials

        if remember:
            save_credentials(platform_id, email, password)
        else:
            delete_credentials(platform_id)

        self.sidebar.get_item(platform_id).set_reconnecting()
        self.sidebar.log_panel.log(f"Connecting to {platform_id}...", "info")

        thread = QThread()
        worker = LoginWorker(
            self._browser_manager, platform_id, email, password,
            self._cookie_bridge,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_login_finished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(lambda pid=platform_id: self._cleanup_login(pid))

        self._login_threads[platform_id] = thread
        self._login_workers[platform_id] = worker
        thread.start()

    def _cleanup_login(self, platform_id: str):
        self._login_threads.pop(platform_id, None)
        self._login_workers.pop(platform_id, None)

    def _on_login_finished(self, platform_id: str, success: bool, msg: str, email: str):
        dialog = self._login_dialogs.get(platform_id)
        if success:
            self.db.set_platform_connected(platform_id, email)
            self.sidebar.refresh_platforms()
            self._profile_page.refresh()
            self.sidebar.log_panel.log(f"{platform_id}: Connected as {email}", "success")
            if msg:
                self.sidebar.log_panel.log(f"{platform_id}: {msg}", "info")
            if dialog:
                dialog.show_success()
        else:
            self.sidebar.get_item(platform_id).set_failed(msg)
            self.sidebar.log_panel.log(f"{platform_id}: {msg}", "error")
            if dialog:
                dialog.show_error(msg)

    def _log(self, message: str, level: str = "info"):
        self.sidebar.log_panel.log(message, level)

    def refresh_avatar(self):
        pp = self.db.get_profile_picture()
        if pp and pp.file_path:
            self._avatar_btn.set_image(pp.file_path)

    def closeEvent(self, event: QCloseEvent):
        self._browser_manager.shutdown()
        super().closeEvent(event)
