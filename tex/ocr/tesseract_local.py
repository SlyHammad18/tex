from __future__ import annotations

import shutil
import time

from PIL import Image, ImageOps

from tex.ocr.base import OcrEngine, OcrError
from tex.ocr.models import ModelInfo, OcrResult

_LANG_NAMES = {
    "eng": "English",
    "deu": "German",
    "fra": "French",
    "spa": "Spanish",
    "ita": "Italian",
    "por": "Portuguese",
    "nld": "Dutch",
    "rus": "Russian",
    "jpn": "Japanese",
    "kor": "Korean",
    "chi_sim": "Chinese (Simplified)",
    "chi_tra": "Chinese (Traditional)",
    "ara": "Arabic",
    "hin": "Hindi",
    "tur": "Turkish",
    "pol": "Polish",
    "swe": "Swedish",
    "nor": "Norwegian",
    "dan": "Danish",
    "fin": "Finnish",
    "ces": "Czech",
    "ell": "Greek",
    "heb": "Hebrew",
    "tha": "Thai",
    "vie": "Vietnamese",
    "ind": "Indonesian",
    "mal": "Malay",
    "ukr": "Ukrainian",
    "ron": "Romanian",
    "hun": "Hungarian",
    "bul": "Bulgarian",
    "hrv": "Croatian",
    "slk": "Slovak",
    "slv": "Slovenian",
    "est": "Estonian",
    "lav": "Latvian",
    "lit": "Lithuanian",
    "cat": "Catalan",
    "glg": "Galician",
    "eus": "Basque",
    "isl": "Icelandic",
    "mkd": "Macedonian",
    "sqi": "Albanian",
    "bel": "Belarusian",
    "kat": "Georgian",
    "hye": "Armenian",
    "kaz": "Kazakh",
    "uzb": "Uzbek",
    "tgl": "Tagalog",
    "msa": "Malay",
    "tam": "Tamil",
    "tel": "Telugu",
    "kan": "Kannada",
    "mal": "Malayalam",
    "guj": "Gujarati",
    "pan": "Punjabi",
    "ori": "Odia",
    "beng": "Bengali",
    "mya": "Burmese",
    "khm": "Khmer",
    "lao": "Lao",
    "sin": "Sinhala",
    "amh": "Amharic",
    "tir": "Tigrinya",
    "or": "Oriya",
    "as": "Assamese",
    "mr": "Marathi",
    "sa": "Sanskrit",
    "ur": "Urdu",
    "fa": "Persian",
    "ps": "Pashto",
    "ku": "Kurdish",
    "ug": "Uyghur",
    "bo": "Tibetan",
    "dz": "Dzongkha",
    "ti": "Tigrinya",
    "rw": "Kinyarwanda",
    "wo": "Wolof",
    "yo": "Yoruba",
    "ig": "Igbo",
    "zu": "Zulu",
    "af": "Afrikaans",
    "sq": "Albanian",
    "ca": "Catalan",
    "eo": "Esperanto",
    "la": "Latin",
    "mi": "Maori",
    "sm": "Samoan",
    "sn": "Shona",
    "so": "Somali",
    "sw": "Swahili",
    "ts": "Tsonga",
    "xh": "Xhosa",
    "ny": "Chichewa",
    "mg": "Malagasy",
    "eo": "Esperanto",
    "fy": "Frisian",
    "gd": "Scottish Gaelic",
    "ht": "Haitian Creole",
    "jv": "Javanese",
    "ku": "Kurdish",
    "lb": "Luxembourgish",
    "mt": "Maltese",
    "ne": "Nepali",
    "pa": "Punjabi",
    "si": "Sinhala",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
    "yi": "Yiddish",
}


def _lang_label(code: str) -> str:
    return _LANG_NAMES.get(code, code)


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
        return [ModelInfo(f"tesseract:{lang}", self.name, _lang_label(lang)) for lang in sorted(langs)]

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
