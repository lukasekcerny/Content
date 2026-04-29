import logging
from typing import Optional

from app.auth.base import AuthProvider, CookieCallback

logger = logging.getLogger(__name__)


class InstagramAuth(AuthProvider):

    def get_login_url(self) -> str:
        return "https://www.instagram.com/accounts/login/"

    def login(self, page, email: str, password: str,
              cookie_callback: Optional[CookieCallback] = None) -> tuple[bool, str]:
        try:
            if self.is_logged_in(page):
                return True, "Already logged in to Instagram"

            page.goto(self.get_login_url(), wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            self._handle_cookies(page, cookie_callback)
            page.wait_for_timeout(1000)

            page.wait_for_selector('input[name="username"]', timeout=15000)
            page.fill('input[name="username"]', email)
            page.wait_for_timeout(300)

            page.fill('input[name="password"]', password)
            page.wait_for_timeout(300)

            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(3000)

            for _ in range(3):
                try:
                    not_now = page.locator('button:has-text("Not Now"), button:has-text("Not now")')
                    if not_now.count() > 0 and not_now.first.is_visible():
                        not_now.first.click()
                        page.wait_for_timeout(1500)
                except Exception:
                    break

            if self.is_logged_in(page):
                return True, "Successfully logged in to Instagram"
            return False, "Login failed - check credentials"

        except Exception as e:
            logger.exception("Instagram login failed")
            return False, f"Login error: {e}"

    def is_logged_in(self, page) -> bool:
        try:
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)
            url = page.url
            if "login" in url or "accounts/login" in url:
                return False
            home = page.locator('svg[aria-label="Home"], a[href="/direct/inbox/"]')
            if home.count() > 0:
                return True
            return "accounts/login" not in url
        except Exception:
            return False
