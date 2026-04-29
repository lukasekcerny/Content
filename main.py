import sys
import os

os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.ui.main_window import MainWindow
from app.theme import build_stylesheet
from app.db.database import Database


def get_app_data_dir() -> str:
    base = os.path.join(os.path.expanduser("~"), ".content-uploader")
    os.makedirs(base, exist_ok=True)
    return base


def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("ContentUploader")

    data_dir = get_app_data_dir()
    db = Database(os.path.join(data_dir, "content.db"))

    app.setStyleSheet(build_stylesheet())

    window = MainWindow(db=db, data_dir=data_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
