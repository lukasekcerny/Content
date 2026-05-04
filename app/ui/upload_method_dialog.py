from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

from app.constants import COLORS as C
from app.ui.components.button import PrimaryButton


class UploadMethodDialog(QDialog):
    """Dialog asking the user whether to post via Web (browser) or Emulator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose upload method")
        self.setFixedSize(380, 180)
        self.setStyleSheet(f"background-color: {C.bg_popup};")

        self._choice: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        label = QLabel("How do you want to post?")
        label.setStyleSheet(
            f"color: {C.text_primary}; font-size: 15px; font-weight: 600; background: transparent;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        desc = QLabel("Web uses the browser automation.\nEmulator opens the mobile app in Android emulator.")
        desc.setStyleSheet(f"color: {C.text_muted}; font-size: 12px; background: transparent;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._web_btn = PrimaryButton("Web (Browser)")
        self._web_btn.setFixedHeight(38)
        self._web_btn.clicked.connect(self._on_web)
        btn_row.addWidget(self._web_btn)

        self._emu_btn = PrimaryButton("Emulator")
        self._emu_btn.setFixedHeight(38)
        self._emu_btn.clicked.connect(self._on_emulator)
        btn_row.addWidget(self._emu_btn)

        layout.addLayout(btn_row)

    @property
    def choice(self) -> str:
        return self._choice

    def _on_web(self):
        self._choice = "web"
        self.accept()

    def _on_emulator(self):
        self._choice = "emulator"
        self.accept()
