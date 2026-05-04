import logging
from typing import Callable, Optional

from PySide6.QtCore import QThread, QObject, Signal

from app.db.database import Database
from app.db.models import Post

logger = logging.getLogger(__name__)


ProgressCallback = Callable[[int, str, str], None]
DoneCallback = Callable[[bool, str], None]


class UploadWorker(QObject):
    """Runs an upload in a background thread (API-first, browser fallback)."""

    progress = Signal(int, str, str)
    done = Signal(bool, str)

    def __init__(self, db: Database, data_dir: str, post_id: int):
        super().__init__()
        self.db = db
        self.data_dir = data_dir
        self.post_id = post_id

    def run(self):
        post = self._get_post()
        if not post:
            logger.error("UploadWorker: post_id=%d not found", self.post_id)
            self.done.emit(False, "Post not found")
            return

        content = self.db.get_content(post.content_id)
        if not content:
            logger.error("UploadWorker: content_id=%d not found for post_id=%d", post.content_id, self.post_id)
            self.done.emit(False, "Content not found")
            return

        logger.info("UploadWorker: starting upload post_id=%d platform=%s type=%s",
                    self.post_id, post.platform_id, post.content_type)
        self.db.update_post_status(self.post_id, "uploading")
        self.progress.emit(5, "upload", "Starting upload...")

        metadata = {
            "caption": post.caption,
            "title": post.title,
            "description": post.description,
            "tags": post.tags,
            "content_type": post.content_type,
        }

        api_uploader = self._get_api_uploader(post.platform_id)
        if api_uploader:
            success, msg = api_uploader.upload(
                content.file_path, metadata,
                progress_callback=self._on_progress,
            )
            if success:
                logger.info("UploadWorker: API upload succeeded post_id=%d platform=%s", self.post_id, post.platform_id)
                self.db.update_post_status(self.post_id, "published")
                self.done.emit(True, msg)
                return

            logger.warning("API upload failed for %s: %s. Falling back to browser.", post.platform_id, msg)
            self.progress.emit(10, "upload", "API failed, trying browser...")

        success, msg = self._browser_upload(post.platform_id, content.file_path, metadata)
        if success:
            logger.info("UploadWorker: browser upload succeeded post_id=%d platform=%s", self.post_id, post.platform_id)
            self.db.update_post_status(self.post_id, "published")
            self.done.emit(True, msg)
        else:
            logger.error("UploadWorker: upload failed post_id=%d platform=%s: %s", self.post_id, post.platform_id, msg)
            self.db.update_post_status(self.post_id, "failed", msg)
            self.done.emit(False, msg)

    def _on_progress(self, value: int, phase: str, status: str):
        self.progress.emit(value, phase, status)

    def _browser_upload(self, platform_id: str, file_path: str, metadata: dict) -> tuple[bool, str]:
        try:
            from app.browser.base import get_browser_action
            from app.browser.manager import BrowserManager

            bm = BrowserManager.get_instance()

            def _do_upload(bt):
                page = bt.get_page(platform_id)
                action = get_browser_action(platform_id)
                return action.upload_content(page, file_path, metadata,
                                             progress_callback=self._on_progress)

            return bm.execute(_do_upload, timeout=180)
        except Exception as e:
            logger.exception("Browser upload failed for %s", platform_id)
            return False, str(e)

    def _get_api_uploader(self, platform_id: str):
        try:
            if platform_id == "tiktok":
                from app.upload.tiktok import TikTokUploader
                return TikTokUploader(self.data_dir)
            elif platform_id == "instagram":
                from app.upload.instagram import InstagramUploader
                return InstagramUploader(self.data_dir)
            elif platform_id == "facebook":
                from app.upload.facebook import FacebookUploader
                return FacebookUploader(self.data_dir)
            elif platform_id == "youtube":
                from app.upload.youtube import YouTubeUploader
                return YouTubeUploader(self.data_dir)
        except ImportError:
            pass
        return None

    def _get_post(self) -> Optional[Post]:
        rows = self.db._conn.execute(
            "SELECT * FROM posts WHERE id = ?", (self.post_id,)
        ).fetchone()
        return Post(**dict(rows)) if rows else None


_active_threads: list[QThread] = []
_active_workers: list[UploadWorker] = []


def start_upload(db: Database, data_dir: str, post_id: int,
                 progress_callback: ProgressCallback = None,
                 done_callback: DoneCallback = None):
    thread = QThread()
    worker = UploadWorker(db, data_dir, post_id)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)

    if progress_callback:
        worker.progress.connect(lambda v, p, s: progress_callback(v, p, s))
    if done_callback:
        worker.done.connect(lambda success, msg: done_callback(success, msg))

    worker.done.connect(thread.quit)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda: _active_threads.remove(thread) if thread in _active_threads else None)
    thread.finished.connect(lambda: _active_workers.remove(worker) if worker in _active_workers else None)

    _active_threads.append(thread)
    _active_workers.append(worker)
    thread.start()
