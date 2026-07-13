# mistralBot — Help

## Setup
See `GETTING_API_KEYS.md` for how to get free Mistral and Tavily API keys. First run of `python chat.py` will prompt for both and cache them under `%LOCALAPPDATA%\mistralBot\config.json` so you won't be asked again on later runs (until you `/logout`).

## Launch flags
- `--max-tokens N` — caps how many tokens the model may generate per reply (default: 1024). Lower it for shorter/cheaper replies, raise it if replies are getting cut off mid-thought.
  Example: `python chat.py --max-tokens 2048`
- `--model NAME` — sets the model for the session (default: `mistral-small-latest`).
  Example: `python chat.py --model mistral-large-latest`
- `--help` / `-h` — prints this launch-flag usage and exits immediately, without prompting for API keys or starting a chat session.

## In-chat commands
- `/exit` — quit cleanly.
- `/clear` — resets in-memory conversation context; the next question gets no prior context. Does not delete or affect the on-disk session transcript already written — that log is untouched, future turns just keep appending to it after the gap.
- `/logout` — delete the cached API keys (`%LOCALAPPDATA%\mistralBot\config.json`) and quit. Next run will prompt for keys again.
- `/max-tokens <n>` — change the generation cap for subsequent replies without restarting (same effect as launching with `--max-tokens n`).
- `/model` — opens an interactive picker of Mistral's free-tier chat models: Up/Down arrows + Enter to select, or press a number key (1-6) to jump straight to that model. Esc or Ctrl+C cancels without changing anything.
- `/model <name>` — sets the model directly without opening the picker, for when you already know the exact model name.
  Note: free-tier response latency varies by model — the smaller/open-weight ones (e.g. `ministral-3b-latest`) can occasionally take 30-60s, noticeably slower than the flagship models. Requests time out and show an error after 60s rather than hanging indefinitely.
- `/search <query>` — forces a live Tavily web search for `<query>` and asks the model to answer using those results, regardless of whether it would have searched on its own. If the search fails or returns nothing, the model still answers and notes that no results were found rather than crashing.
- `/history` — lists all past session files, newest first: index number, timestamp, a short preview of the first user message, and turn count.
- `/search-history "<text>"` — same listing as `/history`, filtered to sessions where any turn (user or assistant) contains `<text>` (case-insensitive).
- `/resume <n>` — loads session `<n>` (from the last `/history`/`/search-history` listing) into the current conversation so follow-ups have that old context again. Subsequent turns are appended to that session's file instead of the new one created at launch; the just-created empty launch file is removed if nothing was said in it yet.
- `/delete-history contains "<text>"` — deletes all session files where any turn contains `<text>`, after showing the matching count and asking for `y/n` confirmation.
- `/delete-history before <YYYY-MM-DD>` — deletes all session files timestamped before that date, same confirmation flow.
- `/delete <chat #>` — deletes the single session at that index from the last `/history` or `/search-history` listing (e.g. `/delete 2`), with `y/n` confirmation. Run `/history` first if you haven't listed sessions yet this session.
- `/delete <keyword>` — shorthand for `/delete-history contains "<keyword>"`, no quotes needed (e.g. `/delete giraffe`).
- Both `/delete-history` and `/delete` refuse to remove the session file you're currently chatting in (including one loaded via `/resume`) — it's skipped from the match set with a note, even if it matches your filter.
- `/help` — prints a condensed version of this command reference to the terminal.

## Slash-command autocomplete
Typing `/` at the prompt shows a live dropdown of every available command below the input line. Keep typing to narrow it (e.g. `/mo` narrows to `/model`). Tab or Enter on a highlighted suggestion completes it into the input line. Ctrl+C and Ctrl+D still cancel/exit as documented above — that didn't change.

## Automatic web search grounding
When you ask a normal question (not `/search`), the model is offered a `web_search` tool and can choose to call it on its own if the question needs current/real-time information. If it does, you'll see `Model requested a web search: <query>` before the (now-grounded) reply streams in. General-knowledge questions skip this and answer directly.

## Cancelling a response (Ctrl+C)
Pressing Ctrl+C while a reply is streaming cancels *your view* of it and drops you back to the `>` prompt — it does not crash the program.

**Important caveat:** based on how Mistral's API is reported to behave (not confirmed on Mistral's own docs, so treat this as a caution rather than a guarantee), cancelling the stream client-side does **not** necessarily stop generation on Mistral's servers — the full response may still be generated and counted against your free-tier quota even though you stopped seeing it. Ctrl+C saves you *reading* time, not necessarily *token quota*. If you want a hard ceiling on how much any single reply can cost you, use `--max-tokens` instead (see above) — that caps generation length before it starts, rather than trying to stop it mid-flight.

## Conversation memory and history
- **In-session memory**: the model remembers your conversation for as long as `chat.py` keeps running, or until you run `/clear`.
- **On-disk history**: every time you launch `chat.py`, a new transcript file is created under `history/<timestamp>.json` and updated turn-by-turn as you chat. These files are **never deleted automatically** — old sessions just accumulate in that folder. Delete them manually if you want to clean up.

## Where things live
- API keys: `%LOCALAPPDATA%\mistralBot\config.json`
- Session transcripts: `history/<timestamp>.json` (in the project folder)
