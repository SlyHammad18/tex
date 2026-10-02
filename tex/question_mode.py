from __future__ import annotations

import subprocess
import sys

from tex import config
from tex.capture import grab_raw
from tex.ocr import make_engine
from tex.ocr.base import ANSWER_PROMPT, OcrError, QUESTION_EXTRACT_PROMPT


def _notify(title: str, body: str) -> None:
    try:
        subprocess.run(
            ["notify-send", "-a", "Tex", title, body],
            timeout=6,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _pick_model(engine, args_model: str) -> str:
    if args_model:
        return args_model
    saved = (config.load_config().get("providers", {}).get(engine.name, {}).get("model") or "").strip()
    if saved:
        return saved
    models = engine.list_models()
    if not models:
        raise OcrError(f"no models found for {engine.label}")
    return models[0].id


def run_question_mode(args_model: str = "", args_engine: str = "") -> int:
    cfg = config.load_config()
    engine_name = args_engine or cfg.get("general", {}).get("engine", "")
    if not engine_name or engine_name == "tesseract":
        _notify("Tex", "Question mode needs an AI engine (--engine gemini/groq/cerebras/openrouter)")
        print("question mode requires an AI engine", file=sys.stderr)
        return 2

    try:
        engine = make_engine(engine_name)
        if not engine.available():
            raise OcrError(f"No API key set for {engine.label} (Settings > API keys)")
        model_id = _pick_model(engine, args_model)

        image, _windows, _origin = grab_raw()
        extracted = engine.extract(image, model_id, QUESTION_EXTRACT_PROMPT)
        question = (extracted.text or "").strip()
        if extracted.error:
            raise OcrError(extracted.error)
        if not question:
            raise OcrError("no text found in the screenshot")

        answer = engine.answer_text(question, model_id).strip()
        if not answer:
            raise OcrError("the model returned no answer")
    except Exception as e:
        _notify("Tex question mode failed", str(e))
        print(f"question mode failed: {e}", file=sys.stderr)
        return 1

    _notify(question[:80], answer)
    print(answer)
    return 0
