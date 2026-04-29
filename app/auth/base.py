import logging
from abc import ABC, abstractmethod
from typing import Callable, Optional

logger = logging.getLogger(__name__)

COOKIE_ACCEPT_TEXTS = [
    "Allow essential and optional cookies",
    "Allow all cookies",
    "Accept all cookies",
    "Accept all",
    "Accept",
    "Allow",
    "Agree",
    "I agree",
    "Got it",
    "OK",
    "Consent",
    "Přijmout vše",
    "Přijmout",
    "Souhlasím",
    "Alle Cookies erlauben",
    "Alle akzeptieren",
]

COOKIE_ESSENTIAL_TEXTS = [
    "Decline optional cookies",
    "Only allow essential cookies",
    "Essential only",
    "Reject all",
    "Decline",
    "Odmítnout nepovinné",
    "Pouze nezbytné",
]

CookieCallback = Callable[[], str]


class AuthProvider(ABC):
    """Abstract base for platform authentication using Playwright."""

    @abstractmethod
    def login(self, page, email: str, password: str,
              cookie_callback: Optional[CookieCallback] = None) -> tuple[bool, str]:
        ...

    @abstractmethod
    def is_logged_in(self, page) -> bool:
        ...

    @abstractmethod
    def get_login_url(self) -> str:
        ...

    def _detect_cookie_banner(self, page) -> tuple[bool, Optional[str], Optional[str]]:
        """Detect cookie consent banners on the current page.

        Returns (found, accept_all_selector, essential_only_selector).
        Selectors are Playwright-compatible text selectors.
        """
        accept_sel = None
        essential_sel = None

        for text in COOKIE_ACCEPT_TEXTS:
            try:
                loc = page.get_by_role("button", name=text)
                if loc.count() > 0 and loc.first.is_visible():
                    accept_sel = text
                    break
            except Exception:
                continue

        if not accept_sel:
            try:
                result = page.evaluate("""() => {
                    const texts = %s;
                    const buttons = document.querySelectorAll('button, [role="button"], a.btn, a[class*="cookie"], div[role="button"]');
                    for (const btn of buttons) {
                        const txt = btn.textContent.trim();
                        for (const t of texts) {
                            if (txt === t || txt.includes(t)) {
                                return t;
                            }
                        }
                    }
                    return null;
                }""" % repr(COOKIE_ACCEPT_TEXTS))
                if result:
                    accept_sel = result
            except Exception:
                pass

        for text in COOKIE_ESSENTIAL_TEXTS:
            try:
                loc = page.get_by_role("button", name=text)
                if loc.count() > 0 and loc.first.is_visible():
                    essential_sel = text
                    break
            except Exception:
                continue

        found = accept_sel is not None or essential_sel is not None
        return found, accept_sel, essential_sel

    def _handle_cookies(self, page, cookie_callback: Optional[CookieCallback] = None):
        """Detect and handle cookie banners. If callback is provided, ask the user."""
        found, accept_sel, essential_sel = self._detect_cookie_banner(page)
        if not found:
            return

        choice = "all"
        if cookie_callback:
            try:
                choice = cookie_callback()
            except Exception:
                choice = "all"

        target_text = None
        if choice == "essential" and essential_sel:
            target_text = essential_sel
        elif accept_sel:
            target_text = accept_sel
        elif essential_sel:
            target_text = essential_sel

        if target_text:
            try:
                loc = page.get_by_role("button", name=target_text)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                    logger.info("Cookie banner dismissed with: %s", target_text)
                    return
            except Exception:
                pass

            try:
                page.evaluate("""(text) => {
                    const buttons = document.querySelectorAll('button, [role="button"], a.btn, div[role="button"]');
                    for (const btn of buttons) {
                        if (btn.textContent.trim().includes(text)) {
                            btn.click();
                            return;
                        }
                    }
                }""", target_text)
                logger.info("Cookie banner dismissed via JS with: %s", target_text)
            except Exception:
                logger.warning("Could not dismiss cookie banner")
