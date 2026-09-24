from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QWidget

from tex.ui import theme


class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label = QLabel(self)
        self.label.setObjectName("toastText")
        self.label.setWordWrap(True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def popup(self, text: str, kind: str = "info") -> None:
        name = {"success": "toastSuccess", "error": "toastError"}.get(kind, "toast")
        if self.objectName() != name:
            self.setObjectName(name)
            self.style().unpolish(self)
            self.style().polish(self)
        self.label.setText(text)
        self.label.adjustSize()
        w = min(max(self.label.width() + 28, 160), self.parentWidget().width() - 32)
        self.label.setFixedWidth(w - 28)
        self.label.adjustSize()
        h = self.label.height() + 20
        self.setGeometry(
            (self.parentWidget().width() - w) // 2,
            14,
            w,
            h,
        )
        self.show()
        self.raise_()
        self._timer.start(3500 if kind != "error" else 5000)


def show_toast(parent: QWidget, text: str, kind: str = "info") -> None:
    toast = parent.findChild(Toast)
    if toast is None:
        toast = Toast(parent)
    toast.popup(text, kind)
