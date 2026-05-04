from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from app.constants import COLORS as C, PLATFORMS
from app.db.database import Database
from app.ui.components.badge import Badge
from app.ui.components.log_panel import LogPanel


class PlatformItem(QFrame):
    """Single platform row in sidebar: icon-area + name + badge + connect button."""

    connect_clicked = Signal(str)

    def __init__(self, platform_id: str, display_name: str, parent=None):
        super().__init__(parent)
        self.platform_id = platform_id
        self._active = False

        self.setStyleSheet(
            f"PlatformItem {{ background: transparent; border: none; padding: 0; }}"
            f"PlatformItem:hover {{ background-color: {C.bg_card}; }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        self._indicator = QFrame()
        self._indicator.setFixedSize(3, 28)
        self._indicator.setStyleSheet(f"background: transparent; border: none; border-radius: 1px;")

        self._name = QLabel(display_name)
        self._name.setStyleSheet(f"color: {C.text_secondary}; font-size: 13px; background: transparent;")
        self._name.setToolTip(display_name)

        self._badge = Badge("Not connected", "neutral")

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setFixedHeight(28)
        self._connect_btn.setStyleSheet(
            f"QPushButton {{ font-size: 11px; padding: 2px 8px; }}"
        )
        self._connect_btn.clicked.connect(lambda: self.connect_clicked.emit(self.platform_id))

        layout.addWidget(self._indicator)
        layout.addWidget(self._name, 1)
        layout.addWidget(self._badge)
        layout.addWidget(self._connect_btn)

    def set_connected(self, username: str):
        self._badge.set_text_and_variant("Connected", "success")
        self._connect_btn.show()
        self._connect_btn.setEnabled(True)
        self._connect_btn.setText("Reconnect")
        self._name.setStyleSheet(f"color: {C.text_primary}; font-size: 13px; font-weight: 500; background: transparent;")

    def set_disconnected(self):
        self._badge.set_text_and_variant("Not connected", "neutral")
        self._connect_btn.show()
        self._connect_btn.setEnabled(True)
        self._connect_btn.setText("Connect")
        self._name.setStyleSheet(f"color: {C.text_secondary}; font-size: 13px; background: transparent;")

    def set_reconnecting(self):
        self._badge.set_text_and_variant("Connecting...", "warning")
        self._connect_btn.show()
        self._connect_btn.setEnabled(False)
        self._connect_btn.setText("Working...")

    def set_failed(self, reason: str = "Login failed"):
        self._badge.set_text_and_variant(reason, "danger")
        self._connect_btn.show()
        self._connect_btn.setEnabled(True)
        self._connect_btn.setText("Retry")

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._indicator.setStyleSheet(f"background: {C.sidebar_indicator}; border: none; border-radius: 1px;")
            self.setStyleSheet(
                f"PlatformItem {{ background-color: {C.bg_card_active}; border: none; }}"
            )
        else:
            self._indicator.setStyleSheet(f"background: transparent; border: none; border-radius: 1px;")
            self.setStyleSheet(
                f"PlatformItem {{ background: transparent; border: none; }}"
                f"PlatformItem:hover {{ background-color: {C.bg_card}; }}"
            )


class Sidebar(QFrame):
    """Left sidebar: platform list + log panel."""

    platform_connect = Signal(str)
    emulator_clicked = Signal()
    app_log_clicked = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setProperty("role", "sidebar")
        self.setFixedWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Platforms")
        header.setProperty("role", "heading")
        header.setStyleSheet(
            f"color: {C.text_muted}; font-size: 11px; font-weight: 600;"
            f"text-transform: uppercase; letter-spacing: 1px;"
            f"padding: 16px 16px 8px 16px; background: transparent;"
        )
        layout.addWidget(header)

        self._platform_items: dict[str, PlatformItem] = {}
        for pid, pdata in PLATFORMS.items():
            item = PlatformItem(pid, pdata["display_name"])
            item.connect_clicked.connect(self.platform_connect.emit)
            self._platform_items[pid] = item
            layout.addWidget(item)

        layout.addSpacing(12)

        self._emulator_btn = QPushButton("Mobile Emulator")
        self._emulator_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._emulator_btn.setStyleSheet(
            f"QPushButton {{ font-size: 12px; font-weight: 500;"
            f"padding: 6px 12px; margin: 0 12px; }}"
        )
        self._emulator_btn.clicked.connect(self.emulator_clicked.emit)
        layout.addWidget(self._emulator_btn)

        layout.addSpacing(6)

        self._applog_btn = QPushButton("App Log")
        self._applog_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._applog_btn.setStyleSheet(
            f"QPushButton {{ font-size: 12px; font-weight: 500;"
            f"padding: 6px 12px; margin: 0 12px; }}"
        )
        self._applog_btn.clicked.connect(self.app_log_clicked.emit)
        layout.addWidget(self._applog_btn)

        layout.addStretch(1)

        log_label = QLabel("Activity Log")
        log_label.setStyleSheet(
            f"color: {C.text_muted}; font-size: 11px; font-weight: 600;"
            f"padding: 8px 16px 4px 16px; background: transparent;"
        )
        layout.addWidget(log_label)

        self.log_panel = LogPanel()
        self.log_panel.setMinimumHeight(100)
        layout.addWidget(self.log_panel, 1)

        self.refresh_platforms()

    def refresh_platforms(self):
        for p in self.db.get_platforms():
            item = self._platform_items.get(p.id)
            if item:
                if p.connected:
                    item.set_connected(p.username or "")
                else:
                    item.set_disconnected()

    def get_item(self, platform_id: str) -> PlatformItem:
        return self._platform_items.get(platform_id)
