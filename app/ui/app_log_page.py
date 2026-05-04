from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
)
from PySide6.QtCore import Signal, Qt

from app.constants import COLORS as C


class AppLogPage(QWidget):
    """Page showing the persistent application log file with a clear button."""

    back_clicked = Signal()
    log_message = Signal(str, str)

    def __init__(self, data_dir: str, parent=None):
        super().__init__(parent)
        self._log_path = os.path.join(data_dir, "app.log")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

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

        title = QLabel("Application Log")
        title.setStyleSheet(
            f"color: {C.text_primary}; font-size: 20px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(title)

        path_label = QLabel(f"File: {self._log_path}")
        path_label.setStyleSheet(
            f"color: {C.text_muted}; font-size: 11px; background: transparent;"
        )
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(32)
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)

        clear_btn = QPushButton("Clear log")
        clear_btn.setProperty("role", "danger")
        clear_btn.setFixedHeight(32)
        clear_btn.clicked.connect(self._clear_log)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._text_area = QPlainTextEdit()
        self._text_area.setReadOnly(True)
        self._text_area.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {C.bg_shell}; color: {C.text_muted};"
            f"border: 1px solid {C.border_soft}; border-radius: 8px;"
            f"font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 11px;"
            f"padding: 12px; }}"
        )
        layout.addWidget(self._text_area, 1)

    def refresh(self):
        if os.path.isfile(self._log_path):
            try:
                with open(self._log_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self._text_area.setPlainText(content)
                self._text_area.verticalScrollBar().setValue(
                    self._text_area.verticalScrollBar().maximum()
                )
            except Exception as e:
                self._text_area.setPlainText(f"Error reading log: {e}")
        else:
            self._text_area.setPlainText("(Log file does not exist yet.)")

    def _clear_log(self):
        try:
            with open(self._log_path, "w", encoding="utf-8") as f:
                f.write("")
            self._text_area.setPlainText("")
            self.log_message.emit("Log file cleared.", "info")
        except Exception as e:
            self.log_message.emit(f"Failed to clear log: {e}", "error")
