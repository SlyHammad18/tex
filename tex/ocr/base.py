from __future__ import annotations

import base64
import io
import json
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


GROUP_PROMPT = (
    "You are given text extracted from a screenshot. List every meaningful number or "
    "number-like value in it, grouped by what it is (IP address, phone number, date, time, "
    "price/amount, percentage, ID/code, version, measurement, coordinate, etc.). "
    'Respond with ONLY a JSON array of objects like {"label": "IP", "value": "192.168.1.1"}. '
    "Use short labels and keep each value exactly as it appears in the text. "
    "No markdown fences, no commentary. If nothing qualifies, respond with [].\n\nText:\n"
)


def parse_number_groups(raw: str) -> list:
    raw = (raw or "").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start : end + 1])
    except Exception:
        return []
    return data if isinstance(data, list) else []


TRANSLATE_PROMPT = (
    "Detect the language of the following text, then translate it to English. "
    'Respond with ONLY a JSON object like {"language": "German", "translation": "Hello"} '
    "where language is the detected language name in English. "
    "No markdown, no commentary.\n\nText:\n"
)


def parse_translation(raw: str) -> tuple[str, str]:
    raw = (raw or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return "", ""
    try:
        data = json.loads(raw[start : end + 1])
    except Exception:
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    return str(data.get("language") or "").strip(), str(data.get("translation") or "").strip()


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
