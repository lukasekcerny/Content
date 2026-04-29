import logging
from datetime import datetime

from apscheduler.schedulers.qt import QtScheduler
from apscheduler.triggers.date import DateTrigger

from app.db.database import Database

logger = logging.getLogger(__name__)


class PostScheduler:
    """APScheduler integration for scheduled posting."""

    def __init__(self, db: Database, data_dir: str):
        self.db = db
        self.data_dir = data_dir
        self._scheduler = QtScheduler()
        self._scheduler.start()
        self._on_post_callback = None
        self._restore_scheduled_posts()

    def set_post_callback(self, callback):
        self._on_post_callback = callback

    def schedule_post(self, post_id: int, scheduled_at: datetime):
        job_id = f"post_{post_id}"

        self._scheduler.add_job(
            self._execute_post,
            trigger=DateTrigger(run_date=scheduled_at),
            id=job_id,
            args=[post_id],
            replace_existing=True,
        )
        logger.info(f"Scheduled post {post_id} for {scheduled_at}")

    def cancel_post(self, post_id: int):
        job_id = f"post_{post_id}"
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Cancelled scheduled post {post_id}")
        except Exception:
            pass

    def _execute_post(self, post_id: int):
        logger.info(f"Executing scheduled post {post_id}")
        if self._on_post_callback:
            self._on_post_callback(post_id)
        else:
            from app.upload.base import start_upload
            start_upload(
                db=self.db,
                data_dir=self.data_dir,
                post_id=post_id,
            )

    def _restore_scheduled_posts(self):
        posts = self.db.get_scheduled_posts()
        now = datetime.now()
        for post in posts:
            if post.scheduled_at:
                try:
                    dt = datetime.fromisoformat(post.scheduled_at)
                    if dt > now:
                        self.schedule_post(post.id, dt)
                    else:
                        self._execute_post(post.id)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid scheduled_at for post {post.id}: {post.scheduled_at}")

    def shutdown(self):
        self._scheduler.shutdown(wait=False)
