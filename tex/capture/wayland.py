from __future__ import annotations

import asyncio
import io
import os
import shutil
import subprocess
import urllib.parse
import uuid

from PIL import Image

from tex.capture.base import CaptureCanceled
from tex.constants import PORTAL_TIMEOUT

_PORTAL_DEST = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_SCREENSHOT_IFACE = "org.freedesktop.portal.Screenshot"
_REQUEST_IFACE = "org.freedesktop.portal.Request"

_WLROOTS_DESKTOPS = {"sway", "hyprland", "wlroots", "river", "labwc", "niri", "wayfire"}


def _wlroots_desktop() -> bool:
    return (os.environ.get("XDG_CURRENT_DESKTOP") or "").split(":")[0].lower() in _WLROOTS_DESKTOPS


def _grim_slurp_available() -> bool:
    return bool(shutil.which("grim")) and bool(shutil.which("slurp"))


def _grim_fullscreen() -> Image.Image:
    out = subprocess.run(["grim", "-"], capture_output=True, check=True, timeout=30)
    return Image.open(io.BytesIO(out.stdout)).convert("RGB")


def _grim_select() -> Image.Image:
    region = subprocess.run(["slurp"], capture_output=True, timeout=300)
    if region.returncode != 0:
        raise CaptureCanceled("selection canceled")
    spec = region.stdout.decode().strip()
    out = subprocess.run(["grim", "-g", spec, "-"], capture_output=True, check=True, timeout=30)
    return Image.open(io.BytesIO(out.stdout)).convert("RGB")


async def _portal_screenshot(interactive: bool) -> str:
    from dbus_next import Variant
    from dbus_next.aio import MessageBus
    from dbus_next.message import Message, MessageType

    bus = await MessageBus().connect()
    try:
        token = uuid.uuid4().hex
        sender = bus.unique_name.lstrip(":").replace(".", "_")
        predicted = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        reply_path = {"path": predicted}
        done: asyncio.Future = asyncio.get_running_loop().create_future()

        def handle(msg: Message) -> None:
            if (
                msg.message_type == MessageType.SIGNAL
                and msg.member == "Response"
                and msg.interface == _REQUEST_IFACE
                and msg.path in (predicted, reply_path["path"])
                and not done.done()
            ):
                done.set_result(msg.body)

        bus.add_message_handler(handle)
        reply = await bus.call(
            Message(
                destination=_PORTAL_DEST,
                path=_PORTAL_PATH,
                interface=_SCREENSHOT_IFACE,
                member="Screenshot",
                signature="sa{sv}",
                body=[
                    "",
                    {
                        "handle_token": Variant("s", token),
                        "interactive": Variant("b", interactive),
                    },
                ],
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{reply.error_name}: {reply.body}")
        if reply.body:
            reply_path["path"] = str(reply.body[0])
        code, results = await asyncio.wait_for(done, timeout=PORTAL_TIMEOUT)
        if code == 1:
            raise CaptureCanceled("screenshot canceled by user")
        if code == 2:
            raise CaptureCanceled("screenshot canceled by user")
        if code != 0:
            raise RuntimeError(f"portal screenshot failed (code {code})")
        uri = results.get("uri", {}).value if isinstance(results.get("uri"), Variant) else results.get("uri")
        if not uri:
            raise RuntimeError("portal returned no image uri")
        return str(uri)
    finally:
        bus.disconnect()


def _load_uri(uri: str) -> Image.Image:
    path = urllib.parse.unquote(uri.removeprefix("file://"))
    return Image.open(path).convert("RGB")


def portal_screenshot(interactive: bool = False) -> Image.Image:
    uri = asyncio.run(_portal_screenshot(interactive))
    return _load_uri(uri)


def grab_fullscreen(interactive: bool = False) -> Image.Image:
    if _grim_slurp_available() and _wlroots_desktop():
        return _grim_fullscreen()
    return portal_screenshot(interactive=False)


def interactive_select() -> Image.Image:
    if _grim_slurp_available() and _wlroots_desktop():
        return _grim_select()
    return portal_screenshot(interactive=True)
