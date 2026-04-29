from PySide6.QtWidgets import QProgressBar, QWidget, QHBoxLayout, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve

from app.constants import COLORS as C


class ContentProgressBar(QProgressBar):
    """Dual-phase progress bar: import (dark) -> upload (orange) -> done (green) / error (red)."""

    def __init__(self, large: bool = False, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setRange(0, 100)
        self.setValue(0)
        if large:
            self.setProperty("size", "large")
        self.set_phase("import")

    def set_phase(self, phase: str):
        self.setProperty("phase", phase)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_progress(self, value: int, phase: str = None):
        if phase:
            self.set_phase(phase)
        self.setValue(min(max(value, 0), 100))


class PlatformProgressRow(QWidget):
    """A row showing: platform label + progress bar + percentage text."""

    def __init__(self, platform_name: str, large: bool = False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self._platform_name = platform_name

        self._label = QLabel()
        self._label.setMinimumWidth(50)
        self._label.setMaximumWidth(100)
        self._label.setStyleSheet(f"color: {C.text_secondary}; font-size: 12px; background: transparent;")
        self._label.setToolTip(platform_name)
        self._set_elided_label()

        self._bar = ContentProgressBar(large=large)
        self._bar.setMinimumWidth(80)

        self._percent = QLabel("0%")
        self._percent.setFixedWidth(40)
        self._percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._percent.setStyleSheet(f"color: {C.text_muted}; font-size: 11px; background: transparent;")

        self._status = QLabel("")
        self._status.setMinimumWidth(50)
        self._status.setMaximumWidth(100)
        self._status.setStyleSheet(f"color: {C.text_muted}; font-size: 11px; background: transparent;")

        layout.addWidget(self._label)
        layout.addWidget(self._bar, 1)
        layout.addWidget(self._percent)
        layout.addWidget(self._status)

    def _set_elided_label(self):
        metrics = self._label.fontMetrics()
        elided = metrics.elidedText(self._platform_name, Qt.TextElideMode.ElideRight, 90)
        self._label.setText(elided)

    def _set_elided_status(self, text: str):
        metrics = self._status.fontMetrics()
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, 90)
        self._status.setText(elided)
        if elided != text:
            self._status.setToolTip(text)
        else:
            self._status.setToolTip("")

    def set_progress(self, value: int, phase: str = "upload", status_text: str = ""):
        self._bar.set_progress(value, phase)
        self._percent.setText(f"{value}%")
        self._set_elided_status(status_text)

        color_map = {
            "upload": C.warning_text,
            "done": C.success_text,
            "error": C.danger_text,
            "import": C.text_muted,
        }
        color = color_map.get(phase, C.text_muted)
        self._status.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")

    def set_done(self):
        self.set_progress(100, "done", "Published")

    def set_error(self, msg: str = "Failed"):
        self._bar.set_phase("error")
        self._set_elided_status(msg)
        self._status.setStyleSheet(f"color: {C.danger_text}; font-size: 11px; background: transparent;")
