from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BrowserAction(ABC):
    """Abstract base for per-platform browser automation actions (Playwright)."""

    @abstractmethod
    def change_profile_picture(self, page, image_path: str, caption: str = ""):
        ...

    @abstractmethod
    def upload_content(self, page, file_path: str, metadata: dict,
                       progress_callback=None) -> tuple[bool, str]:
        ...


def get_browser_action(platform_id: str) -> BrowserAction:
    from app.browser.tiktok import TikTokBrowser
    from app.browser.instagram import InstagramBrowser
    from app.browser.facebook import FacebookBrowser
    from app.browser.youtube import YouTubeBrowser

    actions = {
        "tiktok": TikTokBrowser,
        "instagram": InstagramBrowser,
        "facebook": FacebookBrowser,
        "youtube": YouTubeBrowser,
    }
    cls = actions.get(platform_id)
    if not cls:
        raise ValueError(f"Unknown platform: {platform_id}")
    return cls()
