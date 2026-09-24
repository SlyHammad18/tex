from __future__ import annotations

import shutil
import time

from PIL import Image, ImageOps

from tex.ocr.base import OcrEngine, OcrError
from tex.ocr.models import ModelInfo, OcrResult


def preprocess(img: Image.Image, upscale: int = 2) -> Image.Image:
    gray = img.convert("L")
    gray = ImageOps.autocontrast(gray)
    if upscale and upscale > 1:
        gray = gray.resize((gray.width * upscale, gray.height * upscale), Image.LANCZOS)
    return gray


class TesseractEngine(OcrEngine):
    name = "tesseract"
    label = "Tesseract (offline)"

    def __init__(self, tesseract_cfg: dict | None = None):
        self.cfg = tesseract_cfg or {}

    def available(self) -> bool:
        return bool(shutil.which("tesseract"))

    def list_models(self) -> list[ModelInfo]:
        import pytesseract

        try:
            langs = [l for l in pytesseract.get_languages(config="") if l and l != "osd"]
        except Exception:
            langs = []
        if not langs:
            langs = ["eng"]
        return [ModelInfo(f"tesseract:{lang}", self.name, lang) for lang in sorted(langs)]

    def extract(self, image: Image.Image, model_id: str, prompt: str) -> OcrResult:
        import pytesseract

        lang = model_id.split(":", 1)[1] if ":" in model_id else (self.cfg.get("language") or "eng")
        t0 = time.perf_counter()
        try:
            proc = preprocess(image, int(self.cfg.get("upscale", 2) or 0))
            text = pytesseract.image_to_string(proc, lang=lang)
        except pytesseract.TesseractNotFoundError as e:
            raise OcrError(str(e)) from e
        except Exception as e:
            raise OcrError(f"tesseract failed: {e}") from e
        return OcrResult(
            text=text.strip(),
            model=model_id,
            provider=self.name,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
