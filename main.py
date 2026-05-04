import sys
import os
import logging
import threading
from logging.handlers import RotatingFileHandler

os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.ui.main_window import MainWindow
from app.theme import build_stylesheet
from app.db.database import Database
from app.auth.token_store import get_credentials
from app.constants import PLATFORMS


def install_crash_guards():
    """Install global hooks so the app never silently dies on unhandled exceptions."""
    root_logger = logging.getLogger()

    def _excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root_logger.critical(
            "Uncaught exception on main thread",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _excepthook

    def _thread_excepthook(args):
        root_logger.critical(
            "Uncaught exception on thread %r", args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_excepthook


def get_app_data_dir() -> str:
    base = os.path.join(os.path.expanduser("~"), ".content-uploader")
    os.makedirs(base, exist_ok=True)
    return base


def setup_logging(data_dir: str) -> str:
    """Send all logger.info / logger.exception output to a rotating log file.

    PyInstaller ``--windowed`` drops stdout/stderr, so without this the per-step
    auth logs vanish. The log lives at ``<data_dir>/app.log`` and is the file we
    ask the user to attach when something goes wrong.
    """
    log_path = os.path.join(data_dir, "app.log")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(file_handler)
    return log_path


def reset_stale_platform_connections(db: Database) -> None:
    """Clear `connected = 1` rows that have no stored credentials in the keyring.

    A platform is only considered truly connected if the user has explicitly
    logged in (which stores credentials via `save_credentials`). Anything else
    is leftover state from a previous run or a buggy probe and should be reset
    so the user is prompted to log in again instead of seeing a misleading
    "Connected" badge.
    """
    for pid in PLATFORMS.keys():
        platform = db.get_platform(pid)
        if not platform or not platform.connected:
            continue
        email, password = get_credentials(pid)
        if not email or not password:
            db.set_platform_disconnected(pid)


def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("ContentUploader")
    app.setQuitOnLastWindowClosed(True)

    data_dir = get_app_data_dir()
    log_path = setup_logging(data_dir)
    install_crash_guards()
    root_logger = logging.getLogger(__name__)
    root_logger.info("ContentUploader starting; log file: %s", log_path)

    def _on_about_to_quit():
        import traceback
        root_logger.info("QApplication.aboutToQuit fired")
        stack = "".join(traceback.format_stack())
        root_logger.debug("aboutToQuit stack:\n%s", stack)

    app.aboutToQuit.connect(_on_about_to_quit)

    db = Database(os.path.join(data_dir, "content.db"))
    reset_stale_platform_connections(db)

    app.setStyleSheet(build_stylesheet())

    window = MainWindow(db=db, data_dir=data_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
