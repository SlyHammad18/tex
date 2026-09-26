from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QWidget

from tex.ui import theme

_kind_map = {
    "info": ("toast", theme.MUTED),
    "success": ("toastSuccess", theme.OK),
    "error": ("toastError", theme.ERR),
}
_durations = {"info": 3000, "success": 4000, "error": 5000}
_icons = {"info": "ⓘ", "success": "✓", "error": "⚠"}


class Toast(QFrame):
    dismissed = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._text = ""
        self._kind = "info"
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_fade_out)
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0.0)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 6, 8)
        lay.setSpacing(8)

        self.icon_label = QLabel(_icons["info"], self)
        self.icon_label.setObjectName("toastIcon")
        lay.addWidget(self.icon_label)

        self.label = QLabel(self)
        self.label.setObjectName("toastText")
        self.label.setWordWrap(True)
        lay.addWidget(self.label, 1)

        self.close_btn = QPushButton("✕", self)
        self.close_btn.setObjectName("toastClose")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self._start_fade_out)
        lay.addWidget(self.close_btn)

        self.hide()

    def popup(self, text: str, kind: str = "info") -> None:
        self._text = text
        self._kind = kind
        name, _color = _kind_map.get(kind, _kind_map["info"])
        if self.objectName() != name:
            self.setObjectName(name)
            self.style().unpolish(self)
            self.style().polish(self)

        self.icon_label.setText(_icons.get(kind, _icons["info"]))
        self.label.setText(text)
        self.label.adjustSize()

        w = min(max(self.label.width() + 60, 200), self.parentWidget().width() - 48)
        self.label.setFixedWidth(w - 60)
        self.label.adjustSize()
        h = max(self.label.height() + 16, 40)
        self.setFixedSize(w, h)

        self._reposition()
        self._start_fade_in()
        self._timer.start(_durations.get(kind, 3000))

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        pw = parent.width()
        ph = parent.height()
        x = (pw - self.width()) // 2
        y = ph - self.height() - 24
        self.move(x, y)

    def _start_fade_in(self) -> None:
        self.show()
        self.raise_()

        orig_rect = self.geometry()
        start_rect = QRect(orig_rect.x(), orig_rect.y() + 20, orig_rect.width(), orig_rect.height())

        geo_anim = QPropertyAnimation(self, b"geometry", self)
        geo_anim.setDuration(200)
        geo_anim.setStartValue(start_rect)
        geo_anim.setEndValue(orig_rect)
        geo_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._opacity.setOpacity(0.0)
        op_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        op_anim.setDuration(150)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(geo_anim)
        self._anim_group.addAnimation(op_anim)
        self._anim_group.start()

    def _start_fade_out(self) -> None:
        self._timer.stop()
        self._opacity.setOpacity(1.0)

        orig_rect = self.geometry()
        end_rect = QRect(orig_rect.x(), orig_rect.y() + 16, orig_rect.width(), orig_rect.height())

        geo_anim = QPropertyAnimation(self, b"geometry", self)
        geo_anim.setDuration(200)
        geo_anim.setStartValue(orig_rect)
        geo_anim.setEndValue(end_rect)
        geo_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        op_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        op_anim.setDuration(200)
        op_anim.setStartValue(1.0)
        op_anim.setEndValue(0.0)

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(geo_anim)
        self._anim_group.addAnimation(op_anim)
        self._anim_group.finished.connect(self.hide)
        self._anim_group.start()
        self.dismissed.emit()


def show_toast(parent: QWidget, text: str, kind: str = "info") -> None:
    existing = [c for c in parent.findChildren(Toast) if c.isVisible()]
    for i, t in enumerate(existing):
        target_y = parent.height() - t.height() - 24 - (i + 1) * (t.height() + 8)
        anim = QPropertyAnimation(t, b"geometry", t)
        anim.setDuration(150)
        anim.setStartValue(t.geometry())
        anim.setEndValue(QRect(t.x(), target_y, t.width(), t.height()))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

    toast = parent.findChild(Toast)
    if toast is None:
        toast = Toast(parent)
    toast.popup(text, kind)
