from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent

from app.constants import COLORS as C

MAX_BADGE_WIDTH = 180


class Badge(QLabel):
    """Status chip/badge with state-driven colors and text elision."""

    STYLES = {
        "success": (C.success_bg, C.success_text, C.success),
        "warning": (C.warning_bg, C.warning_text, C.warning),
        "danger": (C.danger_bg, C.danger_text, C.danger),
        "neutral": (C.neutral_state_bg, C.neutral_state_text, C.neutral_state),
    }

    def __init__(self, text: str = "", variant: str = "neutral", parent=None):
        super().__init__("", parent)
        self._full_text = text
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMaximumWidth(MAX_BADGE_WIDTH)
        self.set_variant(variant)
        self._apply_elided_text()

    def set_variant(self, variant: str):
        bg, fg, border = self.STYLES.get(variant, self.STYLES["neutral"])
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid {border};"
            f"border-radius: 6px; padding: 2px 10px; font-size: 11px; font-weight: 500;"
        )

    def set_text_and_variant(self, text: str, variant: str):
        self._full_text = text
        self.setToolTip(text)
        self.set_variant(variant)
        self._apply_elided_text()

    def setText(self, text: str):
        self._full_text = text
        self.setToolTip(text)
        self._apply_elided_text()

    def _apply_elided_text(self):
        available = self.maximumWidth() - 24
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, available)
        super().setText(elided)
        if elided != self._full_text:
            self.setToolTip(self._full_text)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._apply_elided_text()
