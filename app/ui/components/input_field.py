from PySide6.QtWidgets import QLineEdit, QTextEdit, QPushButton, QHBoxLayout, QWidget
from PySide6.QtCore import Qt

from app.constants import COLORS as C


class InputField(QLineEdit):
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)


class PasswordField(QWidget):
    """Password input with a show/hide toggle button."""

    def __init__(self, placeholder: str = "Password", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._input, 1)

        self._toggle = QPushButton("Show")
        self._toggle.setFixedWidth(50)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setStyleSheet(
            f"QPushButton {{ background-color: {C.bg_card}; color: {C.text_muted};"
            f"border: 1px solid {C.border_soft}; border-radius: 6px;"
            f"font-size: 11px; padding: 4px 6px; }}"
            f"QPushButton:hover {{ background-color: {C.bg_card_hover}; color: {C.text_primary}; }}"
        )
        self._toggle.clicked.connect(self._on_toggle)
        layout.addWidget(self._toggle)

        self._visible = False

    def _on_toggle(self):
        self._visible = not self._visible
        if self._visible:
            self._input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle.setText("Hide")
        else:
            self._input.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle.setText("Show")

    def text(self) -> str:
        return self._input.text()

    def setText(self, text: str):
        self._input.setText(text)

    def setPlaceholderText(self, text: str):
        self._input.setPlaceholderText(text)

    def setEchoMode(self, mode):
        self._input.setEchoMode(mode)


class TextArea(QTextEdit):
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setAcceptRichText(False)
        self.setStyleSheet(
            f"QTextEdit {{ background-color: {C.bg_input}; color: {C.text_primary};"
            f"border: 1px solid {C.border_soft}; border-radius: 8px; padding: 8px 12px; }}"
            f"QTextEdit:focus {{ border-color: {C.border_strong}; background-color: #141516; }}"
        )
