from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QCheckBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from app.constants import COLORS as C
from app.ui.components.input_field import InputField, PasswordField
from app.ui.components.button import PrimaryButton


class CookieConsentDialog(QDialog):
    """Modal dialog asking the user how to handle cookie consent."""

    def __init__(self, platform_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cookie Consent")
        self.setMinimumSize(320, 160)
        self.setModal(True)
        self._choice = "all"

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        msg = QLabel(f"{platform_name} is asking about cookies.\nHow would you like to proceed?")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color: {C.text_primary}; font-size: 13px; background: transparent;")
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        essential_btn = QPushButton("Essential Only")
        essential_btn.setStyleSheet(
            f"QPushButton {{ background-color: {C.bg_card}; color: {C.text_secondary};"
            f"border: 1px solid {C.border_soft}; border-radius: 8px; padding: 8px 16px; }}"
            f"QPushButton:hover {{ background-color: {C.bg_card_hover}; }}"
        )
        essential_btn.clicked.connect(lambda: self._set_choice("essential"))

        accept_btn = PrimaryButton("Accept All")
        accept_btn.clicked.connect(lambda: self._set_choice("all"))

        btn_row.addWidget(essential_btn)
        btn_row.addWidget(accept_btn)
        layout.addLayout(btn_row)

    def _set_choice(self, choice: str):
        self._choice = choice
        self.accept()

    @property
    def choice(self) -> str:
        return self._choice


class LoginDialog(QDialog):
    """In-app login form for a specific platform."""

    login_submitted = Signal(str, str, str, bool)

    def __init__(self, platform_id: str, platform_name: str,
                 saved_email: str = "", saved_password: str = "",
                 parent=None):
        super().__init__(parent)
        self.platform_id = platform_id
        self.setWindowTitle(f"Connect to {platform_name}")
        self.setMinimumSize(340, 260)
        self.resize(400, 310)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(f"Log in to {platform_name}")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)

        desc = QLabel("Enter your credentials. They will be stored securely\nin Windows Credential Locker.")
        desc.setProperty("role", "muted")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._email = InputField("Email or username")
        layout.addWidget(self._email)

        self._password = PasswordField("Password")
        layout.addWidget(self._password)

        self._remember_cb = QCheckBox("Remember credentials")
        self._remember_cb.setChecked(True)
        self._remember_cb.setStyleSheet(
            f"QCheckBox {{ color: {C.text_secondary}; font-size: 12px; background: transparent; }}"
        )
        layout.addWidget(self._remember_cb)

        if saved_email:
            self._email.setText(saved_email)
        if saved_password:
            self._password.setText(saved_password)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("role", "ghost")
        cancel_btn.clicked.connect(self.reject)

        self._login_btn = PrimaryButton("Log In")
        self._login_btn.clicked.connect(self._on_submit)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._login_btn)
        layout.addLayout(btn_row)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {C.danger_text}; font-size: 12px; background: transparent;")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

    @property
    def remember(self) -> bool:
        return self._remember_cb.isChecked()

    def _on_submit(self):
        email = self._email.text().strip()
        password = self._password.text()
        if not email or not password:
            self._error_label.setText("Please fill in both fields.")
            self._error_label.show()
            self.adjustSize()
            return
        self._login_btn.setEnabled(False)
        self._login_btn.setText("Logging in...")
        self.login_submitted.emit(self.platform_id, email, password, self.remember)

    def show_error(self, message: str):
        self._error_label.setText(message)
        self._error_label.show()
        self._login_btn.setEnabled(True)
        self._login_btn.setText("Log In")
        self.adjustSize()

    def show_success(self):
        self.accept()
