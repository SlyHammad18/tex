import base64
from unittest.mock import patch

import pytest

from tex.ocr.base import OcrError, strip_fences
from tex.ocr.gemini import GeminiEngine
from tex.ocr.openai_compat import OpenAICompatEngine
from tex.ocr.models import OcrResult, short_model


class Resp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = str(self._body)

    def json(self):
        return self._body


@pytest.fixture
def key():
    with patch("tex.ocr.openai_compat.get_key", return_value="k"), patch(
        "tex.ocr.gemini.get_key", return_value="k"
    ):
        yield


def test_vision_filter_by_architecture():
    eng = OpenAICompatEngine("groq")
    assert eng._is_vision({"id": "x", "architecture": {"input_modalities": ["text", "image"]}})
    assert not eng._is_vision({"id": "x", "architecture": {"input_modalities": ["text"]}})
    assert eng._is_vision({"id": "meta-llama/llama-4-scout-17b-16e-instruct"})
    assert not eng._is_vision({"id": "llama3-8b-8192"})


def test_openai_list_models_filters_and_sorts(key):
    eng = OpenAICompatEngine("openrouter")
    body = {
        "data": [
            {"id": "z/text-only", "architecture": {"input_modalities": ["text"]}},
            {"id": "a/vision-model", "architecture": {"input_modalities": ["text", "image"]}},
            {"id": "b/meta-llama/llama-4-scout:free", "architecture": {"input_modalities": ["text", "image"]}},
        ]
    }
    with patch("tex.ocr.openai_compat.requests.get", return_value=Resp(body=body)) as g:
        models = eng.list_models()
    assert [m.id for m in models] == ["a/vision-model", "b/meta-llama/llama-4-scout:free"]
    args, kwargs = g.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer k"
    assert kwargs["headers"]["X-Title"] == "Tex"


def test_openai_list_models_no_key():
    eng = OpenAICompatEngine("groq")
    with patch("tex.ocr.openai_compat.get_key", return_value=None):
        with pytest.raises(OcrError):
            eng.list_models()


def test_openai_extract_request_and_result(key):
    eng = OpenAICompatEngine("groq")
    body = {
        "choices": [{"message": {"content": "```text\nhello world\n```"}}],
        "usage": {"total_tokens": 42},
    }
    from PIL import Image

    img = Image.new("RGB", (10, 10), "white")
    with patch("tex.ocr.openai_compat.requests.post", return_value=Resp(body=body)) as p:
        result = eng.extract(img, "llama-4-scout", "extract text")
    assert result.ok and result.text == "hello world"
    assert result.usage["total_tokens"] == 42
    args, kwargs = p.call_args
    url = args[0]
    payload = kwargs["json"]
    assert url.endswith("/chat/completions")
    assert payload["model"] == "llama-4-scout"
    assert payload["temperature"] == 0
    content = payload["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "extract text"}
    data_uri = content[1]["image_url"]["url"]
    assert data_uri.startswith("data:image/png;base64,")
    base64.b64decode(data_uri.split(",", 1)[1])


def test_openai_error_raises(key):
    eng = OpenAICompatEngine("cerebras")
    from PIL import Image

    with patch("tex.ocr.openai_compat.requests.post", return_value=Resp(status=401, body={"error": "bad key"})):
        with pytest.raises(OcrError) as e:
            eng.extract(Image.new("RGB", (4, 4)), "m", "p")
    assert "401" in str(e.value)


def test_gemini_list_models_filters(key):
    eng = GeminiEngine()
    body = {
        "models": [
            {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/imagen-3.0-generate-002", "supportedGenerationMethods": ["predict"]},
            {"name": "models/gemini-1.5-flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
        ]
    }
    with patch("tex.ocr.gemini.requests.get", return_value=Resp(body=body)) as g:
        models = eng.list_models()
    ids = [m.id for m in models]
    assert ids == ["gemini-1.5-flash", "gemini-2.0-flash"]
    assert "key" in g.call_args.kwargs["params"]


def test_gemini_extract(key):
    eng = GeminiEngine()
    body = {
        "candidates": [{"content": {"parts": [{"text": "line one\nline two"}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
    }
    from PIL import Image

    with patch("tex.ocr.gemini.requests.post", return_value=Resp(body=body)) as p:
        result = eng.extract(Image.new("RGB", (8, 8)), "gemini-2.0-flash", "go")
    assert result.ok and result.text == "line one\nline two"
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    args, kwargs = p.call_args
    assert ":generateContent" in args[0]
    parts = kwargs["json"]["contents"][0]["parts"]
    assert parts[0] == {"text": "go"}
    assert parts[1]["inline_data"]["mime_type"] == "image/png"


def test_gemini_blocked(key):
    eng = GeminiEngine()
    from PIL import Image

    with patch("tex.ocr.gemini.requests.post", return_value=Resp(body={"promptFeedback": {"blockReason": "SAFETY"}})):
        with pytest.raises(OcrError) as e:
            eng.extract(Image.new("RGB", (4, 4)), "gemini-2.0-flash", "go")
    assert "SAFETY" in str(e.value)


def test_strip_fences():
    assert strip_fences("```text\nabc\n```") == "abc"
    assert strip_fences("plain") == "plain"
    assert strip_fences("```json\n{\"a\":1}\n```") == '{"a":1}'


def test_short_model():
    assert short_model("meta-llama/llama-4-scout") == "llama-4-scout"
    assert short_model("models/gemini-2.0-flash") == "gemini-2.0-flash"
    assert short_model("plain-id") == "plain-id"
