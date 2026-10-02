from __future__ import annotations

import time

import requests

from tex.config import get_key
from tex.constants import PROVIDERS, TIMEOUT_HTTP
from tex.ocr.base import ANSWER_PROMPT, GROUP_PROMPT, TRANSLATE_PROMPT, OcrEngine, OcrError, encode_image, strip_fences
from tex.ocr.models import ModelInfo, OcrResult, short_model

_EXCLUDE = (
    "embedding",
    "aqa",
    "imagen",
    "veo",
    "tts",
    "image-generation",
    "native-audio",
    "learnlm",
)


class GeminiEngine(OcrEngine):
    name = "gemini"

    def __init__(self):
        self.meta = PROVIDERS["gemini"]
        self.label = self.meta["label"]

    def available(self) -> bool:
        return get_key("gemini") is not None

    def _key(self) -> str:
        key = get_key("gemini")
        if not key:
            raise OcrError(f"No API key set for {self.label} (Settings > API keys)")
        return key

    def list_models(self) -> list[ModelInfo]:
        key = self._key()
        r = requests.get(
            f"{self.meta['base_url']}/models",
            params={"key": key},
            timeout=TIMEOUT_HTTP,
        )
        if r.status_code != 200:
            raise OcrError(f"{self.label} {r.status_code}: {r.text[:300]}")
        out: list[ModelInfo] = []
        for m in r.json().get("models", []):
            mid = (m.get("name") or "").removeprefix("models/")
            methods = m.get("supportedGenerationMethods") or []
            if "generateContent" not in methods:
                continue
            low = mid.lower()
            if any(x in low for x in _EXCLUDE):
                continue
            out.append(ModelInfo(mid, "gemini", short_model(mid)))
        return sorted(out, key=lambda m: (0 if "flash" in m.id.lower() else 1, m.id.lower()))

    def extract(self, image, model_id: str, prompt: str) -> OcrResult:
        key = self._key()
        mime, b64 = encode_image(image)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": b64}},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0},
        }
        t0 = time.perf_counter()
        r = requests.post(
            f"{self.meta['base_url']}/models/{model_id}:generateContent",
            params={"key": key},
            json=payload,
            timeout=TIMEOUT_HTTP,
        )
        latency = int((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            raise OcrError(f"{self.label} {r.status_code}: {r.text[:300]}")
        j = r.json()
        cands = j.get("candidates") or []
        if not cands:
            reason = (j.get("promptFeedback") or {}).get("blockReason", "no candidates returned")
            raise OcrError(f"{self.label}: {reason}")
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        um = j.get("usageMetadata") or {}
        usage = {
            "prompt_tokens": um.get("promptTokenCount", 0),
            "completion_tokens": um.get("candidatesTokenCount", 0),
            "total_tokens": um.get("totalTokenCount", 0),
        }
        return OcrResult(
            text=strip_fences(text.strip()),
            model=model_id,
            provider="gemini",
            latency_ms=latency,
            usage=usage,
        )

    def _complete(self, prompt: str, model_id: str) -> str:
        key = self._key()
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        r = requests.post(
            f"{self.meta['base_url']}/models/{model_id}:generateContent",
            params={"key": key},
            json=payload,
            timeout=TIMEOUT_HTTP,
        )
        if r.status_code != 200:
            raise OcrError(f"{self.label} {r.status_code}: {r.text[:300]}")
        j = r.json()
        cands = j.get("candidates") or []
        if not cands:
            reason = (j.get("promptFeedback") or {}).get("blockReason", "no candidates returned")
            raise OcrError(f"{self.label}: {reason}")
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)

    def group_text(self, text: str, model_id: str) -> str:
        return self._complete(GROUP_PROMPT + text, model_id)

    def translate_text(self, text: str, model_id: str) -> str:
        return self._complete(TRANSLATE_PROMPT + text, model_id)

    def answer_text(self, text: str, model_id: str) -> str:
        return strip_fences(self._complete(ANSWER_PROMPT + text, model_id).strip())
