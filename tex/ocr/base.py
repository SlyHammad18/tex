from __future__ import annotations

import base64
import io
from abc import ABC, abstractmethod

from PIL import Image

from tex.ocr.models import ModelInfo, OcrResult


class OcrError(RuntimeError):
    pass


def encode_image(img: Image.Image, max_bytes: int = 5_000_000) -> tuple[str, str]:
    """Encode a PIL image as (mime_type, base64). Falls back to JPEG when the PNG is too large."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    mime = "image/png"
    if buf.tell() > max_bytes:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=88)
        mime = "image/jpeg"
    return mime, base64.b64encode(buf.getvalue()).decode("ascii")


def strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1 and t.rstrip().endswith("```"):
            inner = t[first_nl + 1 : t.rstrip().rfind("```")]
            return inner.strip()
    return t


class OcrEngine(ABC):
    name: str = ""
    label: str = ""

    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        ...

    @abstractmethod
    def extract(self, image: Image.Image, model_id: str, prompt: str) -> OcrResult:
        ...
