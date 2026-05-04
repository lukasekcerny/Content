from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

from app.constants import COLORS as C
from app.ui.components.button import ConfirmButton, DangerButton


class ContinueConfirmDialog(QDialog):
    """Pauses the emulator flow when something failed.

    Asks the user whether to continue with the remaining platforms or cancel.
    The emulator stays running in either case so the user can fix things manually.
    """

    def __init__(self, platform_name: str, reason: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Jsme připraveni pokračovat?")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"background-color: {C.bg_popup};")

        self._should_continue = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Jsme připraveni pokračovat?")
        title.setStyleSheet(
            f"color: {C.text_primary}; font-size: 15px; font-weight: 600; background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subject = QLabel(f"Problém na: {platform_name}")
        subject.setStyleSheet(
            f"color: {C.warning_text}; font-size: 12px; font-weight: 500; background: transparent;"
        )
        subject.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subject)

        reason_label = QLabel(reason)
        reason_label.setStyleSheet(
            f"color: {C.text_muted}; font-size: 12px; background: transparent;"
        )
        reason_label.setWordWrap(True)
        reason_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(reason_label)

        hint = QLabel(
            "Emulátor zůstane spuštěný. Oprav problém ručně a klikni 'Continue'\n"
            "nebo 'Cancel' pro ukončení flow (emulátor zůstane běžet)."
        )
        hint.setStyleSheet(
            f"color: {C.text_disabled}; font-size: 11px; background: transparent;"
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._cancel_btn = DangerButton("Cancel")
        self._cancel_btn.setFixedHeight(38)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        self._continue_btn = ConfirmButton("Continue")
        self._continue_btn.setFixedHeight(38)
        self._continue_btn.setDefault(True)
        self._continue_btn.clicked.connect(self._on_continue)
        btn_row.addWidget(self._continue_btn)

        layout.addLayout(btn_row)

    @property
    def should_continue(self) -> bool:
        return self._should_continue

    def _on_continue(self):
        self._should_continue = True
        self.accept()

    def _on_cancel(self):
        self._should_continue = False
        self.accept()
