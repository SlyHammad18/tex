import json

import pytest

from tex import config


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config" / "config.toml")
    monkeypatch.setattr(config, "KEYS_FILE", tmp_path / "config" / "keys.json")
    return tmp_path


def test_config_round_trip(paths):
    cfg = config.load_config()
    assert cfg["general"]["engine"] == "tesseract"
    assert set(cfg["providers"].keys()) == {"gemini", "groq", "cerebras", "openrouter"}
    cfg["general"]["engine"] = "groq"
    cfg["tesseract"]["language"] = "deu"
    config.save_config(cfg)
    reloaded = config.load_config()
    assert reloaded["general"]["engine"] == "groq"
    assert reloaded["tesseract"]["language"] == "deu"
    assert reloaded["general"]["history_size"] == 30


def test_key_fallback_file(paths, monkeypatch):
    monkeypatch.setattr(config, "_try_keyring_get", lambda p: None)
    monkeypatch.setattr(config, "_try_keyring_set", lambda p, v: (_ for _ in ()).throw(RuntimeError("no keyring")))
    config.set_key("gemini", "abc123")
    assert config.KEYS_FILE.exists()
    assert config.get_key("gemini") == "abc123"
    mode = config.KEYS_FILE.stat().st_mode & 0o777
    assert mode == 0o600
    raw = json.loads(config.KEYS_FILE.read_text())
    assert raw == {"gemini": "abc123"}
    config.set_key("gemini", None)
    assert config.get_key("gemini") is None


def test_key_env_wins(paths, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    assert config.get_key("groq") == "env-key"
