# mistralBot — Spec

A free, terminal-based AI chat tool for PowerShell, powered by Mistral's free API tier, with optional live web-search grounding via Tavily.

## Goals
- Mouse-free Q&A in the terminal.
- Grounded answers using live web search when needed.
- Zero cost: free-tier APIs only, no paid subscriptions.

## Stack
- **Language:** Python 3.
- **LLM:** Mistral La Plateforme free tier (`mistralai` SDK or raw HTTPS). Default model `mistral-small-latest`; override via `--model` flag or `/model <name>` in-chat.
- **Web search:** Tavily API (free tier, 1,000 credits/month, no credit card required — switched from Brave Search after verification showed Brave requires a card on file even for its free tier; see `GETTING_API_KEYS.md`).
- **Output rendering:** `rich` library — minimal styling similar to Claude Code's CLI: bold text/headers, fenced code blocks with syntax highlighting, muted color for metadata (e.g. token/search indicators), no heavy borders/boxes/tables unless content calls for it. Streamed token-by-token.
- **Input:** `prompt_toolkit` — replaces plain `input()` to support the live slash-command autocomplete dropdown.

## Grounding behavior
- **Automatic:** Mistral tool-calling exposes a `web_search` function; when the model decides a question needs current info, it calls the tool, we hit Tavily, feed snippets back, model produces grounded answer.
- **Manual override:** `/search <query>` forces a Tavily search and injects results into context before the next model call, regardless of whether the model would have asked for it.

## Chat session behavior
- Multi-turn memory kept in-process for the life of the session.
- Slash commands: `/search <q>`, `/model <name>`, `/max-tokens <n>`, `/history`, `/search-history "<text>"`, `/resume <n>`, `/delete-history contains "<text>"` / `/delete-history before <date>`, `/clear` (reset in-memory history), `/logout` (delete stored API keys), `/read <path>`, `/ls <dir>`, `/help`, `/exit`.
- Launch flags: `--model <name>`, `--max-tokens <n>`.
- Typing `/` shows a live autocomplete dropdown of matching commands (via `prompt_toolkit`), narrowing as you type more characters; Tab/Enter completes the selection.
- Each session's transcript is written to its own JSON file under `history/` (e.g. `history/2026-07-11_143000.json`) as it progresses, so a crash doesn't lose the log.
- History files persist indefinitely unless removed via `/delete-history` or manually — no automatic/age-based cleanup (a deliberate choice: history is treated as retrievable storage via `/history` / `/search-history` / `/resume`, not a cache to be silently pruned).

## Local file access
- `/read <path>` loads a file's contents into chat context (as a turn, once — not re-pinned on every later request); `/ls <dir>` lists a directory's contents to help pick a file. Both Tab-complete filesystem paths like a terminal (`/ls` offers directories only). Neither is restricted to the launch directory — any path the user can specify is fair game.
- Both commands are gated by a shared, session-scoped permission prompt (`1) Allow once  2) Allow this session  3) Deny`) that appears the first time either is used in a session. Nothing persists across sessions/restarts.
- `/read` does not trigger a model reply itself (state-setting, like `/model`/`/max-tokens`) — the user's next normal message is what asks about the loaded file.
- PDFs are converted to text locally via `pypdf` before injection; no document/image upload to Mistral. Other files are read as plain text with no size or type restriction — best-effort, garbled content on non-text files is an accepted tradeoff rather than building an allowlist.

## Credential handling
- First run: interactively prompt for `MISTRAL_API_KEY` and `TAVILY_API_KEY`.
- Keys are cached in a local config file under `%LOCALAPPDATA%\mistralBot\config.json` so subsequent PowerShell sessions don't re-prompt.
- `/logout` deletes that config file, forcing re-entry next run.
- **Caveat:** a plain local file can't truly auto-expire on reboot/shutdown without a background Windows service, which is out of scope for a simple CLI tool. The file persists until `/logout` is run or it's deleted manually. (Flagging this now since it differs slightly from "clears on reboot" — happy to revisit with a Windows Credential Manager–backed approach later if that matters to you.)

## Project layout (proposed)
```
mistralBot/
  chat.py              # entry point / REPL loop
  mistral_client.py    # Mistral API calls incl. tool-calling + streaming
  search.py            # Tavily API wrapper
  files.py             # local file/dir reading (incl. PDF-to-text)
  history.py           # session JSON logging
  config.py            # credential prompt/load/save/logout
  requirements.txt
  HELP.md              # usage reference (setup, commands, flags)
  history/             # generated session logs (gitignored)
```

## Documentation
- `HELP.md` covers setup, every slash command, launch flags, and file locations — kept up to date as each story lands (see Story 9 in VERIFICATION.md).
- `/help` in-chat and `python chat.py --help` both surface this reference without leaving the terminal.

## Setup for user
1. Get a free Mistral API key at console.mistral.ai.
2. Get a free Tavily API key at tavily.com.
3. `pip install -r requirements.txt`
4. `python chat.py` — prompts for keys on first run, then drops into chat.

## Launch convenience (Windows)
- A `mistralbot` PowerShell function is added to the user's `$PROFILE`, pointing at this project's `chat.py`. Once added, running `mistralbot` from any directory in any new PowerShell window launches the chat app — no `cd` or `python chat.py` needed.
- This is a per-machine, local convenience (the function lives in `$PROFILE`, not in the repo) — each machine that clones the repo adds its own function pointing at its own clone path.
- `setup.ps1` (repo root) automates this: installs dependencies and appends the profile function in one step, idempotently (marker-comment guarded, safe to re-run). `README.md` documents it as the primary setup path, with manual `pip install` as a fallback.

## Known-fixed issues
- **Stale date grounding (fixed, Story 14):** the model previously had no notion of the real current date and inferred it from its training cutoff, sometimes several days off, which threw off how it judged the recency of web-search results. Every model request now carries a system message stating the actual current date/time.
- **Autocomplete Enter bug (fixed, Story 15):** typing a partial slash command and pressing Enter used to submit the raw partial text as a chat message instead of running the command, because no suggestion was preselected by default. The dropdown now preselects the first match, and Enter completes it into the input line (matching Tab) rather than submitting prematurely.

## Distribution
- Source is published on GitHub (`github.com/badhan-kv/TerminalAIChat`, public, MIT licensed) so it can be cloned onto other machines.
- Nothing user-specific or secret is committed: API keys live outside the repo (`%LOCALAPPDATA%\mistralBot\config.json`), and `history/` transcripts, `__pycache__/`, `.pytest_cache/`, and local Claude Code session config (`.claude/`) are all gitignored.
- `README.md` is the entry point for a fresh machine: clone, `pip install -r requirements.txt`, run, plus the `mistralbot` profile-function setup above.

## Open items to confirm before/while building
- None blocking — ready to scaffold once you confirm this spec.
