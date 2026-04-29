from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from app.constants import COLORS as C


class DropZone(QFrame):
    """Overlay widget that appears when files are dragged over the content area."""

    files_dropped = Signal(list)

    SUPPORTED_EXTENSIONS = {
        ".mp4", ".mov", ".webm", ".avi", ".wmv", ".flv", ".mkv",
        ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel("Drop files here")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"color: {C.text_muted}; font-size: 16px; font-weight: 500; background: transparent;"
        )

        self._sublabel = QLabel("Videos, photos, GIFs")
        self._sublabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sublabel.setWordWrap(True)
        self._sublabel.setStyleSheet(
            f"color: {C.text_disabled}; font-size: 13px; background: transparent;"
        )

        layout.addWidget(self._label)
        layout.addWidget(self._sublabel)

        self._set_idle_style()

    def _set_idle_style(self):
        self.setStyleSheet(
            f"DropZone {{ background-color: {C.bg_card}; border: 2px dashed {C.border_default};"
            f"border-radius: 14px; }}"
        )

    def _set_hover_style(self):
        self.setStyleSheet(
            f"DropZone {{ background-color: {C.bg_card_hover}; border: 2px dashed {C.border_strong};"
            f"border-radius: 14px; }}"
        )
        self._label.setText("Release to import")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_hover_style()

    def dragLeaveEvent(self, event):
        self._set_idle_style()
        self._label.setText("Drop files here")

    def dropEvent(self, event: QDropEvent):
        self._set_idle_style()
        self._label.setText("Drop files here")

        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
                if ext in self.SUPPORTED_EXTENSIONS:
                    paths.append(path)

        if paths:
            event.acceptProposedAction()
            self.files_dropped.emit(paths)
