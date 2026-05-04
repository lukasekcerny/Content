from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QThread

from app.constants import COLORS as C, DEFAULT_EMULATOR_CONFIG
from app.mobile.emulator_config import (
    AndroidEmulatorConfig,
    MobilePlatform,
    PlatformLaunchResult,
)
from app.mobile.emulator_worker import EmulatorWorker
from app.ui.components.checkbox import PlatformCheckBox
from app.ui.components.button import PrimaryButton


class EmulatorPanel(QWidget):
    """Page for launching mobile apps in the Android emulator."""

    log_message = Signal(str, str)
    back_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: EmulatorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Back button
        back_row = QHBoxLayout()
        back_btn = QLabel("\u2190 Back")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(
            f"color: {C.text_muted}; font-size: 13px; padding: 4px 0; background: transparent;"
        )
        back_btn.mousePressEvent = lambda e: self.back_clicked.emit()
        back_row.addWidget(back_btn)
        back_row.addStretch()
        layout.addLayout(back_row)

        # Title
        title = QLabel("Mobile Emulator")
        title.setStyleSheet(
            f"color: {C.text_primary}; font-size: 20px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "Select platforms and open their mobile apps in the Android emulator."
        )
        subtitle.setStyleSheet(
            f"color: {C.text_muted}; font-size: 13px; background: transparent;"
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Platform checkboxes
        platforms_card = QFrame()
        platforms_card.setProperty("role", "card")
        card_layout = QVBoxLayout(platforms_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        card_title = QLabel("Platforms")
        card_title.setStyleSheet(
            f"color: {C.text_secondary}; font-size: 12px; font-weight: 600;"
            f"text-transform: uppercase; letter-spacing: 0.5px; background: transparent;"
        )
        card_layout.addWidget(card_title)

        self._checkboxes: dict[MobilePlatform, PlatformCheckBox] = {}
        for platform in MobilePlatform:
            cb = PlatformCheckBox(platform.display_name)
            self._checkboxes[platform] = cb
            card_layout.addWidget(cb)

        layout.addWidget(platforms_card)

        # Launch button
        self._launch_btn = PrimaryButton("Open selected mobile apps")
        self._launch_btn.setFixedHeight(40)
        self._launch_btn.clicked.connect(self._on_launch_clicked)
        layout.addWidget(self._launch_btn)

        # Status area
        status_card = QFrame()
        status_card.setProperty("role", "card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 12, 16, 12)
        status_layout.setSpacing(6)

        status_header = QLabel("Status")
        status_header.setStyleSheet(
            f"color: {C.text_secondary}; font-size: 12px; font-weight: 600;"
            f"text-transform: uppercase; letter-spacing: 0.5px; background: transparent;"
        )
        status_layout.addWidget(status_header)

        self._status_label = QLabel("Ready.")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            f"color: {C.text_muted}; font-size: 13px; background: transparent;"
        )
        status_layout.addWidget(self._status_label)

        layout.addWidget(status_card)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    _LAUNCH_ORDER = [
        MobilePlatform.YOUTUBE, MobilePlatform.FACEBOOK,
        MobilePlatform.TIKTOK, MobilePlatform.INSTAGRAM,
    ]

    def _get_selected_platforms(self) -> list[MobilePlatform]:
        selected = {p for p, cb in self._checkboxes.items() if cb.isChecked()}
        return [p for p in self._LAUNCH_ORDER if p in selected]

    def _on_launch_clicked(self):
        platforms = self._get_selected_platforms()
        if not platforms:
            self._set_status("Select at least one platform.", "warning")
            self.log_message.emit("Select at least one platform.", "warning")
            return

        self._launch_btn.setEnabled(False)
        self._set_status("Starting...", "info")

        # TODO: Load emulator config from settings UI / persistent storage
        config = AndroidEmulatorConfig(avd_name=DEFAULT_EMULATOR_CONFIG["avd_name"])

        thread = QThread()
        worker = EmulatorWorker(config, platforms)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status_update.connect(self._on_status_update)
        worker.finished.connect(self._on_finished)
        worker.confirmation_needed.connect(self._on_confirmation_needed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_thread)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_confirmation_needed(self, platform_name: str, reason: str):
        from app.ui.continue_confirm_dialog import ContinueConfirmDialog
        dialog = ContinueConfirmDialog(platform_name=platform_name, reason=reason, parent=self)
        dialog.exec()
        should_continue = dialog.should_continue
        if self._worker is not None:
            self._worker.confirmation_received.emit(bool(should_continue))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_status_update(self, message: str, level: str):
        self._set_status(message, level)
        self.log_message.emit(message, level)

    def _on_finished(self, results: list):
        self._launch_btn.setEnabled(True)

        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        parts: list[str] = []
        if succeeded:
            names = ", ".join(r.platform.display_name for r in succeeded)
            parts.append(f"Opened: {names}")
        if failed:
            for r in failed:
                parts.append(f"Failed: {r.platform.display_name} \u2014 {r.message}")

        summary = "\n".join(parts) if parts else "No results."
        level = "success" if not failed else ("warning" if succeeded else "error")
        self._set_status(summary, level)

    def _cleanup_thread(self):
        self._thread = None
        self._worker = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str, level: str = "info"):
        color_map = {
            "info": C.text_muted,
            "success": C.success_text,
            "warning": C.warning_text,
            "error": C.danger_text,
        }
        color = color_map.get(level, C.text_muted)
        self._status_label.setText(message)
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 13px; background: transparent;"
        )
