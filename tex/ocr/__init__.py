from __future__ import annotations

from tex.ocr.gemini import GeminiEngine
from tex.ocr.openai_compat import CerebrasEngine, GroqEngine, OpenRouterEngine
from tex.ocr.tesseract_local import TesseractEngine

_ENGINE_IDS = ("tesseract", "gemini", "groq", "cerebras", "openrouter")


def engine_items() -> list[tuple[str, str]]:
    return [
        ("tesseract", "Tesseract (offline)"),
        ("gemini", "Google Gemini"),
        ("groq", "Groq"),
        ("cerebras", "Cerebras"),
        ("openrouter", "OpenRouter"),
    ]


def make_engine(name: str):
    if name == "tesseract":
        from tex import config

        return TesseractEngine(config.load_config().get("tesseract", {}))
    if name == "gemini":
        return GeminiEngine()
    if name == "groq":
        return GroqEngine()
    if name == "cerebras":
        return CerebrasEngine()
    if name == "openrouter":
        return OpenRouterEngine()
    raise KeyError(f"unknown engine: {name}")
