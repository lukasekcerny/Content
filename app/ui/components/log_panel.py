from datetime import datetime

from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtCore import Qt

from app.constants import COLORS as C


class LogPanel(QPlainTextEdit):
    """Monospace log panel for the sidebar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(500)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {C.bg_shell}; color: {C.text_muted};"
            f"border: none; border-top: 1px solid {C.border_soft}; border-radius: 0;"
            f"font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 11px;"
            f"padding: 8px; }}"
        )

    def log(self, message: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "info": C.text_muted,
            "success": C.success_text,
            "warning": C.warning_text,
            "error": C.danger_text,
        }
        color = color_map.get(level, C.text_muted)
        self.appendHtml(
            f'<span style="color:{C.text_disabled}">{ts}</span> '
            f'<span style="color:{color}">{message}</span>'
        )
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
