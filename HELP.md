# mistralBot — Help

## Setup
See `GETTING_API_KEYS.md` for how to get free Mistral and Tavily API keys. First run of `python chat.py` will prompt for both and cache them under `%LOCALAPPDATA%\mistralBot\config.json` so you won't be asked again on later runs (until you `/logout`).

## Launch flags
- `--max-tokens N` — caps how many tokens the model may generate per reply (default: 1024). Lower it for shorter/cheaper replies, raise it if replies are getting cut off mid-thought.
  Example: `python chat.py --max-tokens 2048`
- `--model NAME` — sets the model for the session (default: `ministral-8b-latest`).
  Example: `python chat.py --model ministral-3b-latest`
  Note: as of Sep 2026 the Mistral free tier no longer includes `mistral-small`, `mistral-medium`, or
  `mistral-large` — calling them returns HTTP 429 with a 0 req/min limit (or 403). Use `ministral-8b-latest`,
  `ministral-3b-latest`, `ministral-14b-latest`, `open-mistral-nemo`, or `codestral-latest`.
- `--help` / `-h` — prints this launch-flag usage and exits immediately, without prompting for API keys or starting a chat session.

## In-chat commands
- `/exit` — quit cleanly.
- `/clear` — resets in-memory conversation context; the next question gets no prior context. Does not delete or affect the on-disk session transcript already written — that log is untouched, future turns just keep appending to it after the gap.
- `/logout` — delete the cached API keys (`%LOCALAPPDATA%\mistralBot\config.json`) and quit. Next run will prompt for keys again.
- `/max-tokens <n>` — change the generation cap for subsequent replies without restarting (same effect as launching with `--max-tokens n`).
- `/model` — opens an interactive picker of Mistral's free-tier chat models: Up/Down arrows + Enter to select, or press a number key (1-5) to jump straight to that model. Esc or Ctrl+C cancels without changing anything.
- `/model <name>` — sets the model directly without opening the picker, for when you already know the exact model name.
  Note: free-tier response latency varies by model — the smaller/open-weight ones (e.g. `ministral-3b-latest`) can occasionally take 30-60s, noticeably slower than the flagship models. Requests time out and show an error after 60s rather than hanging indefinitely.
- `/search <query>` — forces a live Tavily web search for `<query>` and asks the model to answer using those results, regardless of whether it would have searched on its own. If the search fails or returns nothing, the model still answers and notes that no results were found rather than crashing.
- `/ls <dir>` — lists a directory's contents (subdirectories shown with a trailing `/`). Tab-completes paths as you type, and only offers directories. See "Local file access" below for the permission prompt.
- `/read <path>` — loads a file's contents into the conversation context and prints a confirmation (`Loaded <path> (<N> chars) into context.`). It does **not** trigger a reply by itself — ask your question as a normal follow-up message afterwards. Tab-completes paths as you type. See "Local file access" below.
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

## Local file access
`/read` and `/ls` can access any file or directory you can specify a path to — not just the folder `chat.py` was launched from — so the first time either is used in a session you're asked:
```
This command reads from the local filesystem. 1) Allow once  2) Allow this session  3) Deny
```
- **Allow once** — proceeds with just that one `/read` or `/ls`, and asks again next time.
- **Allow this session** — proceeds, and no further prompts appear for `/read` or `/ls` for the rest of this chat session (the choice does not persist across restarts).
- **Deny** (or anything else) — cancels that command, nothing is read.

`/read` supports PDFs: the text is extracted locally (via `pypdf`) before being added to context — nothing is uploaded to Mistral as a document or image. Scanned/image-only PDFs with no text layer will extract as empty or near-empty text. Any other file is read as plain text; non-text/binary files may produce garbled content in the model's context since there's no type restriction.

## Automatic web search grounding
When you ask a normal question (not `/search`), the model is offered a `web_search` tool and can choose to call it on its own if the question needs current/real-time information. If it does, you'll see `Model requested a web search: <query>` before the (now-grounded) reply streams in. General-knowledge questions skip this and answer directly.

The choice isn't left entirely to the model (the small free-tier default doesn't always volunteer a search and can wrongly answer "I can't access the internet"): questions that clearly need live data — weather, news, prices, scores, anything about "today"/"latest"/"current" — force the search up front, and if a direct answer reads as an "I can't access the internet" refusal, the search is retried once with the tool forced (`Model declined to search; retrying with web search forced.`).

## Web search fails with an SSL / certificate error
On a machine behind a corporate TLS-inspecting proxy, `requests` (used for Tavily) rejects
the proxy's self-signed root with `CERTIFICATE_VERIFY_FAILED`, so searches fail while the
reply still streams ("technical issues retrieving real-time data"). The bot looks for a CA
bundle in this order and passes it to both the Tavily and Mistral calls:
1. `REQUESTS_CA_BUNDLE` env var (if set and the file exists)
2. `SSL_CERT_FILE` env var (same)
3. `~/Documents/root-cert.pem` (the machine's exported corporate root cert)

Fix: export your corporate/proxy root CA to `Documents\root-cert.pem`, or point one of the
env vars at it. Nothing to configure on machines that aren't behind such a proxy.

## Cancelling a response (Ctrl+C)
Pressing Ctrl+C while a reply is streaming cancels *your view* of it and drops you back to the `>` prompt — it does not crash the program.

**Important caveat:** based on how Mistral's API is reported to behave (not confirmed on Mistral's own docs, so treat this as a caution rather than a guarantee), cancelling the stream client-side does **not** necessarily stop generation on Mistral's servers — the full response may still be generated and counted against your free-tier quota even though you stopped seeing it. Ctrl+C saves you *reading* time, not necessarily *token quota*. If you want a hard ceiling on how much any single reply can cost you, use `--max-tokens` instead (see above) — that caps generation length before it starts, rather than trying to stop it mid-flight.

## Conversation memory and history
- **In-session memory**: the model remembers your conversation for as long as `chat.py` keeps running, or until you run `/clear`.
- **On-disk history**: every time you launch `chat.py`, a new transcript file is created under `history/<timestamp>.json` and updated turn-by-turn as you chat. These files are **never deleted automatically** — old sessions just accumulate in that folder. Delete them manually if you want to clean up.

## Where things live
- API keys: `%LOCALAPPDATA%\mistralBot\config.json`
- Session transcripts: `history/<timestamp>.json` (in the project folder)
