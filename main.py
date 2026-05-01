import sys
import os

os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.ui.main_window import MainWindow
from app.theme import build_stylesheet
from app.db.database import Database
from app.auth.token_store import get_credentials
from app.constants import PLATFORMS


def get_app_data_dir() -> str:
    base = os.path.join(os.path.expanduser("~"), ".content-uploader")
    os.makedirs(base, exist_ok=True)
    return base


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

    data_dir = get_app_data_dir()
    db = Database(os.path.join(data_dir, "content.db"))
    reset_stale_platform_connections(db)

    app.setStyleSheet(build_stylesheet())

    window = MainWindow(db=db, data_dir=data_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
