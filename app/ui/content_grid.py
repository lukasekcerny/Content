import logging
import os
import shutil

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QFrame,
    QGridLayout, QSizePolicy, QPushButton,
)
from PySide6.QtGui import QPixmap, QResizeEvent, QDragEnterEvent, QDropEvent, QDragLeaveEvent
from PySide6.QtCore import Qt, Signal, QThread, QObject, QTimer

from app.constants import COLORS as C
from app.db.database import Database
from app.db.models import Content
from app.ui.components.card import ContentCard
from app.ui.components.progress_bar import ContentProgressBar

logger = logging.getLogger(__name__)

try:
    import filetype
except ImportError:
    filetype = None

try:
    from PIL import Image
except ImportError:
    Image = None

CARD_WIDTH = 200
CARD_SPACING = 16

SUPPORTED_EXTENSIONS = {
    ".mp4", ".mov", ".webm", ".avi", ".wmv", ".flv", ".mkv",
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff",
}


class FileImporter(QObject):
    """Imports files in a background thread."""

    progress = Signal(str, int)
    finished = Signal(str, object)
    error = Signal(str, str)

    def __init__(self, file_path: str, data_dir: str):
        super().__init__()
        self.file_path = file_path
        self.data_dir = data_dir

    def run(self):
        try:
            logger.info("FileImporter: starting import of %s", self.file_path)
            fname = os.path.basename(self.file_path)
            media_dir = os.path.join(self.data_dir, "media")
            thumb_dir = os.path.join(self.data_dir, "thumbnails")
            os.makedirs(media_dir, exist_ok=True)
            os.makedirs(thumb_dir, exist_ok=True)

            dest = os.path.join(media_dir, fname)
            counter = 1
            base, ext = os.path.splitext(fname)
            while os.path.exists(dest):
                dest = os.path.join(media_dir, f"{base}_{counter}{ext}")
                counter += 1

            self.progress.emit(self.file_path, 20)
            shutil.copy2(self.file_path, dest)
            self.progress.emit(self.file_path, 50)

            file_size = os.path.getsize(dest)
            mime_type = ""
            if filetype:
                kind = filetype.guess(dest)
                if kind:
                    mime_type = kind.mime
            if not mime_type:
                ext_lower = ext.lower()
                mime_map = {
                    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
                    ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
                    ".tiff": "image/tiff",
                }
                mime_type = mime_map.get(ext_lower, "application/octet-stream")

            width, height, duration = 0, 0, 0.0
            thumb_path = ""

            if mime_type.startswith("image/") and Image:
                try:
                    with Image.open(dest) as img:
                        width, height = img.size
                    thumb_dest = os.path.join(thumb_dir, os.path.basename(dest) + ".thumb.png")
                    with Image.open(dest) as img:
                        img.thumbnail((200, 150))
                        img.save(thumb_dest, "PNG")
                    thumb_path = thumb_dest
                except Exception:
                    pass

            self.progress.emit(self.file_path, 90)

            content = Content(
                file_path=dest,
                file_name=os.path.basename(dest),
                mime_type=mime_type,
                file_size=file_size,
                width=width,
                height=height,
                duration_seconds=duration,
                thumbnail_path=thumb_path,
            )

            self.progress.emit(self.file_path, 100)
            logger.info("FileImporter: import complete %s -> %s", self.file_path, dest)
            self.finished.emit(self.file_path, content)

        except Exception as e:
            logger.error("FileImporter: import failed %s: %s", self.file_path, e)
            self.error.emit(self.file_path, str(e))


_TAB_STYLE_INACTIVE = (
    f"QPushButton {{ background-color: {C.bg_card}; color: {C.text_secondary};"
    f"border: 1px solid {C.border_soft}; border-radius: 8px;"
    f"padding: 6px 18px; font-size: 13px; font-weight: 500; }}"
    f"QPushButton:hover {{ background-color: {C.bg_card_hover}; }}"
)
_TAB_STYLE_ACTIVE = (
    f"QPushButton {{ background-color: {C.bg_card_active}; color: {C.text_primary};"
    f"border: 1px solid {C.border_strong}; border-radius: 8px;"
    f"padding: 6px 18px; font-size: 13px; font-weight: 600; }}"
)

TABS = [
    ("video", "Videos"),
    ("photo", "Photos"),
    ("gif", "GIFs"),
]

EMPTY_MESSAGES = {
    "video": "No videos yet. Drag and drop video files here to get started.",
    "photo": "No photos yet. Drag and drop image files here to get started.",
    "gif": "No GIFs yet. Drag and drop GIF files here to get started.",
}


class ContentGridPage(QWidget):
    """Main page showing content grid with drag-and-drop zone and type tabs."""

    content_clicked = Signal(int)
    log_message = Signal(str, str)

    def __init__(self, db: Database, data_dir: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.data_dir = data_dir
        self._threads: list[QThread] = []
        self._workers: list[FileImporter] = []
        self._cards: dict[int, ContentCard] = {}
        self._import_bars: dict[str, ContentProgressBar] = {}
        self._current_cols = 0
        self._active_tab = "video"

        self.setAcceptDrops(True)

        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.setInterval(50)
        self._reflow_timer.timeout.connect(self._do_reflow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        self._tab_buttons: dict[str, QPushButton] = {}
        for tab_id, tab_label in TABS:
            btn = QPushButton(tab_label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, t=tab_id: self._switch_tab(t))
            self._tab_buttons[tab_id] = btn
            tab_row.addWidget(btn)
        tab_row.addStretch()
        layout.addLayout(tab_row)
        self._update_tab_styles()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(CARD_SPACING)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_widget)

        layout.addWidget(self._scroll, 1)

        self._empty_label = QLabel(EMPTY_MESSAGES["video"])
        self._empty_label.setProperty("role", "muted")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(
            f"color: {C.text_disabled}; font-size: 14px; padding: 40px; background: transparent;"
        )
        self._grid_layout.addWidget(self._empty_label, 0, 0, 1, 4)

        self._drop_overlay = QLabel("Drop files here\nVideos, photos, GIFs")
        self._drop_overlay.setParent(self)
        self._drop_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_overlay.setStyleSheet(
            f"background-color: rgba(6, 6, 6, 0.85);"
            f"border: 2px dashed {C.border_strong};"
            f"border-radius: 14px;"
            f"color: {C.text_muted}; font-size: 18px; font-weight: 500;"
        )
        self._drop_overlay.hide()

    def _update_tab_styles(self):
        for tab_id, btn in self._tab_buttons.items():
            btn.setStyleSheet(_TAB_STYLE_ACTIVE if tab_id == self._active_tab else _TAB_STYLE_INACTIVE)

    def _switch_tab(self, tab_id: str):
        if tab_id == self._active_tab:
            return
        self._active_tab = tab_id
        self._update_tab_styles()
        self.refresh()

    def _query_for_tab(self) -> list[Content]:
        if self._active_tab == "video":
            return self.db.get_content_by_mime_prefix("video/")
        elif self._active_tab == "photo":
            return self.db.get_images_only()
        else:
            return self.db.get_content_by_mime_prefix("image/gif")

    def _calc_columns(self) -> int:
        available = self._scroll.viewport().width() - 8
        cols = max(1, available // (CARD_WIDTH + CARD_SPACING))
        return min(cols, 5)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._drop_overlay.setGeometry(0, 0, self.width(), self.height())
        self._reflow_timer.start()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_overlay.show()
            self._drop_overlay.raise_()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self._drop_overlay.hide()

    def dropEvent(self, event: QDropEvent):
        self._drop_overlay.hide()
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
                if ext in SUPPORTED_EXTENSIONS:
                    paths.append(path)
        if paths:
            event.acceptProposedAction()
            self._import_files(paths)

    def _do_reflow(self):
        new_cols = self._calc_columns()
        if new_cols != self._current_cols and self._cards:
            self._relayout_cards(new_cols)

    def _relayout_cards(self, cols: int):
        self._current_cols = cols
        card_list = list(self._cards.values())

        for i in reversed(range(self._grid_layout.count())):
            self._grid_layout.takeAt(i)

        for i, card in enumerate(card_list):
            self._grid_layout.addWidget(card, i // cols, i % cols)

    def refresh(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        contents = self._query_for_tab()
        if not contents:
            self._empty_label = QLabel(EMPTY_MESSAGES.get(self._active_tab, "No content."))
            self._empty_label.setProperty("role", "muted")
            self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty_label.setWordWrap(True)
            self._empty_label.setStyleSheet(
                f"color: {C.text_disabled}; font-size: 14px; padding: 40px; background: transparent;"
            )
            self._grid_layout.addWidget(self._empty_label, 0, 0, 1, 4)
            return

        cols = self._calc_columns()
        self._current_cols = cols

        for i, content in enumerate(contents):
            card = ContentCard(content.id)
            card.set_filename(content.file_name)

            if content.thumbnail_path and os.path.isfile(content.thumbnail_path):
                card.set_thumbnail(QPixmap(content.thumbnail_path))
            else:
                if content.mime_type.startswith("video/"):
                    card.add_badge("Video", "neutral")
                elif content.mime_type == "image/gif":
                    card.add_badge("GIF", "neutral")
                elif content.mime_type.startswith("image/"):
                    card.add_badge("Image", "neutral")

            posts = self.db.get_posts_for_content(content.id)
            for post in posts:
                badge_map = {
                    "published": ("Published", "success"),
                    "failed": ("Failed", "danger"),
                    "uploading": ("Uploading", "warning"),
                    "scheduled": ("Scheduled", "neutral"),
                    "draft": ("Draft", "neutral"),
                }
                text, variant = badge_map.get(post.status, ("Draft", "neutral"))
                card.add_badge(f"{post.platform_id[:2].upper()}", variant)

            card.clicked.connect(self.content_clicked.emit)
            self._cards[content.id] = card
            self._grid_layout.addWidget(card, i // cols, i % cols)

    def _import_files(self, paths: list[str]):
        for path in paths:
            self.log_message.emit(f"Importing {os.path.basename(path)}...", "info")

            bar = ContentProgressBar()
            bar.set_phase("import")
            bar.setValue(0)
            bar.setFixedHeight(6)
            self._import_bars[path] = bar
            self._grid_layout.addWidget(bar, self._grid_layout.rowCount(), 0, 1, max(self._current_cols, 1))

            thread = QThread()
            worker = FileImporter(path, self.data_dir)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.progress.connect(self._on_import_progress)
            worker.finished.connect(self._on_import_done)
            worker.error.connect(self._on_import_error)
            worker.finished.connect(thread.quit)
            worker.error.connect(thread.quit)
            thread.finished.connect(thread.deleteLater)
            self._threads.append(thread)
            self._workers.append(worker)
            thread.start()

    def _on_import_progress(self, file_path: str, value: int):
        bar = self._import_bars.get(file_path)
        if bar:
            bar.setValue(value)

    def _tab_for_mime(self, mime_type: str) -> str:
        if mime_type.startswith("video/"):
            return "video"
        if mime_type == "image/gif":
            return "gif"
        if mime_type.startswith("image/"):
            return "photo"
        return self._active_tab

    def _on_import_done(self, file_path: str, content: Content):
        bar = self._import_bars.pop(file_path, None)
        if bar:
            bar.deleteLater()
        self.db.add_content(content)
        self.log_message.emit(f"Imported {content.file_name}", "success")
        target_tab = self._tab_for_mime(content.mime_type)
        if target_tab != self._active_tab:
            self._active_tab = target_tab
            self._update_tab_styles()
        self.refresh()

    def _on_import_error(self, file_path: str, error: str):
        bar = self._import_bars.pop(file_path, None)
        if bar:
            bar.set_phase("error")
            bar.setValue(100)
        self.log_message.emit(f"Failed to import {os.path.basename(file_path)}: {error}", "error")
