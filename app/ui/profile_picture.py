import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDialog,
    QCheckBox, QFrame, QScrollArea, QSizePolicy, QGridLayout,
)
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QMouseEvent
from PySide6.QtCore import Qt, Signal, QThread, QObject

from app.constants import COLORS as C, PLATFORMS
from app.db.database import Database
from app.ui.components.button import PrimaryButton, GhostButton
from app.ui.components.badge import Badge
from app.ui.components.log_panel import LogPanel
from app.ui.components.input_field import TextArea

CAPTION_SUPPORTED_PLATFORMS = {"facebook"}


class ClickableLabel(QLabel):
    """QLabel that emits clicked on mouse press."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PhotoPickerDialog(QDialog):
    """Dialog that lets the user pick a photo from already-imported app content."""

    photo_selected = Signal(str)

    THUMB_SIZE = 100

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Photo")
        self.setMinimumSize(420, 340)
        self.resize(500, 420)
        self.setStyleSheet(
            f"QDialog {{ background-color: {C.bg_popup}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Choose a photo from your library")
        title.setStyleSheet(
            f"color: {C.text_primary}; font-size: 14px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(8)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._grid_widget)
        layout.addWidget(scroll, 1)

        photos = db.get_images_only()
        if not photos:
            empty = QLabel("No photos in app yet.\nImport photos first via drag and drop.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {C.text_disabled}; font-size: 13px; padding: 30px; background: transparent;"
            )
            self._grid_layout.addWidget(empty, 0, 0)
            return

        cols = max(1, (self.width() - 48) // (self.THUMB_SIZE + 8))
        for i, content in enumerate(photos):
            thumb = ClickableLabel()
            thumb.setFixedSize(self.THUMB_SIZE, self.THUMB_SIZE)
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet(
                f"QLabel {{ background-color: {C.bg_card}; border: 2px solid {C.border_soft};"
                f"border-radius: 8px; }}"
                f"QLabel:hover {{ border-color: {C.border_strong}; background-color: {C.bg_card_hover}; }}"
            )
            thumb.setToolTip(content.file_name)

            pm_path = content.thumbnail_path if content.thumbnail_path and os.path.isfile(content.thumbnail_path) else content.file_path
            if os.path.isfile(pm_path):
                pm = QPixmap(pm_path).scaled(
                    self.THUMB_SIZE - 4, self.THUMB_SIZE - 4,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                thumb.setPixmap(pm)

            file_path = content.file_path
            thumb.clicked.connect(lambda fp=file_path: self._select(fp))
            self._grid_layout.addWidget(thumb, i // cols, i % cols)

    def _select(self, file_path: str):
        self.photo_selected.emit(file_path)
        self.accept()


class ProfilePicWorker(QObject):
    """Runs profile picture changes on all platforms in a background thread."""

    progress = Signal(str, str, str)
    finished = Signal()

    def __init__(self, data_dir: str, image_path: str, platform_ids: list[str],
                 caption: str = ""):
        super().__init__()
        self.data_dir = data_dir
        self.image_path = image_path
        self.platform_ids = platform_ids
        self.caption = caption

    def run(self):
        from app.browser.manager import BrowserManager
        bm = BrowserManager.get_instance()

        for pid in self.platform_ids:
            self.progress.emit(pid, "Changing profile picture...", "info")
            try:
                from app.browser.base import get_browser_action
                action = get_browser_action(pid)

                def _do_change(bt, _pid=pid):
                    page = bt.get_page(_pid)
                    action.change_profile_picture(page, self.image_path, caption=self.caption)

                bm.execute(_do_change, timeout=120)
                self.progress.emit(pid, "Profile picture updated", "success")
            except Exception as e:
                self.progress.emit(pid, f"Failed: {e}", "error")
        self.finished.emit()


class ProfilePicturePage(QWidget):
    """Profile picture management page with per-platform checkboxes."""

    back_clicked = Signal()
    avatar_changed = Signal(str)
    log_message = Signal(str, str)
    login_requested = Signal(str)

    def __init__(self, db: Database, data_dir: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.data_dir = data_dir
        self._image_path = None
        self._thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        top = QHBoxLayout()
        back_btn = GhostButton("<  Back")
        back_btn.clicked.connect(self.back_clicked.emit)
        top.addWidget(back_btn)

        title = QLabel("Profile Picture Settings")
        title.setProperty("role", "title")
        title.setStyleSheet(f"color: {C.text_primary}; background: transparent;")
        title.setWordWrap(True)
        top.addWidget(title, 1)
        top.addStretch()
        layout.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        center = QHBoxLayout(scroll_content)
        center.setSpacing(32)

        preview_col = QVBoxLayout()
        preview_col.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._preview = ClickableLabel()
        self._preview.setMinimumSize(120, 120)
        self._preview.setMaximumSize(200, 200)
        self._preview.setFixedSize(200, 200)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview.setStyleSheet(
            f"QLabel {{ background-color: {C.bg_input}; border: 2px solid {C.border_default};"
            f"border-radius: 100px; color: {C.text_muted}; font-size: 12px; }}"
            f"QLabel:hover {{ border-color: {C.border_strong}; background-color: {C.bg_card_hover}; }}"
        )
        self._preview.setText("Click to\nadd image")
        self._preview.clicked.connect(self._pick_image)

        change_btn = PrimaryButton("Change Image")
        change_btn.clicked.connect(self._pick_image)

        preview_col.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignHCenter)
        preview_col.addWidget(change_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        preview_widget = QWidget()
        preview_widget.setLayout(preview_col)
        preview_widget.setMinimumWidth(180)
        preview_widget.setMaximumWidth(280)
        preview_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        center.addWidget(preview_widget)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        platforms_label = QLabel("Apply To Platforms")
        platforms_label.setProperty("role", "heading")
        platforms_label.setStyleSheet(f"color: {C.text_primary}; background: transparent;")
        right_col.addWidget(platforms_label)

        self._platform_checks: dict[str, QCheckBox] = {}
        self._platform_badges: dict[str, Badge] = {}
        self._platform_login_btns: dict[str, GhostButton] = {}

        for pid, pdata in PLATFORMS.items():
            row = QHBoxLayout()
            row.setSpacing(8)

            cb = QCheckBox(pdata["display_name"])
            cb.setChecked(True)
            self._platform_checks[pid] = cb

            badge = Badge("Connected", "success")
            self._platform_badges[pid] = badge

            login_btn = GhostButton("Log in")
            login_btn.setFixedHeight(26)
            login_btn.setStyleSheet(
                f"QPushButton {{ color: {C.text_secondary}; font-size: 11px; padding: 2px 12px;"
                f"background: transparent; border: 1px solid {C.border_default}; border-radius: 6px; }}"
                f"QPushButton:hover {{ background: {C.bg_card}; border-color: {C.border_strong};"
                f"color: {C.text_primary}; }}"
            )
            login_btn.clicked.connect(lambda _checked=False, p=pid: self.login_requested.emit(p))
            login_btn.hide()
            self._platform_login_btns[pid] = login_btn

            row.addWidget(cb)
            row.addWidget(badge)
            row.addWidget(login_btn)
            row.addStretch()
            right_col.addLayout(row)

        right_col.addSpacing(8)

        caption_label = QLabel("Caption / Description")
        caption_label.setStyleSheet(
            f"color: {C.text_primary}; font-size: 13px; font-weight: 500; background: transparent;"
        )
        right_col.addWidget(caption_label)

        self._caption_input = TextArea("Add a caption for platforms that support it...")
        self._caption_input.setMinimumHeight(60)
        self._caption_input.setMaximumHeight(120)
        right_col.addWidget(self._caption_input)

        supported = [PLATFORMS[p]["display_name"] for p in CAPTION_SUPPORTED_PLATFORMS if p in PLATFORMS]
        unsupported = [pdata["display_name"] for pid, pdata in PLATFORMS.items() if pid not in CAPTION_SUPPORTED_PLATFORMS]
        caption_info = QLabel(
            f"Caption will be posted on: {', '.join(supported)}\n"
            f"Not supported: {', '.join(unsupported)}"
        )
        caption_info.setWordWrap(True)
        caption_info.setStyleSheet(
            f"color: {C.text_muted}; font-size: 11px; background: transparent;"
        )
        right_col.addWidget(caption_info)

        right_col.addSpacing(8)

        self._apply_btn = PrimaryButton("Apply Changes")
        self._apply_btn.clicked.connect(self._apply_changes)
        right_col.addWidget(self._apply_btn)

        right_col.addSpacing(16)

        log_label = QLabel("Log")
        log_label.setStyleSheet(f"color: {C.text_muted}; font-size: 11px; background: transparent;")
        right_col.addWidget(log_label)

        self._log = LogPanel()
        self._log.setMinimumHeight(80)
        self._log.setMaximumHeight(200)
        right_col.addWidget(self._log)
        right_col.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right_col)
        center.addWidget(right_widget, 1)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def refresh(self):
        pp = self.db.get_profile_picture()
        if pp and pp.file_path and os.path.isfile(pp.file_path):
            self._image_path = pp.file_path
            self._set_preview(pp.file_path)

        platforms = self.db.get_platforms()
        connected_ids = {p.id for p in platforms if p.connected}

        for pid, cb in self._platform_checks.items():
            badge = self._platform_badges[pid]
            login_btn = self._platform_login_btns[pid]
            if pid in connected_ids:
                cb.setEnabled(True)
                cb.setChecked(True)
                badge.set_text_and_variant("Connected", "success")
                badge.show()
                login_btn.hide()
            else:
                cb.setEnabled(False)
                cb.setChecked(False)
                badge.hide()
                login_btn.show()

    def _set_preview(self, path: str):
        if os.path.isfile(path):
            pm = QPixmap(path).scaled(
                196, 196,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            rounded = QPixmap(196, 196)
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            clip = QPainterPath()
            clip.addEllipse(0, 0, 196, 196)
            painter.setClipPath(clip)
            x = (pm.width() - 196) // 2
            y = (pm.height() - 196) // 2
            painter.drawPixmap(0, 0, pm, max(x, 0), max(y, 0), 196, 196)
            painter.end()
            self._preview.setPixmap(rounded)

    def _pick_image(self):
        dialog = PhotoPickerDialog(self.db, parent=self)
        dialog.photo_selected.connect(self._on_photo_picked)
        dialog.exec()

    def _on_photo_picked(self, file_path: str):
        self._image_path = file_path
        self._set_preview(file_path)
        self.db.set_profile_picture(file_path)
        self.avatar_changed.emit(file_path)

    def _apply_changes(self):
        if not self._image_path:
            self._log.log("No image selected.", "warning")
            return

        selected = [pid for pid, cb in self._platform_checks.items() if cb.isChecked() and cb.isEnabled()]
        if not selected:
            self._log.log("No platforms selected.", "warning")
            return

        caption = self._caption_input.toPlainText().strip()

        self._apply_btn.setEnabled(False)
        self._apply_btn.setText("Applying...")

        self._thread = QThread()
        worker = ProfilePicWorker(
            self.data_dir, self._image_path, selected, caption=caption,
        )
        self._worker = worker
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(self._on_worker_done)
        worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_worker_progress(self, platform_id: str, message: str, level: str):
        pname = PLATFORMS.get(platform_id, {}).get("display_name", platform_id)
        self._log.log(f"{pname}: {message}", level)
        self.log_message.emit(f"Profile pic - {pname}: {message}", level)

    def _on_worker_done(self):
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText("Apply Changes")
        self._log.log("Done.", "info")
