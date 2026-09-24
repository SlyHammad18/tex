from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICONS: dict[str, str] = {
    "select": '<rect x="4" y="5.5" width="16" height="13" rx="2" fill="none" stroke="{c}" stroke-width="1.7" stroke-dasharray="4 3"/>',
    "window": '<rect x="3.5" y="4.5" width="17" height="15" rx="2" fill="none" stroke="{c}" stroke-width="1.7"/><line x1="3.5" y1="9" x2="20.5" y2="9" stroke="{c}" stroke-width="1.7"/><circle cx="6.2" cy="6.8" r="0.9" fill="{c}"/>',
    "screen": '<rect x="3" y="4.5" width="18" height="12.5" rx="2" fill="none" stroke="{c}" stroke-width="1.7"/><line x1="9" y1="20.5" x2="15" y2="20.5" stroke="{c}" stroke-width="1.7"/><line x1="12" y1="17" x2="12" y2="20.5" stroke="{c}" stroke-width="1.7"/>',
    "gear": '<circle cx="12" cy="12" r="3.2" fill="none" stroke="{c}" stroke-width="1.7"/><g stroke="{c}" stroke-width="1.7"><line x1="12" y1="2.8" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="21.2"/><line x1="2.8" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="21.2" y2="12"/><line x1="5.5" y1="5.5" x2="7.7" y2="7.7"/><line x1="16.3" y1="16.3" x2="18.5" y2="18.5"/><line x1="18.5" y1="5.5" x2="16.3" y2="7.7"/><line x1="7.7" y1="16.3" x2="5.5" y2="18.5"/></g>',
    "copy": '<rect x="8.5" y="8.5" width="11" height="11" rx="2" fill="none" stroke="{c}" stroke-width="1.7"/><path d="M15.5 5.5v-1h-11v11h1" fill="none" stroke="{c}" stroke-width="1.7"/>',
    "save": '<path d="M12 4v10m0 0l-4-4m4 4l4-4" fill="none" stroke="{c}" stroke-width="1.7"/><path d="M4.5 15.5v2a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-2" fill="none" stroke="{c}" stroke-width="1.7"/>',
    "back": '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="{c}" stroke-width="1.9"/>',
    "crop": '<path d="M7 3v14a1 1 0 0 0 1 1h13" fill="none" stroke="{c}" stroke-width="1.7"/><path d="M3 7h14a1 1 0 0 1 1 1v13" fill="none" stroke="{c}" stroke-width="1.7"/>',
    "compare": '<rect x="3.5" y="5" width="7" height="14" rx="1.5" fill="none" stroke="{c}" stroke-width="1.6"/><rect x="13.5" y="5" width="7" height="14" rx="1.5" fill="none" stroke="{c}" stroke-width="1.6"/>',
}


def render_icon(name: str, size: int = 32, color: str = "#E6EAF0") -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        f'viewBox="0 0 24 24">{ICONS[name].format(c=color)}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    icon = QIcon()
    if not renderer.isValid() or size <= 0:
        return icon
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(QPixmap.fromImage(img))


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    if img.mode != "RGB":
        img = img.convert("RGB")
    data = img.tobytes()
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


APP_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
    '<rect x="8" y="8" width="112" height="112" rx="26" fill="#101318"/>'
    '<rect x="8.5" y="8.5" width="111" height="111" rx="25.5" fill="none" stroke="#2A313D" stroke-width="1.5"/>'
    '<rect x="34" y="34" width="60" height="14" rx="4" fill="#4CC2FF"/>'
    '<rect x="57" y="34" width="14" height="60" rx="4" fill="#4CC2FF"/>'
    '<rect x="34" y="86" width="24" height="8" rx="4" fill="#2A313D"/>'
    '<rect x="70" y="86" width="24" height="8" rx="4" fill="#2A313D"/>'
    '</svg>'
)


def app_icon() -> QIcon:
    renderer = QSvgRenderer(QByteArray(APP_ICON_SVG.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()
    img = QImage(128, 128, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter, QRectF(0, 0, 128, 128))
    painter.end()
    return QIcon(QPixmap.fromImage(img))
