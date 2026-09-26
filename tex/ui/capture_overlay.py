from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from tex.capture.base import CaptureMode, Rect, WindowInfo
from tex.ui.icons import pil_to_pixmap
from tex.ui import theme


def _to_qrect(r: Rect) -> QRect:
    return QRect(r.x, r.y, r.w, r.h)


class CaptureOverlay(QWidget):
    accepted = Signal(object)
    canceled = Signal()

    def __init__(
        self,
        image,
        windows: list[Rect],
        mode: CaptureMode,
        px_origin_fn,
        hint: str = "",
        parent=None,
    ):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._mode = mode
        self._px_origin_fn = px_origin_fn
        self._pix = pil_to_pixmap(image)
        self._windows = list(windows)
        self._hint = hint or self._default_hint()
        self._origin_px = QPoint(0, 0)
        self._dpr = 1.0
        self._press_px: QPoint | None = None
        self._cur_px: QPoint | None = None
        self._dragging = False
        self._sel_px: Rect | None = None
        self._hover_idx: int | None = None
        self.setCrossCursor()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    def setCrossCursor(self) -> None:
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _default_hint(self) -> str:
        return {
            CaptureMode.SELECT: "Drag to select an area  ·  Esc to cancel",
            CaptureMode.WINDOW: "Click a window to capture  ·  Esc to cancel",
            CaptureMode.SCREEN: "Select an area  ·  Esc to cancel",
        }[self._mode]

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._dpr = self.devicePixelRatioF() or 1.0
        self._origin_px = self._px_origin_fn(self.mapToGlobal(QPoint(0, 0)))
        self.raise_()
        self.activateWindow()

    def _local_to_px(self, pos: QPointF) -> QPoint:
        return QPoint(
            int(pos.x() * self._dpr) + self._origin_px.x(),
            int(pos.y() * self._dpr) + self._origin_px.y(),
        )

    def _px_to_local(self, r: Rect) -> QRectF:
        return QRectF(
            (r.x - self._origin_px.x()) / self._dpr,
            (r.y - self._origin_px.y()) / self._dpr,
            r.w / self._dpr,
            r.h / self._dpr,
        )

    def _current_rect(self) -> Rect | None:
        if self._mode == CaptureMode.WINDOW and self._hover_idx is not None and not self._dragging:
            return self._windows[self._hover_idx]
        if self._sel_px is not None:
            return self._sel_px
        return None

    def _accept(self, rect: Rect) -> None:
        self.accepted.emit(rect)
        self.close()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._press_px = self._local_to_px(e.position())
        self._cur_px = self._press_px
        self._dragging = False

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        px = self._local_to_px(e.position())
        self._cur_px = px
        if self._press_px is not None:
            dx = abs(px.x() - self._press_px.x())
            dy = abs(px.y() - self._press_px.y())
            if dx * dy > 36 or max(dx, dy) > 12:
                self._dragging = True
                self._hover_idx = None
                self._sel_px = Rect(
                    min(self._press_px.x(), px.x()),
                    min(self._press_px.y(), px.y()),
                    max(dx, 1),
                    max(dy, 1),
                )
        if self._mode == CaptureMode.WINDOW and not self._dragging:
            from tex.capture.base import smallest_containing

            self._hover_idx = smallest_containing(self._windows, px.x(), px.y())
        self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton or self._press_px is None:
            return
        if self._dragging and self._sel_px is not None and self._sel_px.area >= 16:
            self._accept(self._sel_px)
            return
        if self._mode == CaptureMode.WINDOW and self._hover_idx is not None:
            self._accept(self._windows[self._hover_idx])
            return
        self._press_px = None
        self._dragging = False
        self._sel_px = None
        self.update()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.canceled.emit()
            self.close()
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            rect = self._current_rect()
            if rect is not None:
                self._accept(rect)
            return
        super().keyPressEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        dpr = self._dpr

        if not self._pix.isNull():
            p.save()
            p.scale(1 / dpr, 1 / dpr)
            p.translate(-self._origin_px)
            p.drawPixmap(0, 0, self._pix)
            p.restore()

        p.fillRect(self.rect(), QColor(0, 0, 0, 115))

        rect = self._current_rect()
        if rect is not None and not self._pix.isNull():
            local = self._px_to_local(rect)
            src = QRectF(rect.x, rect.y, rect.w, rect.h)
            p.drawPixmap(local, self._pix, src)

            # Accent border
            pen = QPen(QColor(theme.ACCENT), 2)
            p.setPen(pen)
            p.drawRect(local)

            # Subtle glow around the selection
            glow_color = QColor(theme.ACCENT)
            glow_color.setAlpha(40)
            glow_pen = QPen(glow_color, 6)
            p.setPen(glow_pen)
            p.drawRect(local.adjusted(-3, -3, 3, 3))
            p.setPen(QPen(QColor(theme.ACCENT), 2))
            p.drawRect(local)

            # Resize handles
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.ACCENT))
            hs = 4
            for cx in (local.left(), local.center().x(), local.right()):
                for cy in (local.top(), local.center().y(), local.bottom()):
                    p.drawRect(QRectF(cx - hs, cy - hs, hs * 2, hs * 2))

            label = f"{rect.w} × {rect.h}"
            if self._mode == CaptureMode.WINDOW and self._hover_idx is not None and not self._dragging:
                title = self._window_title(rect)
                if title:
                    label = title
            self._draw_chip(p, local.topLeft(), label)

        self._draw_chip(p, QPointF(self.width() / 2 - 80, 16), self._hint, center=True)

    def _window_title(self, rect: Rect) -> str:
        for w in self._windows:
            if w.x == rect.x and w.y == rect.y and w.w == rect.w and w.h == rect.h:
                try:
                    return w.title
                except AttributeError:
                    return ""
        return ""

    def _draw_chip(self, p: QPainter, top_left: QPointF, text: str, center: bool = False) -> None:
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text) + 24
        th = fm.height() + 12
        x = top_left.x() - (tw / 2 if center else 0)
        y = top_left.y()
        bg = QRectF(x, y, tw, th)

        # Subtle shadow
        shadow = QRectF(x + 1, y + 1, tw, th)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 80))
        p.drawRoundedRect(shadow, 6, 6)

        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.setBrush(QColor(23, 27, 34, 235))
        p.drawRoundedRect(bg, 6, 6)
        p.setPen(QColor(theme.TEXT))
        p.drawText(bg, Qt.AlignmentFlag.AlignCenter, text)

    @staticmethod
    def window_rects(windows: list[WindowInfo], origin: tuple[int, int]) -> list[Rect]:
        ox, oy = origin
        return [Rect(w.rect.x - ox, w.rect.y - oy, w.rect.w, w.rect.h) for w in windows]
