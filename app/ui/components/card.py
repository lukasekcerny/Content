from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QSizePolicy
from PySide6.QtGui import QPixmap, QMouseEvent
from PySide6.QtCore import Qt, Signal

from app.constants import COLORS as C
from app.ui.components.badge import Badge

CARD_W = 200
CARD_H = 240
THUMB_H = 150


class ContentCard(QFrame):
    """Clickable content card showing thumbnail, filename, badges, and progress bars."""

    clicked = Signal(int)

    def __init__(self, content_id: int, parent=None):
        super().__init__(parent)
        self.content_id = content_id
        self.setProperty("role", "card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(160, 200)
        self.setMaximumSize(280, 320)
        self.setFixedSize(CARD_W, CARD_H)
        sp = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(sp)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        self._thumbnail = QLabel()
        self._thumbnail.setMinimumSize(160, 120)
        self._thumbnail.setMaximumHeight(180)
        self._thumbnail.setFixedHeight(THUMB_H)
        self._thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail.setStyleSheet(
            f"background-color: {C.bg_input}; border-radius: 12px 12px 0 0;"
            f"border: none;"
        )
        self._thumbnail.setScaledContents(False)

        self._filename = QLabel()
        self._filename.setStyleSheet(
            f"color: {C.text_primary}; font-size: 12px; padding: 4px 10px 0 10px;"
            f"background: transparent;"
        )
        self._filename.setMaximumWidth(CARD_W - 10)
        self._filename.setWordWrap(False)

        self._badge_row = QHBoxLayout()
        self._badge_row.setContentsMargins(10, 0, 10, 0)
        self._badge_row.setSpacing(4)
        self._badge_row.addStretch()

        self._progress_container = QVBoxLayout()
        self._progress_container.setContentsMargins(10, 0, 10, 0)
        self._progress_container.setSpacing(2)

        layout.addWidget(self._thumbnail)
        layout.addWidget(self._filename)
        layout.addLayout(self._badge_row)
        layout.addLayout(self._progress_container)
        layout.addStretch()

    def set_thumbnail(self, pixmap: QPixmap):
        w = self._thumbnail.width() or CARD_W
        h = self._thumbnail.height() or THUMB_H
        scaled = pixmap.scaled(
            w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail.setPixmap(scaled)

    def set_filename(self, name: str):
        metrics = self._filename.fontMetrics()
        elided = metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, self.width() - 20)
        self._filename.setText(elided)
        self._filename.setToolTip(name)

    def add_badge(self, text: str, variant: str = "neutral"):
        badge = Badge(text, variant)
        self._badge_row.insertWidget(self._badge_row.count() - 1, badge)

    def clear_badges(self):
        while self._badge_row.count() > 1:
            item = self._badge_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_progress_row(self, widget: QWidget):
        self._progress_container.addWidget(widget)

    def clear_progress(self):
        while self._progress_container.count():
            item = self._progress_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.content_id)
        super().mousePressEvent(event)
