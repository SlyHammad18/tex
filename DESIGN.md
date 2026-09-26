# Tex — Design Document

**Tex** · Screenshot capture + AI text extraction for Linux
Version: 0.1 (design) · Platform: Debian/Ubuntu-class Linux, X11 + Wayland · License: MIT

---

## 1. Description

Tex is a lightweight Linux screenshot utility in the spirit of Debian's GNOME Screenshot, with AI-powered text extraction built in. The user captures a **region (selection)**, a **window**, or the **full screen**, then extracts text from the capture in two ways:

- **Offline** — Tesseract OCR, fully local, zero network.
- **Online** — free-tier vision models from **Gemini**, **Groq**, **Cerebras**, and **OpenRouter**. Tex auto-lists every vision-capable model each API key has access to. The default behavior is plain text extraction ("just get the text"); users can supply a **custom prompt**.

Tex ships as a standalone window app plus CLI flags (`tex --select`, `--window`, `--screen`) for keyboard shortcuts and scripting.

---

## 2. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-1 | Three capture modes: **Selection** (drag rectangle), **Window** (hover/pick — native on X11, falls back to region crop on Wayland), **Full Screen** (multi-monitor aware). |
| FR-2 | Post-capture re-crop: the captured image can be re-cropped before extraction on any backend. |
| FR-3 | Offline OCR via Tesseract: language picker populated from `tesseract --list-langs`, Pillow preprocessing (grayscale → autocontrast → optional 2× upscale → binarize). |
| FR-4 | Online OCR via Gemini / Groq / Cerebras / OpenRouter: one adapter per provider; on key entry, fetch the provider's model list and show **only vision-capable models** (filtered by `architecture.input_modalities` where the API exposes it, curated fallback list otherwise). |
| FR-5 | Default extraction prompt is fixed ("extract only the text"); user can toggle a **custom prompt** field per run. |
| FR-6 | Result actions: copy to clipboard, save as `.txt`, re-run extraction, re-crop image. Image preview panel alongside the text result. |
| FR-8 | History: recent captures (thumbnail, timestamp, engine used, result) persisted under `~/.local/share/Tex/`; click to reopen and re-extract. |
| FR-9 | Settings dialog: API key per provider, default engine + model, Tesseract language, history size, keyring integration with secure-file fallback. |
| FR-10 | CLI: `tex [--select|--window|--screen] [--engine tesseract\|gemini\|groq\|cerebras\|openrouter] [--model ID] [--prompt TEXT] [--clipboard] [--save PATH]`; bare `tex` opens the main window. |
| FR-11 | All errors surface as in-app toasts (missing key, network timeout, provider error, no text found); extraction is cancelable while running. |
| FR-12 | Single instance: a second launch with flags routes its arguments to the running instance (QLocalServer) or exits cleanly. |

---

## 3. Non-Functional Requirements

- **Responsiveness** — The UI thread never blocks. All network calls and Tesseract runs execute in worker threads (QThreadPool + Qt signals); the capture overlay paints at interactive rates.
- **Privacy** — Offline mode performs zero network I/O. Online runs are visibly labeled with provider and model name. Keys never leave the machine except to their own provider.
- **Security** — API keys stored via the OS keyring (SecretService) when available; fallback file `~/.config/tex/keys.json` created with `chmod 600`. Keys are never logged.
- **Robustness** — 30 s HTTP timeout per request, no silent retries, provider error bodies surfaced verbatim in toasts and logs. Graceful degradation: no `tesseract` binary → offline engine hidden; no portal on Wayland → actionable error message.
- **Performance** — Cold start < 1 s. Captures held in RAM (PIL image, lazy QPixmap). History thumbnails downscaled to ~200 px.
- **Resource footprint** — Minimal dependencies, no Electron/Node runtime; the app is a Python package plus the system `tesseract-ocr` binary.
- **Maintainability** — One shared OpenAI-compatible client covers Groq, Cerebras, and OpenRouter; all engines sit behind a single `OcrEngine` ABC; results are typed dataclasses.
- **Logging** — Rotating log under `~/.local/state/tex/log/` (DEBUG for local operations; provider URLs logged, never keys or auth headers).

---

## 4. Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.11+ | Best OCR/AI ecosystem, fastest to build |
| GUI | **PySide6** (Qt Widgets + QSS) | Native feel, powerful overlay/drag interactions, no web runtime |
| X11 capture | **mss** + **python-xlib** (EWMH window enumeration) | Fast multi-monitor grabs; real window picking |
| Wayland capture | **dbus-next** → `org.freedesktop.portal.Screenshot` (interactive for selection, non-interactive otherwise); optional `grim`/`slurp` fast-path on wlroots compositors | The only portable Wayland path |
| OCR (offline) | **pytesseract** + system `tesseract-ocr` | Industry-standard local OCR |
| OCR preprocessing | **Pillow** (grayscale, autocontrast, resize, threshold) | Keeps dependencies light — no OpenCV/numpy |
| HTTP | **requests** (synchronous, inside worker threads) | Simple; sync-in-thread beats asyncio complexity here |
| Keyring | **keyring** (optional extra) | SecretService integration |
| Config | **TOML** (`tomllib` stdlib on 3.11) at `~/.config/tex/config.toml` | Human-editable |
| Tests | **pytest** (+ `responses` for HTTP mocking) | Standard |
| Packaging | **pyproject.toml** + `.desktop` entry + hicolor SVG icon; `pip install .` | Debian-friendly |

> Groq, Cerebras, and OpenRouter are all OpenAI-compatible → one `openai_compat.py` client parametrized by base URL, auth, and vision filter. Only Gemini needs bespoke code (its `generateContent` REST API).

---

## 5. File Structure

```
Tex/
├── DESIGN.md
├── README.md
├── LICENSE
├── pyproject.toml
├── data/
│   ├── tex.desktop
│   └── icons/hicolor/scalable/apps/tex.svg
├── tex/
│   ├── __init__.py            # __version__
│   ├── __main__.py            # python -m tex
│   ├── app.py                 # QApplication bootstrap, single-instance, QSS load
│   ├── cli.py                 # argparse → CaptureMode / OcrRequest
│   ├── config.py              # config.toml load/save, keyring + keys.json fallback, paths
│   ├── constants.py           # default prompt, provider metadata, paths
│   ├── workers.py             # QRunnable extraction jobs + Signals
│   ├── capture/
│   │   ├── __init__.py        # get_backend() → X11 or Wayland, by session probe
│   │   ├── base.py            # CaptureBackend ABC + geometry types
│   │   ├── x11.py             # mss grab; xlib EWMH window list & geometry
│   │   └── wayland.py         # portal Screenshot (interactive/non-interactive); grim fast-path
│   ├── ocr/
│   │   ├── __init__.py        # registry: name → engine class; fallback vision-model lists
│   │   ├── base.py            # OcrEngine ABC: list_models(), extract() → OcrResult
│   │   ├── models.py          # OcrResult, ModelInfo dataclasses
│   │   ├── tesseract_local.py # offline engine
│   │   ├── openai_compat.py   # shared client: Groq, Cerebras, OpenRouter
│   │   └── gemini.py          # generateContent REST adapter
│   └── ui/
│       ├── main_window.py     # mode cards, history list, result hosting
│       ├── capture_overlay.py # fullscreen translucent drag-select overlay
│       ├── result_panel.py    # image preview + text view + actions
│       ├── settings_dialog.py # keys, defaults, tesseract languages
│       ├── history.py         # list widget + persistence
│       ├── toasts.py          # transient notification widget
│       └── theme.py           # palette constants + QSS stylesheet
└── tests/
    ├── test_config.py
    ├── test_geometry.py
    └── test_ocr_adapters.py   # mocked HTTP: model filtering, request/response shapes
```

---

## 6. Architecture

### 6.1 Capture flow

```
Mode picked (UI card or CLI flag)
  → backend = get_backend()        # probe XDG_SESSION_TYPE / WAYLAND_DISPLAY
  → X11:
      fullscreen: mss grab of the full virtual screen (multi-monitor)
      window:     python-xlib EWMH window list → hover-pick → window geometry → crop
      selection:  capture_overlay (translucent, always-on-top) → drag rect → crop
  → Wayland:
      selection:  portal Screenshot with interactive=true (compositor's native select UI);
                  wlroots + grim/slurp installed → grim -o <output> + slurp fast-path
      fullscreen: portal Screenshot (non-interactive)
      window:     portal full grab → selection overlay crop (documented fallback)
  → CaptureResult { PIL.Image, source_label, monitor/geometry }
```

### 6.2 Extraction flow

```
OcrRequest { image, engine, model, prompt }
  → workers.ExtractWorker (QThreadPool, one job per model)
      tesseract:     Pillow preprocess → pytesseract.image_to_string(lang)
      gemini:        POST v1beta/models/{id}:generateContent  (inline_data, base64)
      openai_compat: POST {base_url}/chat/completions         (image_url = data:image/png;base64,…)
  → emits finished(model, OcrResult { text, latency_ms, usage, error }) per model
  → UI: single run → ResultPanel text view
```

### 6.3 Default prompt (`constants.py`)

> "Extract all text from this image exactly as written. Preserve reading order and line breaks. Output only the extracted text — no commentary, no markdown fences."

---

## 7. Theme & UI Design

**Dark-first, single theme in v1.** Quiet, flat, tool-like — closer to Flameshot's polish than a dashboard.

### 7.1 Palette

| Token | Hex | Use |
|-------|-----|-----|
| `bg` | `#101318` | window background |
| `surface` | `#171B22` | panels, result area |
| `card` | `#1D232C` | mode cards, inputs, tabs |
| `border` | `#2A313D` | 1 px outlines |
| `text` | `#E6EAF0` | primary text |
| `muted` | `#8B93A1` | secondary labels |
| `accent` | `#4CC2FF` | primary buttons, selection border, active tab |
| `ok` | `#7EE787` | success toast, "copied" state |
| `err` | `#FF6B6B` | errors |
| overlay dim | `rgba(0,0,0,0.45)` | selection backdrop |

### 7.2 Shape & typography

- 8 px spacing grid; 10 px radius on cards, 6 px on buttons/inputs; 1 px `border` outlines.
- System font (Cantarell/Ubuntu) 10 pt; extracted text rendered in monospace — `"JetBrains Mono", "DejaVu Sans Mono", monospace`.
- Icons: inline SVG (marquee / window / monitor / gear / copy) bundled in code or `data/` — no icon-theme dependency.

### 7.3 Main window (~860×560, min 720×480)

```
┌ Tex ────────────────────────────────────────────── ⚙ ─┐
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ ▭ Select │  │ ▢ Window │  │ ▦ Screen │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│  ┌ Recent ────────────────────────────────────────┐   │
│  │ [thumb] 14:02 · Selection · gemini-2.0-flash   │   │
│  └────────────────────────────────────────────────┘   │
│  status bar: engine · model · Ready                   │
└───────────────────────────────────────────────────────┘
```

After a capture the window swaps to the **Result view**:

- **Left:** scaled image preview.
- **Right:** engine bar — `Tesseract ▾ | provider ▾ | model ▾ | ☐ Custom prompt | [Extract]` — then the text panel, then a toolbar: Copy · Save .txt · Re-crop · Back.

### 7.4 Selection overlay

Fullscreen borderless translucent Qt window: crosshair cursor, dimmed backdrop, rubber-band rectangle with a 2 px `accent` border and 8 corner handles, live `W × H` tooltip, **Esc** cancels, mouse release confirms.

---

## 8. Task Breakdown

### T1 — Scaffold & shell
Files: `pyproject.toml`, `tex/{__init__,__main__,app,cli,config,constants}.py`, `ui/theme.py`, stub `ui/main_window.py`.
Acceptance: `python -m tex` opens a themed empty window; `tex --select` parses; `config.toml` round-trips; keyring-with-fallback key API works (unit-tested).

### T2 — Capture backends + overlay
Files: `capture/*`, `ui/capture_overlay.py`.
Acceptance: on X11 — selection, true window picking, multi-monitor fullscreen; on Wayland/GNOME — portal-based selection + fullscreen; Esc/cancel paths clean; captured image lands in the Result view.

### T3 — Offline OCR
Files: `ocr/base.py`, `ocr/models.py`, `ocr/tesseract_local.py`, `workers.py`.
Acceptance: screenshot → text in a worker thread; language dropdown from `--list-langs`; cancel works; missing tesseract binary hides the offline engine.

### T4 — Online providers
Files: `ocr/openai_compat.py`, `ocr/gemini.py`, `ocr/__init__.py` (registry + fallback vision lists).
Acceptance: with a real free key per provider — vision-only model list populates; default extraction returns clean text; wrong key / timeout → toast with the provider's error; mocked tests cover model filtering and request shapes.

### T5 — Result UI
Files: `ui/result_panel.py`, `ui/toasts.py`.
Acceptance: extract / copy / save / re-crop / re-run; custom-prompt toggle.

### T6 — Settings, history, polish
Files: `ui/settings_dialog.py`, `ui/history.py`, single-instance logic in `app.py`, CLI flags end-to-end.
Acceptance: keys editable per provider and persisted safely; history reopens captures; `tex --screen --engine groq --model … --clipboard` works; second instance defers to the first.

### T7 — Packaging, docs, tests
Files: `data/tex.desktop`, icon SVG, `README.md`, `tests/*`.
Acceptance: `pip install .` + desktop entry launch cleanly; pytest green; README covers install (the `tesseract-ocr` apt dependency), API keys for all four providers, and Wayland caveats (portal permission prompt, window-mode crop fallback).

---

## 9. Verification

1. **X11 session** — all three modes; window titles correct; multi-monitor grab spans correctly.
2. **Wayland session (GNOME)** — portal prompt appears (once, then remembered); interactive selection works; window-mode crop fallback documented.
3. **OCR matrix** — Tesseract with 2 languages; one real model per provider (Gemini flash, Groq llama-4-scout, Cerebras llama-4, an OpenRouter `:free` vision model).
4. **Failure paths** — revoked key, airplane-mode online attempt, cancel mid-extraction, empty (solid-color) image → graceful toasts everywhere.
5. **CLI** — every flag combination from FR-10; single-instance behavior.
6. **Security** — `stat -c %a` on the fallback keys file = `600`; keys absent from logs.
7. **Tests** — full `pytest` run green.
