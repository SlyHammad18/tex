from __future__ import annotations

import datetime as _dt
import json
import uuid
from pathlib import Path

from tex import config
from tex.capture.base import CaptureMode

_FILE_NAME = "history.json"


class HistoryStore:
    def __init__(self):
        self._file = config.DATA_DIR / _FILE_NAME
        self._img_dir = config.DATA_DIR / "captures"

    def _load(self) -> list[dict]:
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, entries: list[dict]) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(entries, indent=1), encoding="utf-8")

    def entries(self) -> list[dict]:
        return self._load()

    def add(self, image, mode: CaptureMode, label: str = "") -> str:
        entry_id = uuid.uuid4().hex[:12]
        self._img_dir.mkdir(parents=True, exist_ok=True)
        img_path = self._img_dir / f"{entry_id}.png"
        image.save(img_path, format="PNG")
        entries = self._load()
        entries.insert(
            0,
            {
                "id": entry_id,
                "ts": _dt.datetime.now().isoformat(timespec="seconds"),
                "mode": mode.value,
                "label": label,
                "engine": "",
                "model": "",
                "text": "",
                "image": str(img_path),
            },
        )
        limit = int(config.load_config()["general"].get("history_size", 30) or 30)
        for old in entries[limit:]:
            try:
                Path(old["image"]).unlink(missing_ok=True)
            except Exception:
                pass
        self._save(entries[:limit])
        return entry_id

    def update(self, entry_id: str, engine: str, model: str, text: str) -> None:
        entries = self._load()
        for e in entries:
            if e["id"] == entry_id:
                e["engine"] = engine
                e["model"] = model
                e["text"] = text
                break
        self._save(entries)

    def remove(self, entry_id: str) -> None:
        entries = self._load()
        for e in entries:
            if e["id"] == entry_id:
                try:
                    Path(e["image"]).unlink(missing_ok=True)
                except Exception:
                    pass
        self._save([e for e in entries if e["id"] != entry_id])


_store: HistoryStore | None = None


def get_store() -> HistoryStore:
    global _store
    if _store is None:
        _store = HistoryStore()
    return _store
