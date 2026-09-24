from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from PIL import Image


class CaptureMode(str, Enum):
    SELECT = "select"
    WINDOW = "window"
    SCREEN = "screen"

    @property
    def label(self) -> str:
        return {"select": "Selection", "window": "Window", "screen": "Screen"}[self.value]


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x2 and self.y <= py < self.y2


@dataclass
class WindowInfo:
    wid: int
    title: str
    rect: Rect


@dataclass
class CaptureResult:
    image: Image.Image
    mode: CaptureMode
    windows: list[WindowInfo] = field(default_factory=list)
    origin: tuple[int, int] = (0, 0)
    dpr: float = 1.0
    preselected: bool = False
    label: str = ""


class CaptureCanceled(RuntimeError):
    pass


def normalize(x1: int, y1: int, x2: int, y2: int, min_size: int = 1) -> Rect:
    x, y = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    if w < min_size:
        w = min_size
    if h < min_size:
        h = min_size
    return Rect(x, y, w, h)


def smallest_containing(rects: list[Rect], px: int, py: int) -> int | None:
    best: int | None = None
    for i, r in enumerate(rects):
        if not r.contains(px, py):
            continue
        if best is None or r.area < rects[best].area:
            best = i
    return best


def crop_image(image: Image.Image, rect: Rect) -> Image.Image:
    left = max(0, rect.x)
    top = max(0, rect.y)
    right = min(image.width, rect.x2)
    bottom = min(image.height, rect.y2)
    if right - left < 1 or bottom - top < 1:
        raise ValueError("crop rectangle is empty")
    return image.crop((left, top, right, bottom))
