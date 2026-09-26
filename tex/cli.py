from __future__ import annotations

import argparse
from tex import __version__
from tex.capture.base import CaptureMode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="tex",
        description="Tex - screenshot capture with AI text extraction.",
    )
    p.add_argument("--version", action="version", version=f"Tex {__version__}")

    mode = p.add_mutually_exclusive_group()
    for m in CaptureMode:
        mode.add_argument(
            f"--{m.value}",
            dest="mode",
            action="store_const",
            const=m.value,
            help=f"capture {m.value} on launch",
        )

    p.add_argument(
        "--engine",
        choices=["tesseract", "gemini", "groq", "cerebras", "openrouter"],
        help="extraction engine to run after capture",
    )
    p.add_argument("--model", help="model id (provider) or tesseract language tag")
    p.add_argument("--prompt", help="custom extraction prompt")
    p.add_argument("--clipboard", action="store_true", help="copy result text to clipboard")
    p.add_argument("--save", metavar="PATH", help="save result text to a .txt file")
    return p.parse_args(argv)
