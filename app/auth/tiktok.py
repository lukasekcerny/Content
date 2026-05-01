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
            if "login" in url or "/signup" in url:
                return False

            # A visible "Log in" link/button is a strong signal that the user is NOT logged in.
            for selector in (
                'a[href*="/login"]',
                'button:has-text("Log in")',
                'a:has-text("Log in")',
            ):
                try:
                    loc = page.locator(selector)
                    if loc.count() > 0 and loc.first.is_visible():
                        return False
                except Exception:
                    continue

            # An avatar / profile link present means the user IS logged in.
            for selector in (
                '[data-e2e="nav-profile"]',
                '[data-e2e="profile-icon"]',
                'a[href^="/@"]',
            ):
                try:
                    loc = page.locator(selector)
                    if loc.count() > 0 and loc.first.is_visible():
                        return True
                except Exception:
                    continue

            return False
        except Exception:
            return False
