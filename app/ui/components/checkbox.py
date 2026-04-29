from PySide6.QtWidgets import QCheckBox


class PlatformCheckBox(QCheckBox):
    """Styled checkbox for platform target selection."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
