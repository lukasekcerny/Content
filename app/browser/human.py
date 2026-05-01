"""Human-like browser interaction helpers for Playwright.

The platform sign-in flows (TikTok in particular) are aggressive about
detecting headless/automated sessions. The helpers in this module add
the small dose of randomness that an average user produces:

  * pre-click hover with a short pause,
  * jittered keystroke delays when typing into form fields,
  * variable post-action waits,
  * a small init script that hides the most obvious automation signals.

They are deliberately small, dependency-free wrappers around Playwright's
sync API so any auth/upload provider can use them without pulling in a
full third-party stealth library.
"""

import logging
import random
import time

logger = logging.getLogger(__name__)


def human_pause(min_ms: int = 400, max_ms: int = 1400) -> None:
    """Sleep for a random duration via ``time.sleep`` (no page required)."""
    time.sleep(random.uniform(min_ms / 1000.0, max_ms / 1000.0))


def page_pause(page, min_ms: int = 400, max_ms: int = 1400) -> None:
    """Wait for a random duration on a Playwright page."""
    try:
        page.wait_for_timeout(int(random.uniform(min_ms, max_ms)))
    except Exception:
        human_pause(min_ms, max_ms)


def human_click(locator, page=None, hover_first: bool = True) -> None:
    """Hover briefly then click the given locator.

    ``page`` is optional but lets us pause via ``page.wait_for_timeout``
    instead of a real ``time.sleep`` call, which integrates better with
    Playwright's event loop.
    """
    try:
        if hover_first:
            try:
                locator.hover(timeout=4000)
                if page is not None:
                    page_pause(page, 80, 260)
                else:
                    human_pause(80, 260)
            except Exception:
                pass
        locator.click(delay=random.uniform(40, 130))
    except Exception:
        # Last-resort fallback: a plain click without delay/hover.
        locator.click()


def human_type(page, text: str, min_delay: int = 70, max_delay: int = 170) -> None:
    """Type ``text`` on the focused element with per-character jitter.

    Roughly every 20th character we throw in a longer pause to mimic a
    real human pausing to think while typing.
    """
    for ch in text:
        page.keyboard.type(ch, delay=random.uniform(min_delay, max_delay))
        if random.random() < 0.05:
            human_pause(180, 420)


def fill_field_humanly(page, locator, text: str) -> None:
    """Click into a field, clear any existing value, then type humanly."""
    try:
        locator.click(delay=random.uniform(40, 130))
    except Exception:
        locator.click()
    page_pause(page, 180, 420)
    try:
        locator.fill("")
    except Exception:
        try:
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
        except Exception:
            pass
    page_pause(page, 100, 250)
    human_type(page, text)


REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


STEALTH_INIT_SCRIPT = """
(() => {
    try {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    } catch (e) {}
    try {
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    } catch (e) {}
    try {
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    } catch (e) {}
    try {
        window.chrome = window.chrome || { runtime: {} };
    } catch (e) {}
    try {
        const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
        if (originalQuery) {
            window.navigator.permissions.query = (parameters) => (
                parameters && parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
        }
    } catch (e) {}
})();
"""


def apply_stealth(context) -> None:
    """Inject a small set of anti-detection patches into a Playwright context."""
    try:
        context.add_init_script(STEALTH_INIT_SCRIPT)
    except Exception:
        logger.warning("Failed to apply stealth init script", exc_info=True)
