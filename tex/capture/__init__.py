from __future__ import annotations

import os

from PIL import Image

from tex.capture.base import CaptureCanceled, WindowInfo
from tex.capture import wayland


def is_wayland() -> bool:
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def grab_raw() -> tuple[Image.Image, list[WindowInfo], tuple[int, int]]:
    """Blocking full-screen grab. Returns (image, windows, origin)."""
    if is_wayland():
        return wayland.grab_fullscreen(), [], (0, 0)
    from tex.capture import x11

    img, origin = x11.grab_fullscreen()
    try:
        windows = x11.list_windows()
    except Exception:
        windows = []
    return img, windows, origin


def interactive_select() -> Image.Image:
    """Compositor-driven region selection (Wayland)."""
    return wayland.interactive_select()
