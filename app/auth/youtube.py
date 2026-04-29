import logging
from typing import Optional

from app.auth.base import AuthProvider, CookieCallback

logger = logging.getLogger(__name__)


class YouTubeAuth(AuthProvider):

    def get_login_url(self) -> str:
        return "https://accounts.google.com/"

    def login(self, page, email: str, password: str,
              cookie_callback: Optional[CookieCallback] = None) -> tuple[bool, str]:
        try:
            if self.is_logged_in(page):
                return True, "Already logged in to YouTube"

            page.goto(
                "https://accounts.google.com/ServiceLogin?continue=https://studio.youtube.com/",
                wait_until="domcontentloaded", timeout=30000,
            )
            page.wait_for_timeout(2000)

            self._handle_cookies(page, cookie_callback)
            page.wait_for_timeout(1000)

            page.wait_for_selector('input[type="email"]', timeout=15000)
            page.fill('input[type="email"]', email)
            page.wait_for_timeout(500)

            page.click('#identifierNext')
            page.wait_for_timeout(3000)

            page.wait_for_selector('input[type="password"]', state="visible", timeout=15000)
            page.fill('input[type="password"]', password)
            page.wait_for_timeout(500)

            page.click('#passwordNext')
            page.wait_for_load_state("networkidle", timeout=20000)
            page.wait_for_timeout(4000)

            if self.is_logged_in(page):
                return True, "Successfully logged in to YouTube"
            return False, "Login failed - check credentials"

        except Exception as e:
            logger.exception("YouTube login failed")
            return False, f"Login error: {e}"

    def is_logged_in(self, page) -> bool:
        try:
            page.goto("https://studio.youtube.com/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)
            url = page.url
            if "accounts.google.com" in url:
                return False
            if "studio.youtube.com" in url:
                return True
            return False
        except Exception:
            return False
