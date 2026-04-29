import logging
from typing import Optional

from app.auth.base import AuthProvider, CookieCallback

logger = logging.getLogger(__name__)


class TikTokAuth(AuthProvider):

    def get_login_url(self) -> str:
        return "https://www.tiktok.com/login/phone-or-email/email"

    def login(self, page, email: str, password: str,
              cookie_callback: Optional[CookieCallback] = None) -> tuple[bool, str]:
        try:
            if self.is_logged_in(page):
                return True, "Already logged in to TikTok"

            page.goto(self.get_login_url(), wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            self._handle_cookies(page, cookie_callback)
            page.wait_for_timeout(1000)

            page.wait_for_selector('input[name="username"], input[type="text"]', timeout=15000)
            username_input = page.locator('input[name="username"], input[type="text"]').first
            username_input.fill(email)
            page.wait_for_timeout(500)

            page.fill('input[type="password"]', password)
            page.wait_for_timeout(500)

            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(3000)

            if self.is_logged_in(page):
                return True, "Successfully logged in to TikTok"
            return False, "Login failed - check credentials or CAPTCHA triggered"

        except Exception as e:
            logger.exception("TikTok login failed")
            return False, f"Login error: {e}"

    def is_logged_in(self, page) -> bool:
        try:
            page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)
            url = page.url
            content = page.content().lower()
            if "login" not in url and ("profile" in content or "upload" in content):
                return True
            return False
        except Exception:
            return False
