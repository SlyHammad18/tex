# Tex

Screenshot capture with AI text extraction for Linux. Capture a selection, a
window, or the full screen, then extract text **offline** with Tesseract or
**online** with free-tier vision models from **Google Gemini**, **Groq**,
**Cerebras**, and **OpenRouter** — including a multi-model **compare mode**.

Dark, minimal UI built with Qt (PySide6). Works on X11 and Wayland.

## Features

- **Capture modes** — Selection (drag), Window (hover-pick on X11; crop
  fallback on Wayland), Full Screen (multi-monitor aware).
- **Offline OCR** — Tesseract with automatic preprocessing (grayscale,
  autocontrast, upscale) and language selection from installed packs.
- **Online OCR** — per-provider model lists filtered to vision-capable models;
  plain "extract the text" by default.
- **Custom prompt** — toggle a prompt field to ask anything of the image.
- **Compare mode** — send one capture to several models in parallel; results
  land in tabs with latency/token chips and per-tab copy, plus an "All" tab.
- **History** — recent captures with thumbnails; click to reopen and re-extract.
- **CLI** — `tex --select|--window|--screen` with optional headless-style
  auto-extraction for keybinds and scripts.
- **Single instance** — launching again routes flags to the running app.

## Install

System dependencies (Debian/Ubuntu):

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng          # offline OCR
# optional extra languages, e.g.: tesseract-ocr-deu tesseract-ocr-fra
```

On **Wayland**, Tex uses `xdg-desktop-portal` (GNOME/KDE ship it); on wlroots
compositors (sway, Hyprland…) it uses `grim` + `slurp` when available:

```bash
sudo apt install xdg-desktop-portal grim slurp   # as applicable
```

Install Tex:

```bash
pip install .
# with OS keyring support for API keys:
pip install .[keyring]
```

Run with `tex` or from your app grid.

## API keys

Get free keys and paste them in **Settings → API keys** (stored in your OS
keyring when available, otherwise `~/.config/tex/keys.json` with `0600`
permissions):

| Provider | Get a key | Environment variable |
|----------|-----------|----------------------|
| Google Gemini | https://aistudio.google.com/apikey | `GEMINI_API_KEY` |
| Groq | https://console.groq.com/keys | `GROQ_API_KEY` |
| Cerebras | https://cloud.cerebras.ai | `CEREBRAS_API_KEY` |
| OpenRouter | https://openrouter.ai/keys | `OPENROUTER_API_KEY` |

Environment variables override stored keys.

## Usage

Launch the window and pick a mode, or use flags:

```bash
tex                          # open the main window
tex --select                 # capture a region, then show the result view
tex --window                 # pick a window (X11 native, Wayland crop fallback)
tex --screen                 # capture the full screen
tex --select --engine groq --model meta-llama/llama-4-scout-17b-16e-instruct \
    --clipboard              # capture, extract, copy, exit
tex --select --engine tesseract --model tesseract:eng --save out.txt
tex --screen --engine openrouter --compare "meta-llama/llama-4-scout:free,google/gemini-2.0-flash-exp:free" --clipboard
```

Model ids: pick them from the model dropdown after entering a key, or pass
them explicitly. `--prompt "…"` replaces the default extraction prompt.

## Files & privacy

- `~/.config/tex/config.toml` — settings
- `~/.config/tex/keys.json` — key fallback (0600) when no keyring
- `~/.local/share/Tex/` — history captures + results
- `~/.local/state/tex/` — logs

Offline (Tesseract) mode never touches the network. Online mode sends the
image only to the provider you picked.

## Wayland notes

- The first capture triggers a desktop-portal permission prompt; approve
  (and "allow always") once.
- Window mode falls back to a crop selection over the full grab — portals do
  not expose window geometry on GNOME/KDE.
- On wlroots compositors with `grim`+`slurp`, selection uses slurp natively.

## Development

```bash
pip install -e .[dev]
pytest
```

Design details live in [DESIGN.md](DESIGN.md). MIT licensed.
