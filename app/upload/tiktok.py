import logging

from app.auth.token_store import get_api_token

logger = logging.getLogger(__name__)


class TikTokUploader:
    """TikTok API uploader. Falls back to browser if no API token available."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def upload(self, file_path: str, metadata: dict,
               progress_callback=None) -> tuple[bool, str]:
        access_token = get_api_token("tiktok", "access_token")
        if not access_token:
            return False, "No TikTok API token - will use browser"

        # API implementation would go here using httpx
        # For now, signal that API is not configured so browser fallback activates
        return False, "TikTok API upload not yet implemented - using browser fallback"
