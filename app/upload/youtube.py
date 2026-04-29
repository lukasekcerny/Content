import logging

from app.auth.token_store import get_api_token

logger = logging.getLogger(__name__)


class YouTubeUploader:
    """YouTube API uploader via Data API v3."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def upload(self, file_path: str, metadata: dict,
               progress_callback=None) -> tuple[bool, str]:
        access_token = get_api_token("youtube", "access_token")
        if not access_token:
            return False, "No YouTube API token - will use browser"

        return False, "YouTube API upload not yet implemented - using browser fallback"
