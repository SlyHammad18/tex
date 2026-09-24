from __future__ import annotations

PROVIDERS: dict[str, dict] = {
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "key_env": "GEMINI_API_KEY",
        "key_url": "https://aistudio.google.com/apikey",
        "fallback_models": ["gemini-2.0-flash", "gemini-2.5-flash"],
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "key_url": "https://console.groq.com/keys",
        "fallback_models": [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
        ],
    },
    "cerebras": {
        "label": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "key_env": "CEREBRAS_API_KEY",
        "key_url": "https://cloud.cerebras.ai",
        "fallback_models": [
            "llama-4-scout-17b-16e-instruct",
            "llama-4-maverick-17b-128e-instruct",
        ],
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "key_url": "https://openrouter.ai/keys",
        "extra_headers": {
            "HTTP-Referer": "https://github.com/tex-capture/tex",
            "X-Title": "Tex",
        },
        "fallback_models": [
            "meta-llama/llama-4-scout:free",
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen2.5-vl-72b-instruct:free",
        ],
    },
}

VISION_HINTS = ("vision", "-vl", "llama-4", "gemini", "gpt-4", "pixtral", "qwen")

DEFAULT_PROMPT = (
    "Extract all text from this image exactly as written. Preserve reading "
    "order and line breaks. Output only the extracted text - no commentary, "
    "no markdown fences."
)

TIMEOUT_HTTP = 30
PORTAL_TIMEOUT = 120

KEYRING_SERVICE = "tex"
