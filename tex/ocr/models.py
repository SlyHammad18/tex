from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    label: str = ""


def short_model(model_id: str) -> str:
    mid = model_id
    if mid.startswith("models/"):
        mid = mid[len("models/"):]
    if "/" in mid:
        mid = mid.rsplit("/", 1)[1]
    return mid


@dataclass
class OcrResult:
    text: str = ""
    model: str = ""
    provider: str = ""
    error: str | None = None
    latency_ms: int = 0
    usage: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text.strip())
