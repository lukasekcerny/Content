import logging
from typing import Optional, Callable

from app.auth.token_store import get_credentials
from app.auth.base import CookieCallback

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages browser sessions for all platforms using BrowserManager."""

    def __init__(self, browser_manager):
        self._bm = browser_manager

    def login_platform(self, platform_id: str, email: str, password: str,
                       cookie_callback: Optional[CookieCallback] = None) -> tuple[bool, str]:
        logger.info("SessionManager: starting login for platform=%s", platform_id)
        try:
            def _do_login(bt):
                page = bt.get_page(platform_id)
                auth = self._get_auth_provider(platform_id)
                return auth.login(page, email, password, cookie_callback=cookie_callback)

            result = self._bm.execute(_do_login, timeout=120)
            if result[0]:
                logger.info("SessionManager: login succeeded for platform=%s", platform_id)
            else:
                logger.warning("SessionManager: login returned failure for platform=%s: %s", platform_id, result[1])
            return result
        except Exception as e:
            logger.exception("Login failed for %s", platform_id)
            return False, str(e)

    def check_session(self, platform_id: str) -> bool:
        try:
            def _do_check(bt):
                page = bt.get_page(platform_id)
                auth = self._get_auth_provider(platform_id)
                return auth.is_logged_in(page)

            return self._bm.execute(_do_check, timeout=60)
        except Exception as e:
            logger.warning("Session check failed for %s: %s", platform_id, e)
            return False

    def auto_reconnect(self, platform_id: str,
                       cookie_callback: Optional[CookieCallback] = None) -> tuple[bool, str]:
        email, password = get_credentials(platform_id)
        if not email or not password:
            return False, "No stored credentials"
        return self.login_platform(platform_id, email, password, cookie_callback=cookie_callback)

    def _get_auth_provider(self, platform_id: str):
        from app.auth.tiktok import TikTokAuth
        from app.auth.instagram import InstagramAuth
        from app.auth.facebook import FacebookAuth
        from app.auth.youtube import YouTubeAuth

        providers = {
            "tiktok": TikTokAuth,
            "instagram": InstagramAuth,
            "facebook": FacebookAuth,
            "youtube": YouTubeAuth,
        }
        cls = providers.get(platform_id)
        if not cls:
            raise ValueError(f"Unknown platform: {platform_id}")
        return cls()
