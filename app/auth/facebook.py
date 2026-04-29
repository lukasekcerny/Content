import logging
from typing import Optional

from app.auth.base import AuthProvider, CookieCallback

logger = logging.getLogger(__name__)


class FacebookAuth(AuthProvider):

    def get_login_url(self) -> str:
        return "https://www.facebook.com/login"

    def login(self, page, email: str, password: str,
              cookie_callback: Optional[CookieCallback] = None) -> tuple[bool, str]:
        try:
            if self.is_logged_in(page):
                return True, "Already logged in to Facebook"

            page.goto(self.get_login_url(), wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            self._handle_cookies(page, cookie_callback)
            page.wait_for_timeout(1000)

            page.wait_for_selector('#email', timeout=15000)
            page.fill('#email', email)
            page.wait_for_timeout(300)

            page.fill('#pass', password)
            page.wait_for_timeout(300)

            page.click('button[name="login"]')
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(3000)

            if self.is_logged_in(page):
                return True, "Successfully logged in to Facebook"
            return False, "Login failed - check credentials"

        except Exception as e:
            logger.exception("Facebook login failed")
            return False, f"Login error: {e}"

    def is_logged_in(self, page) -> bool:
        try:
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)
            url = page.url
            if "login" in url or "checkpoint" in url:
                return False
            fb_logo = page.locator('[aria-label="Facebook"]')
            if fb_logo.count() > 0:
                return True
            return "login" not in url
        except Exception:
            return False
