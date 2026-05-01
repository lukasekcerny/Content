"""TikTok authentication via the "Continue with Google" flow.

Why Google instead of TikTok's own email/password form?
The TikTok web login is a very heavily protected endpoint (CAPTCHA, slider
puzzles, fingerprint checks). Going through Google OAuth is far more
reliable for an automated session because Google's flow is much more
forgiving as long as the browser looks like a real user. Most TikTok
accounts created through "Continue with Google" stay accessible this way.

The flow this provider drives is:

  1. open ``https://www.tiktok.com/explore`` (visible browser),
  2. dismiss the cookie banner if any,
  3. click the top "Log in" button (``#header-login-button``),
  4. click "Continue with Google" in the resulting modal,
  5. on the Google popup: type the email -> Next -> type the password -> Next,
  6. if the OAuth consent screen "Pokračovat / Continue" appears, click it,
  7. wait ~15 s for the redirect back to TikTok to settle,
  8. screenshot the resulting TikTok page (and try to open it for the user),
  9. close the browser window.

Every "find this element" step uses Playwright's ``Locator.wait_for`` with a
generous timeout (``LONG_WAIT_MS``) so a slow network or a slow render does
not abort the flow prematurely; only when the element really does not show
up at all does the step fail.
"""

import logging
import os
import time
from datetime import datetime
from typing import Iterable, Optional

from app.auth.base import AuthProvider, CookieCallback
from app.browser.human import (
    fill_field_humanly,
    human_click,
    page_pause,
)

logger = logging.getLogger(__name__)


SCREENSHOT_DIR = os.path.join(
    os.path.expanduser("~"), ".content-uploader", "screenshots",
)


# All "wait until the user can see this element" steps use this timeout.
# Playwright's ``Locator.wait_for`` polls until either the element shows up
# in the requested state or this timeout elapses, so 60 s gives slow pages
# plenty of time without hanging forever.
LONG_WAIT_MS = 60_000

# How long the post-login redirect back to TikTok is allowed to take.
POST_LOGIN_WAIT_S = 15


class TikTokAuth(AuthProvider):
    """Drive the TikTok login through Google OAuth, like a real user."""

    def get_login_url(self) -> str:
        return "https://www.tiktok.com/explore"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def login(self, page, email: str, password: str,
              cookie_callback: Optional[CookieCallback] = None) -> tuple[bool, str]:
        screenshot_path = ""
        try:
            self._log_step("bringing browser to front")
            try:
                page.bring_to_front()
            except Exception:
                pass

            self._log_step("navigating to https://www.tiktok.com/explore")
            page.goto(
                "https://www.tiktok.com/explore",
                wait_until="domcontentloaded", timeout=LONG_WAIT_MS,
            )
            try:
                page.wait_for_load_state("load", timeout=20000)
            except Exception:
                logger.debug("'load' state did not finish, continuing", exc_info=True)
            page_pause(page, 1800, 3200)

            self._log_step("handling cookie banner if present")
            try:
                self._handle_cookies(page, cookie_callback)
            except Exception:
                logger.warning("Cookie handling raised; continuing", exc_info=True)
            page_pause(page, 700, 1500)

            # Try to click the Log in button. We do not pre-check "are we
            # already signed in?" because TikTok's logged-out HTML contains
            # several selectors that look like logged-in indicators (sidebar
            # Profile icon etc.) and any heuristic gives false positives.
            # Instead we just attempt the click with a generous timeout; if
            # the button truly is not there, the click raises and we fall
            # back to verifying via is_logged_in().
            self._log_step("waiting for and clicking the TikTok 'Log in' button")
            login_clicked = False
            try:
                self._click_tiktok_login_button(page)
                login_clicked = True
                self._log_step("'Log in' button clicked")
            except Exception as click_err:
                self._log_step(f"could not click 'Log in': {click_err}")
                if self.is_logged_in(page):
                    self._log_step("user is already signed in - skipping login form")
                    screenshot_path = self._save_screenshot(page)
                    self._open_screenshot(screenshot_path)
                    self._close_browser(page)
                    return True, self._with_screenshot(
                        "Already signed in to TikTok.", screenshot_path,
                    )
                raise

            assert login_clicked
            page_pause(page, 1300, 2400)

            self._log_step("waiting for the 'Continue with Google' button")
            google_page = self._click_continue_with_google(page)

            self._log_step("waiting for Google email field")
            self._enter_google_credentials(google_page, email, password)

            self._log_step("waiting for OAuth consent ('Pokracovat'/'Continue') if shown")
            self._maybe_click_oauth_consent(google_page)

            self._log_step(f"waiting {POST_LOGIN_WAIT_S}s for TikTok redirect")
            self._wait_for_post_login(page, google_page, seconds=POST_LOGIN_WAIT_S)

            self._log_step("taking screenshot of the TikTok page")
            screenshot_path = self._save_screenshot(page)
            self._open_screenshot(screenshot_path)

            self._log_step("verifying TikTok session")
            success = self.is_logged_in(page)

            self._log_step("closing the TikTok browser window")
            self._close_browser(page)

            if success:
                return True, self._with_screenshot(
                    "Logged in to TikTok via Google.", screenshot_path,
                )
            return False, self._with_screenshot(
                "Login flow finished but TikTok session was not detected. "
                "If 2FA / CAPTCHA was shown, retry and complete it manually.",
                screenshot_path,
            )
        except Exception as e:
            err_str = str(e)
            page_was_closed = (
                "Target page, context or browser has been closed" in err_str
                or "Target closed" in err_str
            )
            if page_was_closed:
                clean_msg = (
                    "Browser window was closed before the login could finish. "
                    "Click Connect again to retry."
                )
                logger.warning(
                    "TikTok login aborted: browser closed during step '%s'",
                    self._last_step,
                )
            else:
                clean_msg = f"Login error during step '{self._last_step}': {e}"
                logger.exception(
                    "TikTok Google login failed at step: %s", self._last_step,
                )

            if not page_was_closed:
                try:
                    screenshot_path = screenshot_path or self._save_screenshot(page)
                    self._open_screenshot(screenshot_path)
                except Exception:
                    pass
            try:
                self._close_browser(page)
            except Exception:
                pass
            return False, self._with_screenshot(clean_msg, screenshot_path)

    def is_logged_in(self, page) -> bool:
        try:
            if self._is_page_dead(page):
                return False

            try:
                current_url = page.url
            except Exception:
                current_url = ""

            if (
                not current_url
                or "accounts.google.com" in current_url
                or "/login" in current_url
                or "/signup" in current_url
            ):
                page.goto(
                    "https://www.tiktok.com",
                    wait_until="domcontentloaded", timeout=LONG_WAIT_MS,
                )
                page.wait_for_timeout(2500)

            url = page.url
            if "/login" in url or "/signup" in url:
                return False

            # Use Playwright's :visible pseudo so we ignore the duplicate-but-hidden
            # copies of the Log in button that TikTok ships in the markup.
            for selector in (
                'a[href*="/login"]:visible',
                'button:has-text("Log in"):visible',
                'a:has-text("Log in"):visible',
                "#header-login-button:visible",
            ):
                try:
                    if page.locator(selector).count() > 0:
                        return False
                except Exception:
                    continue

            for selector in (
                '[data-e2e="profile-username"]:visible',
                'a[href^="/@"]:visible',
                'header [class*="DivHeaderRightContainer"] img:visible',
            ):
                try:
                    if page.locator(selector).count() > 0:
                        return True
                except Exception:
                    continue

            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    _last_step: str = "(idle)"

    def _log_step(self, msg: str) -> None:
        self._last_step = msg
        logger.info("[tiktok-login] %s", msg)

    def _wait_for_first_visible(
        self, page, selectors: Iterable[str], timeout_ms: int = LONG_WAIT_MS,
    ):
        """Race a list of selectors and return the first one that becomes visible.

        Each individual ``wait_for`` only gets a slice of the total budget so
        we keep coming back and checking the other selectors too; in
        aggregate we still cover the full ``timeout_ms`` window.
        """
        sel_list = list(selectors)
        if not sel_list:
            raise ValueError("_wait_for_first_visible needs at least one selector")
        deadline = time.time() + timeout_ms / 1000.0
        last_error: Optional[Exception] = None
        slice_ms = max(1500, int(timeout_ms / len(sel_list) / 2))
        while time.time() < deadline:
            for sel in sel_list:
                if time.time() >= deadline:
                    break
                try:
                    loc = page.locator(sel).first
                    loc.wait_for(state="visible", timeout=slice_ms)
                    return loc
                except Exception as e:
                    last_error = e
                    continue
        if last_error is not None:
            raise last_error
        raise TimeoutError(f"None of the selectors became visible: {sel_list}")

    def _click_tiktok_login_button(self, page) -> None:
        """Wait for the TikTok "Log in" button and click it.

        TikTok renders TWO elements with ``id="header-login-button"`` -- the
        small one in the top-right header and the big one in the left sidebar
        ``SubMainNavContentContainer``. Playwright's ``.first`` /
        ``wait_for_selector`` both pick the *DOM-first* element, which on the
        explore page is the hidden one (its container is collapsed until you
        hover the sidebar). We therefore filter at the selector level with
        Playwright's ``:visible`` pseudo-class and, as a defensive fallback,
        iterate ``locator(...).all()`` and pick whichever match is actually
        visible.
        """
        # Selectors that Playwright filters down to only the visible matches.
        visible_selectors = (
            "#header-login-button:visible",
            'button#header-login-button:visible',
            'button:has-text("Log in"):visible',
            '[role="button"]:has-text("Log in"):visible',
        )

        login_btn = None
        last_err: Optional[Exception] = None
        for sel in visible_selectors:
            try:
                self._log_step(f"waiting for visible match of: {sel}")
                page.wait_for_selector(sel, timeout=15000)
                login_btn = page.locator(sel).first
                self._log_step(f"found Log in button via: {sel}")
                break
            except Exception as e:
                last_err = e
                self._log_step(f"selector '{sel}' did not match: {e}")
                continue

        # Defensive fallback: enumerate every #header-login-button in the DOM
        # and use the first one that reports as visible.
        if login_btn is None:
            self._log_step("falling back to manual visibility scan of #header-login-button")
            try:
                all_btns = page.locator("#header-login-button")
                count = all_btns.count()
                self._log_step(f"DOM has {count} '#header-login-button' element(s)")
                for i in range(count):
                    try:
                        candidate = all_btns.nth(i)
                        if candidate.is_visible():
                            login_btn = candidate
                            self._log_step(f"using #header-login-button at index {i} (visible)")
                            break
                    except Exception:
                        continue
            except Exception as e:
                self._log_step(f"manual scan failed: {e}")

        if login_btn is None:
            raise last_err if last_err is not None else RuntimeError(
                "TikTok 'Log in' button not found (no visible match)"
            )

        page_pause(page, 350, 850)
        try:
            login_btn.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        try:
            human_click(login_btn, page=page)
        except Exception as click_err:
            self._log_step(f"hover+click failed ({click_err}); retrying with force=True")
            login_btn.click(force=True, timeout=10000)

    def _click_continue_with_google(self, page):
        """Click "Continue with Google" and return the page that holds the
        Google login form (a popup if TikTok opens one, otherwise the
        same page after a redirect)."""
        google_btn = self._wait_for_first_visible(
            page,
            (
                '[data-e2e="channel-item"]:has-text("Continue with Google")',
                'div[role="link"]:has-text("Continue with Google")',
                'div:has-text("Continue with Google")',
                'button:has-text("Continue with Google")',
            ),
            timeout_ms=LONG_WAIT_MS,
        )
        page_pause(page, 500, 1100)

        try:
            with page.context.expect_page(timeout=15000) as info:
                human_click(google_btn, page=page)
            popup = info.value
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=LONG_WAIT_MS)
            except Exception:
                pass
            page_pause(popup, 1200, 2400)
            return popup
        except Exception:
            page_pause(page, 1200, 2400)
            try:
                if "accounts.google.com" in page.url:
                    return page
            except Exception:
                pass
            try:
                page.wait_for_url("**accounts.google.com**", timeout=15000)
            except Exception:
                pass
            return page

    def _enter_google_credentials(self, google_page, email: str, password: str) -> None:
        email_input = self._wait_for_first_visible(
            google_page,
            (
                'input[name="identifier"]',
                "#identifierId",
                'input[type="email"]',
            ),
            timeout_ms=LONG_WAIT_MS,
        )
        page_pause(google_page, 400, 900)
        fill_field_humanly(google_page, email_input, email)
        page_pause(google_page, 600, 1300)

        email_next = self._wait_for_first_visible(
            google_page,
            (
                "#identifierNext button",
                "#identifierNext",
                'div[id="identifierNext"] button',
            ),
            timeout_ms=LONG_WAIT_MS,
        )
        human_click(email_next, page=google_page)
        page_pause(google_page, 2500, 4500)

        password_input = self._wait_for_first_visible(
            google_page,
            (
                'input[name="Passwd"]',
                '#password input[type="password"]',
                'input[type="password"]',
            ),
            timeout_ms=LONG_WAIT_MS,
        )
        page_pause(google_page, 400, 900)
        fill_field_humanly(google_page, password_input, password)
        page_pause(google_page, 600, 1400)

        password_next = self._wait_for_first_visible(
            google_page,
            (
                "#passwordNext button",
                "#passwordNext",
                'div[id="passwordNext"] button',
            ),
            timeout_ms=LONG_WAIT_MS,
        )
        human_click(password_next, page=google_page)
        page_pause(google_page, 2500, 4500)

    def _maybe_click_oauth_consent(self, google_page) -> None:
        """If Google shows the "Continue to TikTok" consent screen, accept it.

        This step is optional - if Google doesn't ask for consent (e.g. the
        user already approved TikTok in the past), the popup goes straight
        back to TikTok and this method just returns after a short wait.
        """
        if self._is_page_dead(google_page):
            return
        candidates = (
            'button:has-text("Pokracovat")',
            'button:has-text("Pokračovat")',
            'button:has-text("Continue")',
            'button:has-text("Allow")',
            'button:has-text("Povolit")',
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            if self._is_page_dead(google_page):
                return
            for sel in candidates:
                try:
                    btn = google_page.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        page_pause(google_page, 500, 1100)
                        human_click(btn, page=google_page)
                        page_pause(google_page, 1500, 2800)
                        return
                except Exception:
                    continue
            try:
                google_page.wait_for_timeout(500)
            except Exception:
                return

    def _wait_for_post_login(self, page, google_page, seconds: int = 15) -> None:
        """Pause for the requested number of seconds while the redirect back
        to TikTok finishes. Uses small ``page.wait_for_timeout`` slices so the
        page event loop keeps spinning."""
        end = time.time() + seconds
        while time.time() < end:
            try:
                page.wait_for_timeout(1000)
            except Exception:
                try:
                    time.sleep(1)
                except Exception:
                    return

    def _save_screenshot(self, page) -> str:
        try:
            if self._is_page_dead(page):
                return ""
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(SCREENSHOT_DIR, f"tiktok_login_{ts}.png")
            page.screenshot(path=path, full_page=True)
            logger.info("Saved TikTok login screenshot to %s", path)
            return path
        except Exception:
            logger.exception("Failed to save TikTok login screenshot")
            return ""

    def _open_screenshot(self, path: str) -> None:
        if not path or not os.path.isfile(path):
            return
        try:
            os.startfile(path)
        except Exception:
            logger.debug("Could not auto-open screenshot %s", path, exc_info=True)

    def _close_browser(self, page) -> None:
        """Close the persistent context that owns ``page``.

        After this call the BrowserThread's ``_pages`` / ``_contexts`` may
        still hold stale references to the closed objects, but the next
        ``get_page("tiktok")`` will detect that and recreate the context
        from the same on-disk profile (which keeps us logged in).
        """
        try:
            ctx = page.context
        except Exception:
            ctx = None
        try:
            page.close()
        except Exception:
            pass
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass

    @staticmethod
    def _is_page_dead(page) -> bool:
        try:
            return bool(page.is_closed())
        except Exception:
            return True

    @staticmethod
    def _with_screenshot(msg: str, screenshot_path: str) -> str:
        if screenshot_path:
            return f"{msg} Screenshot: {screenshot_path}"
        return msg
