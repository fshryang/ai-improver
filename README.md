# AI Improver

[![GitHub Release](https://img.shields.io/badge/release-v0.1.0-blue)](https://github.com/fshryang/ai-improver/releases/tag/v0.1.0)
[![Downloads](https://img.shields.io/github/downloads/fshryang/ai-improver/latest/total)](https://github.com/fshryang/ai-improver/releases)

A Windows desktop app that watches your clipboard and instantly applies AI-powered editing rules to any text you copy. Inspired by Grammarly, but with a **no-AI-slop** prompt baked in — it cuts filler, removes em-dash abuse, and preserves your voice.

Built with **PySide6** (Qt) + provider-agnostic HTTP calls.

## Quick Install (click to download)

👉 **[AI-Improver.exe](https://github.com/fshryang/ai-improver/releases/download/v0.1.0/AI-Improver.exe)** — Windows 10/11 x64, no install needed

1. Download the `.exe` from the [Releases page](https://github.com/fshryang/ai-improver/releases)
2. Double-click to run (Windows may show a SmartScreen warning — click **More info → Run anyway**)
3. Right-click the ✦ tray icon → **Settings…** → paste your API key → **Save**
4. Start using it. That's it.

## Features

- **Clipboard watcher** — select any text, press `Ctrl+C`, a tiny "✦ Improve" badge pops up near your cursor
- **Dual-pane editor** — original on the left (read-only), AI-improved on the right (editable)
- **Diff highlighting**
  - 🔴 Red + strikethrough = text removed by the AI
  - 🟢 Green background = text added by the AI
- **Selection sync** — select a sentence in either pane, the corresponding region in the other pane lights up yellow
- **Improve / Detect modes** — Improve rewrites; Detect only flags AI-slop patterns
- **Diff toggle** — turn highlighting on/off with one click
- **Settings dialog** — configure API keys, model, and base URL from within the app (no hand-editing JSON)
- **System tray** — minimize to tray, open editor on demand, quick quit

## No-AI-Slop Rules

Every AI call includes these system instructions:

1. Cut filler — remove hedging ("quite", "rather"), vague qualifiers, throat-clearing openers
2. Be direct — prefer active voice, concrete specifics over abstractions
3. Preserve voice — edit, don't homogenize the writer's idiom
4. Em-dash ban — never use `—` to set off explanations; rewrite with `-ing`, `-ed`, or `which` clauses
5. Flag AI-slop vocabulary — "delve", "tapestry", "navigate", etc.

## Supported Providers

| Provider | Model (default) | Protocol |
|----------|----------------|----------|
| DeepSeek | `deepseek-v4-flash` | OpenAI-compatible |
| OpenAI | `gpt-4o-mini` | OpenAI-compatible |
| Anthropic | `claude-3-5-haiku-latest` | Anthropic |
| Local (Ollama / LM Studio) | `llama3.1:8b` | OpenAI-compatible |

Adding a new provider = one Python file in `providers/` + one entry in `ai_engine.py`.

## Quick Start

### Run from source

```powershell
git clone https://github.com/fshryang/ai-improver.git
cd ai-improver
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Configure

1. Right-click the ✦ tray icon → **Settings…**
2. Pick your active provider (e.g. `deepseek`)
3. Paste your API key
4. Check the model and base URL (defaults are pre-filled)
5. Click **Save**

The app writes your config to `config.json` in the same directory as the executable. It is never committed to git.

### Use

1. Copy any text (`Ctrl+C`) — wait for the "✦ Improve" badge
2. Click the badge to open the editor
3. Review the diff — red = removed, green = added
4. Select text in either pane to see the counterpart highlighted
5. Click **Copy improved** to paste the result back wherever you need it

### Build a standalone .exe

```powershell
# Windows long paths must be enabled first (one-time, admin PowerShell):
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# Then:
pip install pyinstaller
pyinstaller --onefile --noconsole --name "AI-Improver" --collect-submodules PySide6 ^
  --hidden-import providers --hidden-import providers.openai_provider ^
  --hidden-import providers.anthropic_provider --hidden-import providers.local_provider main.py
```

The `.exe` lands in `dist/`. Drop it anywhere, run it, fill in your API key — done.

## Project Structure

```
ai-improver/
├── main.py                 # Entry point: QApplication + system tray
├── clipboard_watcher.py    # QThread that polls the Windows clipboard
├── sign_popup.py           # Frameless "✦ Improve" badge near cursor
├── editor_popup.py         # Dual-pane editor with diff + selection sync
├── ai_engine.py            # Abstract provider factory
├── prompts.py              # No-AI-Slop system prompts (improve / detect)
├── config.py               # JSON config loader / saver (auto-generates defaults)
├── settings_dialog.py      # In-app settings UI
├── providers/
│   ├── openai_provider.py  # OpenAI + DeepSeek + any OpenAI-compatible endpoint
│   ├── anthropic_provider.py
│   └── local_provider.py   # Ollama / LM Studio
├── config.example.json     # Template (empty keys — never commit your real config)
└── requirements.txt
```

## Privacy

- Your API key lives only in `config.json` on your local machine
- It is listed in `.gitignore` and will never be committed
- Clipboard text is sent only to whichever provider you configure — nothing else

## License

MIT
