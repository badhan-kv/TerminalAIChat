# TerminalAIChat (mistralBot)

A free, terminal-based AI chat tool for PowerShell, powered by Mistral's free API tier, with optional live web-search grounding via Tavily.

## Features
- Streaming, markdown-rendered replies in the terminal (via `rich`).
- Automatic web-search grounding when the model decides it needs current info, plus a manual `/search <query>` override (via Tavily).
- Multi-turn in-session memory, with every session logged to `history/` so you can browse, search, and resume past chats.
- Slash-command autocomplete (type `/` for a live dropdown).
- Model/token switching mid-chat (`/model`, `/max-tokens`).

Run `/help` in-chat or `python chat.py --help` for the full command reference, or see `HELP.md`.

## Setup (any machine)
1. Install Python 3.
2. Clone this repo and `cd` into it:
   ```powershell
   git clone https://github.com/badhan-kv/TerminalAIChat.git
   cd TerminalAIChat
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Get free API keys (no credit card required for either) — see `GETTING_API_KEYS.md`:
   - Mistral API key from console.mistral.ai
   - Tavily API key from tavily.com
5. Run it:
   ```powershell
   python chat.py
   ```
   First run prompts for the two API keys and caches them under `%LOCALAPPDATA%\mistralBot\config.json` (Windows) so you won't be asked again. Use `/logout` in-chat to clear cached keys.

## Quick launch from any directory (PowerShell)
Add a `mistralbot` function to your PowerShell profile so you can just type `mistralbot` from anywhere instead of `cd`-ing into the project and running `python chat.py`:

```powershell
notepad $PROFILE   # creates the file if it doesn't exist yet
```

Add this, replacing the path with wherever you cloned the repo on *this* machine:

```powershell
function mistralbot {
    python "C:\path\to\TerminalAIChat\chat.py" @args
}
```

Save, open a new PowerShell window, and run `mistralbot` (or `mistralbot --max-tokens 2048`, etc.) from any directory.

## License
MIT — see `LICENSE`.
