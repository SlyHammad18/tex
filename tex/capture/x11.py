from __future__ import annotations

from PIL import Image

from tex.capture.base import Rect, WindowInfo


def grab_fullscreen() -> tuple[Image.Image, tuple[int, int]]:
    import mss

    with mss.mss() as sct:
        mon = sct.monitors[0]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.rgb)
        return img, (mon["left"], mon["top"])


def _wm_name(dpy, win) -> str | None:
    from Xlib import X

    for atom_name, prop_type in (
        ("_NET_WM_NAME", dpy.intern_atom("UTF8_STRING")),
        ("WM_NAME", X.AnyPropertyType),
    ):
        prop = win.get_full_property(dpy.intern_atom(atom_name), prop_type)
        if prop and prop.value:
            val = prop.value
            if isinstance(val, bytes):
                return val.decode("utf-8", "replace")
            return str(val)
    return None


def list_windows() -> list[WindowInfo]:
    from Xlib import X
    from Xlib.display import Display

    dpy = Display()
    root = dpy.screen().root
    prop = root.get_full_property(dpy.intern_atom("_NET_CLIENT_LIST"), X.AnyPropertyType)
    if not prop or not prop.value:
        return []
    out: list[WindowInfo] = []
    for wid in prop.value:
        try:
            win = dpy.create_resource_object("window", wid)
            geo = win.get_geometry()
            loc = win.translate_coords(root, 0, 0)
        except Exception:
            continue
        if geo.width < 40 or geo.height < 40:
            continue
        out.append(
            WindowInfo(
                wid=int(wid),
                title=_wm_name(dpy, win) or "",
                rect=Rect(int(loc.x), int(loc.y), int(geo.width), int(geo.height)),
            )
        )
    return out
