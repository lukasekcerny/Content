from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, Signal

from app.constants import COLORS as C


class ModeToggle(QFrame):
    """Segmented two-button toggle: Web | Phone.

    Used in the main window header to switch the global app mode that
    controls whether Post Now / Apply Changes runs through the web flow
    (Playwright) or the phone flow (Android emulator).
    """

    mode_changed = Signal(str)

    def __init__(self, current: str = "web", parent=None):
        super().__init__(parent)
        self._current = current if current in ("web", "phone") else "web"

        self.setStyleSheet(
            f"QFrame {{ background-color: {C.bg_input}; border: 1px solid {C.border_soft};"
            f"border-radius: 10px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        self._web_btn = self._make_btn("Web")
        self._phone_btn = self._make_btn("Phone")

        self._web_btn.clicked.connect(lambda: self._set_mode("web"))
        self._phone_btn.clicked.connect(lambda: self._set_mode("phone"))

        layout.addWidget(self._web_btn)
        layout.addWidget(self._phone_btn)

        self._refresh_styles()

    def _make_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(30)
        btn.setMinimumWidth(72)
        btn.setFlat(True)
        return btn

    def _set_mode(self, mode: str):
        if mode == self._current:
            return
        self._current = mode
        self._refresh_styles()
        self.mode_changed.emit(mode)

    def set_mode(self, mode: str):
        if mode in ("web", "phone") and mode != self._current:
            self._current = mode
            self._refresh_styles()

    @property
    def mode(self) -> str:
        return self._current

    def _refresh_styles(self):
        for btn, mode in ((self._web_btn, "web"), (self._phone_btn, "phone")):
            if mode == self._current:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {C.primary_bg};"
                    f"color: {C.primary_text}; border: 1px solid {C.primary_border};"
                    f"border-radius: 8px; font-weight: 600; padding: 4px 14px; }}"
                    f"QPushButton:hover {{ background-color: {C.primary_hover};"
                    f"border-color: {C.primary_text}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: transparent;"
                    f"color: {C.text_muted}; border: 1px solid transparent;"
                    f"border-radius: 8px; font-weight: 500; padding: 4px 14px; }}"
                    f"QPushButton:hover {{ color: {C.text_secondary};"
                    f"background-color: {C.bg_card}; }}"
                )
