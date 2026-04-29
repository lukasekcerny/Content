import os
import sys
import logging
import threading
import shutil
import winreg
from typing import Any, Callable, Optional
from queue import Queue

from PySide6.QtCore import QThread, QObject, Signal

logger = logging.getLogger(__name__)


def _find_chrome_executable() -> Optional[str]:
    """Find the system-installed Chrome executable on Windows."""
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        val, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        if val and os.path.isfile(val):
            return val
    except OSError:
        pass

    found = shutil.which("chrome") or shutil.which("google-chrome")
    return found


class BrowserThread(QThread):
    """Dedicated thread that owns the Playwright instance.

    All browser operations are submitted as callables via `run_command()` and
    executed sequentially on this thread.  Results (or exceptions) are returned
    to callers through a per-command `Queue`.
    """

    ready = Signal()

    def __init__(self, data_dir: str, parent=None):
        super().__init__(parent)
        self._data_dir = data_dir
        self._command_queue: Queue[tuple[Callable, Queue] | None] = Queue()
        self._playwright = None
        self._contexts: dict[str, Any] = {}
        self._pages: dict[str, Any] = {}
        self._running = True

    def run(self):
        from playwright.sync_api import sync_playwright

        pw_cm = sync_playwright()
        self._playwright = pw_cm.start()
        logger.info("Playwright started on BrowserThread")
        self.ready.emit()

        while self._running:
            item = self._command_queue.get()
            if item is None:
                break
            fn, result_q = item
            try:
                result = fn(self)
                result_q.put(("ok", result))
            except Exception as e:
                logger.exception("BrowserThread command failed")
                result_q.put(("error", e))

        self._shutdown_contexts()
        try:
            self._playwright.stop()
        except Exception:
            pass
        logger.info("Playwright stopped")

    def run_command(self, fn: Callable[["BrowserThread"], Any], timeout: float = 120) -> Any:
        """Submit a callable to the browser thread and block until it completes."""
        result_q: Queue = Queue()
        self._command_queue.put((fn, result_q))
        status, value = result_q.get(timeout=timeout)
        if status == "error":
            raise value
        return value

    def get_page(self, platform_id: str):
        """Get or create a persistent page for a platform (must be called ON the browser thread)."""
        if platform_id in self._pages:
            page = self._pages[platform_id]
            try:
                page.title()
                return page
            except Exception:
                self._pages.pop(platform_id, None)
                ctx = self._contexts.pop(platform_id, None)
                if ctx:
                    try:
                        ctx.close()
                    except Exception:
                        pass

        profile_dir = os.path.join(self._data_dir, "browser", platform_id)
        os.makedirs(profile_dir, exist_ok=True)

        launch_kwargs = dict(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        try:
            ctx = self._playwright.chromium.launch_persistent_context(
                channel="chrome", **launch_kwargs,
            )
        except Exception as first_err:
            logger.warning("channel='chrome' failed (%s), trying executable_path", first_err)
            chrome_path = _find_chrome_executable()
            if chrome_path:
                logger.info("Found Chrome at %s", chrome_path)
                ctx = self._playwright.chromium.launch_persistent_context(
                    executable_path=chrome_path, **launch_kwargs,
                )
            else:
                logger.warning("System Chrome not found, falling back to bundled chromium")
                ctx = self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        self._contexts[platform_id] = ctx

        if ctx.pages:
            page = ctx.pages[0]
        else:
            page = ctx.new_page()
        self._pages[platform_id] = page
        logger.info("Persistent context created for %s", platform_id)
        return page

    def _shutdown_contexts(self):
        for pid, ctx in list(self._contexts.items()):
            try:
                ctx.close()
                logger.info("Closed context for %s", pid)
            except Exception:
                logger.debug("Error closing context for %s", pid, exc_info=True)
        self._contexts.clear()
        self._pages.clear()

    def request_stop(self):
        self._running = False
        self._command_queue.put(None)


class BrowserManager:
    """Singleton that manages the BrowserThread lifecycle."""

    _instance: Optional["BrowserManager"] = None

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        self._thread: Optional[BrowserThread] = None

    @classmethod
    def get_instance(cls, data_dir: str = "") -> "BrowserManager":
        if cls._instance is None:
            cls._instance = cls(data_dir)
        return cls._instance

    def start(self):
        if self._thread and self._thread.isRunning():
            return
        self._thread = BrowserThread(self._data_dir)
        self._thread.start()
        logger.info("BrowserManager started")

    def execute(self, fn: Callable[[BrowserThread], Any], timeout: float = 120) -> Any:
        if not self._thread or not self._thread.isRunning():
            raise RuntimeError("BrowserThread is not running")
        return self._thread.run_command(fn, timeout=timeout)

    def get_page(self, platform_id: str):
        """Convenience: get a page for a platform (blocks until ready)."""
        return self.execute(lambda bt: bt.get_page(platform_id))

    def shutdown(self):
        if self._thread and self._thread.isRunning():
            self._thread.request_stop()
            self._thread.wait(10000)
            logger.info("BrowserManager shut down")
        self._thread = None
        BrowserManager._instance = None
