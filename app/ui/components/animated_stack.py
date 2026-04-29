from PySide6.QtWidgets import QStackedWidget, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import (
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint, QAbstractAnimation,
)


class AnimatedStackedWidget(QStackedWidget):
    """QStackedWidget with smooth slide transitions between pages."""

    DURATION = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animation_group: QParallelAnimationGroup | None = None
        self._previous_index = 0

    def slide_to(self, index: int, direction: str = "auto"):
        """Animate transition to the given page index.

        direction: 'left', 'right', or 'auto' (right if going forward, left if back).
        """
        if index == self.currentIndex():
            return
        if self._animation_group and self._animation_group.state() == QAbstractAnimation.State.Running:
            self._animation_group.stop()
            self._finish_animation()

        old_index = self.currentIndex()
        new_widget = self.widget(index)
        old_widget = self.widget(old_index)
        if not new_widget or not old_widget:
            self.setCurrentIndex(index)
            return

        if direction == "auto":
            direction = "right" if index > old_index else "left"

        width = self.width()
        offset = width if direction == "right" else -width

        new_widget.setGeometry(0, 0, width, self.height())
        new_widget.move(offset, 0)
        new_widget.show()
        new_widget.raise_()

        anim_old = QPropertyAnimation(old_widget, b"pos", self)
        anim_old.setDuration(self.DURATION)
        anim_old.setStartValue(QPoint(0, 0))
        anim_old.setEndValue(QPoint(-offset, 0))
        anim_old.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim_new = QPropertyAnimation(new_widget, b"pos", self)
        anim_new.setDuration(self.DURATION)
        anim_new.setStartValue(QPoint(offset, 0))
        anim_new.setEndValue(QPoint(0, 0))
        anim_new.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._animation_group = QParallelAnimationGroup(self)
        self._animation_group.addAnimation(anim_old)
        self._animation_group.addAnimation(anim_new)

        self._pending_index = index
        self._animation_group.finished.connect(self._finish_animation)
        self._animation_group.start()

    def _finish_animation(self):
        idx = getattr(self, "_pending_index", self.currentIndex())
        self.setCurrentIndex(idx)
        for i in range(self.count()):
            w = self.widget(i)
            if w:
                w.move(0, 0)

    def slide_forward(self, index: int):
        self.slide_to(index, "right")

    def slide_back(self, index: int):
        self.slide_to(index, "left")
