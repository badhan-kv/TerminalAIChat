# TerminalAIChat (mistralBot)

A free, terminal-based AI chat tool for PowerShell, powered by Mistral's free API tier, with optional live web-search grounding via Tavily.

**Platform:** Windows / PowerShell only (uses `%LOCALAPPDATA%` for config storage and a PowerShell profile function for the `mistralbot` launch command).

## Features
- Streaming, markdown-rendered replies in the terminal (via `rich`).
- Automatic web-search grounding when the model decides it needs current info, plus a manual `/search <query>` override (via Tavily).
- Multi-turn in-session memory, with every session logged to `history/` so you can browse, search, and resume past chats.
- Slash-command autocomplete (type `/` for a live dropdown).
- Model/token switching mid-chat (`/model`, `/max-tokens`).
- Local file access: `/read <path>` loads a file (including PDFs, converted to text locally) into chat context, `/ls <dir>` browses a directory first — both Tab-complete paths and are gated behind a one-time-per-session permission prompt.

Run `/help` in-chat or `python chat.py --help` for the full command reference, or see `HELP.md`.

## Publishing history

This project was originally published to GitHub on 13 July 2026. The repository
was deleted and re-published on 10 September 2026 to resolve a technical problem
with GitHub's cached repository metadata; the code and commit history are
otherwise unchanged.

## Prerequisites
- **Python 3** (3.10+) — check with `python --version`. Get it from [python.org](https://www.python.org/downloads/) if missing.
- **Git** — check with `git --version`. Get it from [git-scm.com](https://git-scm.com/downloads) if missing.
- **PowerShell** — comes with Windows.

## 1. Get your free API keys
Two keys are required, both free tier, neither requires a credit card:

1. **Mistral API key**
   - Go to [console.mistral.ai](https://console.mistral.ai) and sign up / sign in.
   - Your account defaults to **Free mode** (rate-limited, no card needed).
   - Go to **API Keys** in the console and generate a key. Copy it somewhere safe.
2. **Tavily API key** (powers live web-search grounding)
   - Go to [tavily.com](https://tavily.com) and sign up (email or Google/GitHub OAuth).
   - Your dashboard shows an API key immediately (starts with `tvly-`). Copy it.
   - Free tier: 1,000 search credits/month, recurring.

See `GETTING_API_KEYS.md` for more detail and sourcing notes on these limits.

You'll paste both keys in when you first run the app (step 3 below) — no need to set them as environment variables yourself.

## 2. Clone and set up
```powershell
git clone https://github.com/badhan-kv/TerminalAIChat.git
cd TerminalAIChat
.\setup.ps1
```
`setup.ps1` does two things:
- Installs Python dependencies (`pip install -r requirements.txt`).
- Adds a `mistralbot` function to your PowerShell profile (`$PROFILE`), pointing at this clone, so you can launch the app from any directory afterwards. Safe to re-run — it won't add a duplicate.

If you'd rather not touch your PowerShell profile, skip `setup.ps1` and just run `pip install -r requirements.txt` — you can still launch with `python chat.py` from inside the project folder.

## 3. First run
Open a **new** PowerShell window (so the profile change takes effect), then from anywhere:
```powershell
mistralbot
```
(or `python chat.py` if you skipped the profile setup, from inside the project folder).

First run prompts for your Mistral and Tavily API keys (input hidden) and caches them under `%LOCALAPPDATA%\mistralBot\config.json`, so you won't be asked again on later runs. Use `/logout` in-chat to clear cached keys and re-enter them.

## Everyday use
```powershell
mistralbot                       # start a chat
mistralbot --model ministral-3b-latest
mistralbot --max-tokens 2048
```
Type `/help` in-chat for the full command list, or see `HELP.md`.

## Setting up on another machine
Repeat steps 1–3 above on the new machine — each machine keeps its own cached API keys and its own `mistralbot` profile function pointing at wherever you cloned the repo there.

## Updating an existing install
From inside the cloned folder:
```powershell
git pull
pip install -r requirements.txt
```
This only touches files tracked in the repo. Anything machine-local and outside the repo — cached API keys (`%LOCALAPPDATA%\mistralBot\config.json`), session history (`history/`), and unrelated local machine settings (e.g. a root certificate under `Documents\`) — is untouched by `git pull`, so there's nothing to back up first. If you have uncommitted edits to a tracked file on that machine, run `git status` before pulling; `git pull` will refuse to overwrite them rather than silently discarding anything.

## License
MIT — see `LICENSE`.
