import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton, QCheckBox, QSizePolicy,
)
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtCore import Qt, Signal

from app.constants import COLORS as C, PLATFORMS, CONTENT_TYPES
from app.db.database import Database
from app.db.models import Post
from app.ui.components.button import PrimaryButton, GhostButton
from app.ui.components.input_field import InputField, TextArea
from app.ui.components.progress_bar import PlatformProgressRow
from app.ui.components.badge import Badge


class PlatformTargetWidget(QFrame):
    """A single platform+content_type target with checkbox, caption fields, progress."""

    def __init__(self, platform_id: str, platform_name: str, content_type: dict, parent=None):
        super().__init__(parent)
        self.platform_id = platform_id
        self.content_type_info = content_type
        self.setProperty("role", "card")
        self.setStyleSheet(
            f"PlatformTargetWidget {{ background-color: {C.bg_card};"
            f"border: 1px solid {C.border_soft}; border-radius: 12px; padding: 12px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        label_text = f"{platform_name} > {content_type['label']}"
        self._checkbox = QCheckBox(label_text)
        self._checkbox.setStyleSheet(f"QCheckBox {{ color: {C.text_primary}; font-weight: 500; font-size: 13px; background: transparent; }}")
        self._checkbox.setToolTip(label_text)
        header.addWidget(self._checkbox, 1)
        header.addStretch()
        layout.addLayout(header)

        self._fields_container = QVBoxLayout()
        self._fields_container.setSpacing(6)

        self._caption_field = InputField(f"Caption (max {content_type.get('caption_max', 'N/A')} chars)")
        self._fields_container.addWidget(self._caption_field)

        self._extra_fields = {}
        if content_type.get("extra_fields"):
            for field_name in content_type["extra_fields"]:
                f = InputField(field_name.capitalize())
                self._extra_fields[field_name] = f
                self._fields_container.addWidget(f)

        if platform_id == "youtube":
            self._title_field = InputField("Title")
            self._desc_field = InputField("Description")
            self._tags_field = InputField("Tags (comma-separated)")
            self._fields_container.addWidget(self._title_field)
            self._fields_container.addWidget(self._desc_field)
            self._fields_container.addWidget(self._tags_field)
        else:
            self._title_field = None
            self._desc_field = None
            self._tags_field = None

        layout.addLayout(self._fields_container)

        self._progress = PlatformProgressRow(platform_name, large=True)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._checkbox.toggled.connect(self._on_toggled)
        self._on_toggled(False)

    def _on_toggled(self, checked: bool):
        for i in range(self._fields_container.count()):
            w = self._fields_container.itemAt(i).widget()
            if w:
                w.setVisible(checked)

    def is_checked(self) -> bool:
        return self._checkbox.isChecked()

    def set_checked(self, checked: bool):
        self._checkbox.setChecked(checked)

    def get_post_data(self) -> dict:
        data = {
            "platform_id": self.platform_id,
            "content_type": self.content_type_info["type"],
            "caption": self._caption_field.text(),
        }
        if self._title_field:
            data["title"] = self._title_field.text()
        if self._desc_field:
            data["description"] = self._desc_field.text()
        if self._tags_field:
            data["tags"] = self._tags_field.text()
        return data

    def load_post(self, post: Post):
        self._checkbox.setChecked(True)
        self._caption_field.setText(post.caption or "")
        if self._title_field:
            self._title_field.setText(post.title or "")
        if self._desc_field:
            self._desc_field.setText(post.description or "")
        if self._tags_field:
            self._tags_field.setText(post.tags or "")

    @property
    def progress_row(self) -> PlatformProgressRow:
        return self._progress

    def show_progress(self):
        self._progress.show()


class ContentDetailPage(QWidget):
    """Detail page for a single content item: preview, metadata, per-platform targets."""

    back_clicked = Signal()
    log_message = Signal(str, str)

    def __init__(self, db: Database, data_dir: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.data_dir = data_dir
        self._content_id = None
        self._target_widgets: list[PlatformTargetWidget] = []
        self._current_pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        top = QHBoxLayout()
        back_btn = GhostButton("<  Back")
        back_btn.clicked.connect(self.back_clicked.emit)
        top.addWidget(back_btn)
        top.addStretch()
        layout.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scroll_content = QWidget()
        self._main_layout = QHBoxLayout(self._scroll_content)
        self._main_layout.setSpacing(24)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._preview_col = QVBoxLayout()
        self._preview_col.setSpacing(12)

        self._preview_label = QLabel()
        self._preview_label.setMinimumSize(200, 200)
        self._preview_label.setMaximumSize(400, 400)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            f"background-color: {C.bg_input}; border-radius: 12px; border: 1px solid {C.border_soft};"
        )
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._filename_label = QLabel()
        self._filename_label.setStyleSheet(f"color: {C.text_primary}; font-size: 14px; font-weight: 500; background: transparent;")
        self._filename_label.setWordWrap(True)

        self._meta_label = QLabel()
        self._meta_label.setProperty("role", "muted")
        self._meta_label.setStyleSheet(f"color: {C.text_muted}; font-size: 12px; background: transparent;")
        self._meta_label.setWordWrap(True)

        self._title_input = InputField("Title (internal)")
        self._desc_input = InputField("Description (internal)")

        self._preview_col.addWidget(self._preview_label)
        self._preview_col.addWidget(self._filename_label)
        self._preview_col.addWidget(self._meta_label)
        self._preview_col.addWidget(QLabel("Title:"))
        self._preview_col.addWidget(self._title_input)
        self._preview_col.addWidget(QLabel("Description:"))
        self._preview_col.addWidget(self._desc_input)
        self._preview_col.addStretch()

        self._targets_col = QVBoxLayout()
        self._targets_col.setSpacing(12)

        targets_header = QLabel("Publish To")
        targets_header.setProperty("role", "heading")
        targets_header.setStyleSheet(f"color: {C.text_primary}; font-size: 14px; font-weight: 600; background: transparent;")
        self._targets_col.addWidget(targets_header)

        self._targets_container = QVBoxLayout()
        self._targets_container.setSpacing(8)
        self._targets_col.addLayout(self._targets_container)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._post_btn = PrimaryButton("Post Now")
        self._post_btn.clicked.connect(self._on_post_now)

        self._schedule_btn = QPushButton("Schedule")
        self._schedule_btn.clicked.connect(self._on_schedule)

        btn_row.addWidget(self._post_btn)
        btn_row.addWidget(self._schedule_btn)
        btn_row.addStretch()
        self._targets_col.addLayout(btn_row)
        self._targets_col.addStretch()

        self._left_widget = QWidget()
        self._left_widget.setLayout(self._preview_col)
        self._left_widget.setMinimumWidth(260)
        self._left_widget.setMaximumWidth(440)
        self._left_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        right_widget = QWidget()
        right_widget.setLayout(self._targets_col)

        self._main_layout.addWidget(self._left_widget)
        self._main_layout.addWidget(right_widget, 1)

        scroll.setWidget(self._scroll_content)
        layout.addWidget(scroll, 1)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._scale_preview()

    def _scale_preview(self):
        if self._current_pixmap and not self._current_pixmap.isNull():
            w = min(self._preview_label.width(), 400)
            h = min(self._preview_label.height(), 400)
            if w > 10 and h > 10:
                scaled = self._current_pixmap.scaled(
                    w, h, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._preview_label.setPixmap(scaled)

    def load_content(self, content_id: int):
        self._content_id = content_id
        content = self.db.get_content(content_id)
        if not content:
            return

        self._filename_label.setText(content.file_name)
        self._title_input.setText(content.title or "")
        self._desc_input.setText(content.description or "")

        meta_parts = []
        if content.mime_type:
            meta_parts.append(content.mime_type)
        if content.file_size:
            size_mb = content.file_size / (1024 * 1024)
            meta_parts.append(f"{size_mb:.1f} MB")
        if content.width and content.height:
            meta_parts.append(f"{content.width}x{content.height}")
        if content.duration_seconds:
            meta_parts.append(f"{content.duration_seconds:.1f}s")
        self._meta_label.setText("  |  ".join(meta_parts))

        if content.thumbnail_path and os.path.isfile(content.thumbnail_path):
            self._current_pixmap = QPixmap(content.thumbnail_path)
            self._scale_preview()
        else:
            self._current_pixmap = None
            self._preview_label.setText(content.file_name)

        self._build_targets(content)

    def _build_targets(self, content):
        for w in self._target_widgets:
            w.deleteLater()
        self._target_widgets.clear()

        from app.upload.validator import get_compatible_targets
        compatible = get_compatible_targets(content)

        platforms = self.db.get_platforms()
        connected_ids = {p.id for p in platforms if p.connected}

        existing_posts = {
            (p.platform_id, p.content_type): p
            for p in self.db.get_posts_for_content(content.id)
        }

        for platform_id, ct in compatible:
            if platform_id not in connected_ids:
                continue
            pname = PLATFORMS[platform_id]["display_name"]
            widget = PlatformTargetWidget(platform_id, pname, ct)

            existing = existing_posts.get((platform_id, ct["type"]))
            if existing:
                widget.load_post(existing)

            self._target_widgets.append(widget)
            self._targets_container.addWidget(widget)

        if not self._target_widgets:
            no_targets = QLabel("No compatible platforms connected. Connect a platform first.")
            no_targets.setStyleSheet(f"color: {C.text_disabled}; font-size: 13px; padding: 20px; background: transparent;")
            no_targets.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_targets.setWordWrap(True)
            self._targets_container.addWidget(no_targets)
            self._target_widgets.append(no_targets)

    def _on_post_now(self):
        if not self._content_id:
            return
        content = self.db.get_content(self._content_id)
        if content:
            content.title = self._title_input.text()
            content.description = self._desc_input.text()
            self.db.update_content(content)

        for tw in self._target_widgets:
            if not isinstance(tw, PlatformTargetWidget) or not tw.is_checked():
                continue
            data = tw.get_post_data()
            post = Post(
                content_id=self._content_id,
                platform_id=data["platform_id"],
                content_type=data["content_type"],
                status="uploading",
                caption=data.get("caption", ""),
                title=data.get("title", ""),
                description=data.get("description", ""),
                tags=data.get("tags", ""),
            )
            post_id = self.db.add_post(post)
            tw.show_progress()
            tw.progress_row.set_progress(10, "upload", "Starting...")
            self.log_message.emit(
                f"Uploading to {data['platform_id']} ({data['content_type']})...", "info"
            )
            self._start_upload(post_id, tw)

    def _start_upload(self, post_id: int, target_widget: PlatformTargetWidget):
        from app.upload.base import start_upload
        start_upload(
            db=self.db,
            data_dir=self.data_dir,
            post_id=post_id,
            progress_callback=lambda v, phase, status: target_widget.progress_row.set_progress(v, phase, status),
            done_callback=lambda success, msg: self._on_upload_done(post_id, target_widget, success, msg),
        )

    def _on_upload_done(self, post_id: int, tw: PlatformTargetWidget, success: bool, msg: str):
        if success:
            tw.progress_row.set_done()
            self.log_message.emit(msg, "success")
        else:
            tw.progress_row.set_error(msg)
            self.log_message.emit(msg, "error")

    def _on_schedule(self):
        self.log_message.emit("Scheduling is not yet configured. Use Post Now.", "warning")
