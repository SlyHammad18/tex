from __future__ import annotations

import json
import os
import stat
from pathlib import Path
import tomllib

try:
    import tomli_w
except ImportError:  # pragma: no cover
    tomli_w = None

from tex.constants import KEYRING_SERVICE, PROVIDERS

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "tex"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "Tex"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "tex"
CONFIG_FILE = CONFIG_DIR / "config.toml"
KEYS_FILE = CONFIG_DIR / "keys.json"

DEFAULTS: dict = {
    "general": {"engine": "tesseract", "history_size": 30},
    "tesseract": {"language": "eng", "upscale": 2},
    "providers": {name: {"model": ""} for name in PROVIDERS},
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    return _deep_merge(DEFAULTS, data)


def save_config(cfg: dict) -> None:
    if tomli_w is None:
        raise RuntimeError("tomli-w is required to write config.toml")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(cfg, f)


def _try_keyring_get(provider: str) -> str | None:
    import keyring

    return keyring.get_password(KEYRING_SERVICE, provider)


def _try_keyring_set(provider: str, value: str | None) -> None:
    import keyring

    if value:
        keyring.set_password(KEYRING_SERVICE, provider, value)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, provider)
        except Exception:
            pass


def _read_keys_file() -> dict:
    if not KEYS_FILE.exists():
        return {}
    try:
        return json.loads(KEYS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_keys_file(keys: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KEYS_FILE.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    KEYS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


def get_key(provider: str) -> str | None:
    env = PROVIDERS[provider]["key_env"]
    val = os.environ.get(env)
    if val:
        return val
    try:
        val = _try_keyring_get(provider)
        if val:
            return val
    except Exception:
        pass
    return _read_keys_file().get(provider) or None


def set_key(provider: str, value: str | None) -> None:
    value = (value or "").strip() or None
    try:
        _try_keyring_set(provider, value)
        keys = _read_keys_file()
        if provider in keys:
            del keys[provider]
            _write_keys_file(keys)
        return
    except Exception:
        pass
    keys = _read_keys_file()
    if value:
        keys[provider] = value
    elif provider in keys:
        del keys[provider]
    _write_keys_file(keys)
