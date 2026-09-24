from __future__ import annotations

import time

import requests

from tex.config import get_key
from tex.constants import PROVIDERS, TIMEOUT_HTTP, VISION_HINTS
from tex.ocr.base import OcrEngine, OcrError, encode_image, strip_fences
from tex.ocr.models import ModelInfo, OcrResult, short_model


class OpenAICompatEngine(OcrEngine):
    def __init__(self, provider: str):
        self.provider = provider
        self.meta = PROVIDERS[provider]
        self.name = provider
        self.label = self.meta["label"]

    def available(self) -> bool:
        return get_key(self.provider) is not None

    def _headers(self) -> dict:
        headers = {"Authorization": f"Bearer {get_key(self.provider)}"}
        headers.update(self.meta.get("extra_headers", {}))
        return headers

    @staticmethod
    def _is_vision(m: dict) -> bool:
        arch = m.get("architecture") or {}
        mods = arch.get("input_modalities")
        if mods:
            return "image" in mods
        mid = (m.get("id") or "").lower()
        return any(h in mid for h in VISION_HINTS)

    def _fallback(self, ids: list[str]) -> list[ModelInfo]:
        out = []
        for fb in self.meta["fallback_models"]:
            if any(fb in i for i in ids):
                out.append(ModelInfo(fb, self.provider, short_model(fb)))
        return out or [ModelInfo(fb, self.provider, short_model(fb)) for fb in self.meta["fallback_models"]]

    def list_models(self) -> list[ModelInfo]:
        if not self.available():
            raise OcrError(f"No API key set for {self.label} (Settings > API keys)")
        r = requests.get(f"{self.meta['base_url']}/models", headers=self._headers(), timeout=TIMEOUT_HTTP)
        if r.status_code != 200:
            raise OcrError(f"{self.label} {r.status_code}: {r.text[:300]}")
        data = r.json().get("data", [])
        ids = [m.get("id", "") for m in data]
        models = [ModelInfo(m["id"], self.provider, short_model(m["id"])) for m in data if self._is_vision(m)]
        if not models:
            models = self._fallback(ids)
        return sorted(models, key=lambda m: m.id.lower())

    def extract(self, image, model_id: str, prompt: str) -> OcrResult:
        mime, b64 = encode_image(image)
        payload = {
            "model": model_id,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ],
        }
        t0 = time.perf_counter()
        r = requests.post(
            f"{self.meta['base_url']}/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=TIMEOUT_HTTP,
        )
        latency = int((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            raise OcrError(f"{self.label} {r.status_code}: {r.text[:300]}")
        j = r.json()
        try:
            text = j["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as e:
            raise OcrError(f"{self.label}: unexpected response shape: {j}") from e
        return OcrResult(
            text=strip_fences(text.strip()),
            model=model_id,
            provider=self.provider,
            latency_ms=latency,
            usage=dict(j.get("usage") or {}),
        )


class GroqEngine(OpenAICompatEngine):
    def __init__(self):
        super().__init__("groq")


class CerebrasEngine(OpenAICompatEngine):
    def __init__(self):
        super().__init__("cerebras")


class OpenRouterEngine(OpenAICompatEngine):
    def __init__(self):
        super().__init__("openrouter")
