# mistralBot — Verification Strategy

## Approach
Agile, story-by-story. Each story ships with written acceptance criteria, automated tests for its core logic, and a manual smoke test you run in PowerShell before it's marked done.

## Method of working
Whenever a story (or any change with a manual smoke-test step) is finished, provide the exact smoke-test instructions as part of that same response — concrete commands/inputs to run and what to look for — rather than just pointing at the acceptance criteria and asking the user to go test it. The user runs the test; Claude prepares the runbook.

## Test layers
1. **Unit tests (pytest, mocked HTTP)** — cover non-trivial logic only:
   - `config.py`: first-run prompt, save/load, `/logout` deletes the file.
   - `search.py`: Tavily request building, response parsing into snippets, error/empty-result handling.
   - `mistral_client.py`: request payload shape, tool-call detection/routing, streaming chunk assembly — all against mocked HTTP responses, not the live API.
   - `history.py`: session JSON file created/appended correctly, one record per turn.
   - No tests for the REPL loop / CLI plumbing itself — that's verified manually.
2. **Manual smoke test (live API, once per story)** — for anything that touches the real Mistral or Tavily endpoints, you run the tool once against the real free-tier key and confirm it behaves as expected. Catches API contract drift that mocks can't.
3. No CI. Run `pytest` locally before marking a story done.

## Definition of Done (per story)
A story is done when:
- [ ] Acceptance criteria (below, per story) are all checked.
- [ ] `pytest` passes for any new/changed core-logic tests.
- [ ] You've run the manual smoke-test steps yourself in PowerShell and confirmed the behavior.

## Story backlog with acceptance criteria

### Story 1 — Credential setup (`config.py`)
- First run with no config file prompts for `MISTRAL_API_KEY` and `TAVILY_API_KEY` and saves them to `%LOCALAPPDATA%\mistralBot\config.json`.
- Second run (config file present) does not prompt again.
- `/logout` deletes the config file; next run prompts again.
- *Manual smoke test:* run `python chat.py` twice — confirm no second prompt — then `/logout`, exit, run again — confirm it re-prompts.

### Story 2 — Basic chat loop, non-streaming (`chat.py`, `mistral_client.py`)
- Typing a question sends it to Mistral and prints a reply.
- Conversation history is kept in-memory; a follow-up question shows the model has prior context.
- `/exit` quits cleanly.
- *Manual smoke test:* ask a question, ask a follow-up referencing "it", confirm the model resolves the reference correctly.

### Story 3 — Streaming + rich output (`mistral_client.py`, `chat.py`)
- Response text appears incrementally as it's generated, not all at once.
- Markdown (bold, code blocks) renders correctly in the terminal.
- *Manual smoke test:* ask for a short code snippet, confirm it streams and renders as a syntax-highlighted code block.

### Story 4 — Session history logging (`history.py`)
- A new `history/<timestamp>.json` file is created at session start.
- Each turn (user + assistant message) is appended/flushed to that file as the session proceeds.
- *Manual smoke test:* have a short conversation, kill the terminal mid-session, confirm the file on disk contains the turns up to that point.

### Story 5 — Manual web search grounding (`search.py`, `/search` command)
- `/search <query>` calls Tavily, injects top results into context, and the next model reply references them.
- Empty/failed search results degrade gracefully (model still answers, notes no results found).
- *Manual smoke test:* ask about something recent/time-sensitive with `/search`, confirm the answer reflects current info with no crash.

### Story 6 — Automatic grounding via tool-calling (`mistral_client.py`, `search.py`)
- Model is given a `web_search` tool definition; for a query that clearly needs current info, it invokes the tool on its own (verified by a log line, not asked to fake it).
- Tool result is fed back and the final answer is grounded.
- For a query that doesn't need current info, the model answers directly without triggering search.
- *Manual smoke test:* ask a current-events question (should auto-search) and a general-knowledge question (should not), confirm the difference.

### Story 7 — Model & generation switching (`/model`, `--model`, `/max-tokens`, `--max-tokens`)
- `--model mistral-large-latest` at launch sets the session's default model.
- `/model <name>` mid-session switches for subsequent turns.
- `--max-tokens N` at launch sets the generation cap (already implemented — see below).
- `/max-tokens <n>` mid-session changes the cap for subsequent turns, same as the launch flag.
- *Manual smoke test:* start with default, switch via `/model`, confirm next reply's behavior/latency is consistent with the new model; separately, run `/max-tokens 50` mid-chat and confirm the next reply is capped at roughly that length.

### Story 8 — History browsing & management (`/history`, `/search-history`, `/resume`, `/delete-history`)
- `/history` lists past session files newest-first: index number, timestamp, a truncated preview of the first user message, and turn count.
- `/search-history "<text>"` lists sessions (same fields as `/history`) where any turn's content contains `<text>` (case-insensitive substring match).
- `/resume <n>` loads that session's full transcript into the current in-memory conversation (so follow-ups have that old context again), and subsequent turns are appended to that same session file instead of the new empty one created at launch — the just-created empty file for the current launch is removed so it doesn't linger as clutter.
- `/delete-history contains "<text>"` deletes all session files where any turn contains `<text>`, after printing the matching count and asking for `y/n` confirmation.
- `/delete-history before <YYYY-MM-DD>` deletes all session files timestamped before that date, after printing the matching count and asking for `y/n` confirmation.
- Deletion always requires explicit confirmation — no silent/automatic deletion.
- `/delete <chat #>` (e.g. `/delete 2`) deletes the single session at that index from the last `/history`/`/search-history` listing, with the same `y/n` confirmation.
- `/delete <keyword>` (no quotes) is shorthand for `/delete-history contains "<keyword>"`.
- `/delete-history` and `/delete` never delete the currently-active session file (including one loaded via `/resume`), even if it matches the filter — it's excluded from the match set with a printed note. (Added after a live bug: deleting the active session crashed the next turn.)
- *Manual smoke test:* have 2-3 short chats (separate `chat.py` runs) with distinguishable content, then in a new session: `/history` (confirm all show up), `/search-history "<a distinctive word>"` (confirm only the matching one(s) show), `/resume <n>` on one (confirm a follow-up question shows it has that old context), `/delete-history before <a future date>` (confirm it lists and, after confirming, deletes all of them).

### Story 9 — `/clear` command
- `/clear` resets in-memory conversation history; next question gets no prior context.
- Does not delete the on-disk history file already written (that's a separate log, not undone).
- *Manual smoke test:* build context, `/clear`, ask a question relying on cleared context, confirm the model no longer has it.

### Story 10 — Slash-command autocomplete (live dropdown)
- Typing `/` alone shows a live dropdown below the input listing every available command.
- Typing more characters (e.g. `/mo`) narrows the dropdown to matching commands (e.g. `/model`).
- Tab or Enter on a highlighted suggestion completes it into the input line.
- Built with `prompt_toolkit` (`PromptSession` + a `Completer`), replacing the plain `input()` call — Ctrl+C/Ctrl+D behavior at the prompt must keep working exactly as before (cancel/exit).
- *Manual smoke test:* type `/` and confirm the dropdown appears with all commands; type `/mo` and confirm it narrows to `/model`; press Tab to complete it, confirm the full command lands in the input line; confirm Ctrl+C and Ctrl+D still behave as documented in Story 1/2.

### Story 11 — Help / usage docs (`HELP.md`, `/help` command, `--help` flag)
- `HELP.md` in the project root documents: setup (getting API keys, first-run flow), every slash command (`/search`, `/model`, `/max-tokens`, `/history`, `/search-history`, `/resume`, `/delete-history`, `/clear`, `/logout`, `/help`, `/exit`), the `--model`/`--max-tokens` launch flags, autocomplete usage, and where session history/config files live.
- `/help` inside a chat session prints a condensed version of the same command reference to the terminal.
- `python chat.py --help` prints launch-flag usage and exits, without starting a chat session.
- *Manual smoke test:* run `--help` before any key is configured (should not prompt for credentials), then in a live session run `/help` and confirm every documented command actually behaves as described.

### Story 12 — PowerShell quick-launch command
- A `mistralbot` function is added to the user's `$PROFILE` (created if it doesn't exist) that runs `python <project>\chat.py` with any passed-through args.
- Running `mistralbot` from any directory, in a fresh PowerShell window, launches the chat app exactly as `python chat.py` would from the project directory.
- No unit tests — this is shell configuration, not application logic; verified manually only.
- *Manual smoke test:* open a new PowerShell window, `cd` to somewhere unrelated (e.g. `cd ~`), run `mistralbot`, confirm the chat app starts normally (prompts or drops into chat). Try `mistralbot --help` too and confirm launch flags still work.

### Story 13 — GitHub packaging & second-machine setup
- `.gitignore` excludes `history/*.json` (transcripts), `__pycache__/`, `.pytest_cache/`, `.claude/` (local Claude Code session config), and `CHECKPOINT.md` — nothing user-specific or generated is committed.
- `README.md` documents: what the project is, prerequisites (Python 3, API keys per `GETTING_API_KEYS.md`), clone + `pip install -r requirements.txt` + `python chat.py` first-run flow, and the optional `mistralbot` PowerShell profile-function setup for quick launch.
- `LICENSE` (MIT) is present at repo root.
- Repo is pushed to a public GitHub repo (`badhan-kv/TerminalAIChat`) via `gh` CLI browser-based device-code auth — no password or long-lived token is ever typed into or handled by Claude Code.
- No unit tests — packaging/docs, not application logic.
- *Manual smoke test:* on this machine, clone the repo fresh into a throwaway directory (`git clone https://github.com/badhan-kv/TerminalAIChat temp-clone`), follow only the README's setup steps from scratch, confirm `python chat.py` runs. Then delete the throwaway clone.

### Story 14 — Ground the model in the real current date (bug fix)
- Every request to Mistral (`send_message`, `get_tool_calls`, `stream_message`) is prepended with a `system` message stating the actual current date/time, so the model doesn't fall back on its stale training-data cutoff when reasoning about "today", "now", or how recent web-search results are.
- The system message is generated fresh per-call (`mistral_client.current_date_system_message()`), not stored in the persisted `messages`/history list, so it doesn't pollute `/history`, `/resume`, or session transcripts.
- *Manual smoke test:* ask "what's today's date?" with no search — confirm it matches the real date. Then ask a time-sensitive question that triggers auto-search (e.g. "what happened in the news today") and confirm the model's framing of "today"/recency lines up with the actual date rather than being off by several days.

### Story 15 — Fix slash-command autocomplete: preselect first match, don't submit partial text
- **Bug:** typing a partial slash command (e.g. `/mo`) and pressing Enter previously submitted the literal partial text as a chat message instead of completing/running the intended command, because nothing in the dropdown was preselected by default.
- The first matching suggestion in the dropdown is now preselected automatically as completions are computed (`chat.preselect_first_completion`), without needing an explicit Down/Tab press.
- Pressing Enter while a partial (non-exact) slash command is typed completes the preselected (or manually arrow-selected) suggestion into the input line — same behavior as Tab — rather than submitting it (`chat.handle_enter`).
- Once the input line holds a complete, exact command (e.g. after that first Enter, or if typed out in full), a further Enter submits it normally, same as before this fix.
- Non-slash text is unaffected — Enter always submits directly since no completion menu is open.
- Unit tests cover `preselect_first_completion` and `handle_enter` in isolation (mocked buffer/complete_state) — the actual interactive rendering isn't unit-testable, per this project's usual REPL/TUI testing approach.
- *Manual smoke test:* type `/mo`, confirm `/model` appears highlighted in the dropdown without pressing any arrow key, press Enter once — confirm it completes to `/model` in the input line (doesn't submit), press Enter again — confirm it now runs `/model`. Separately, type `/exit` in full and press Enter once — confirm it quits immediately (no double-Enter needed for an already-exact command). Also confirm typing a normal (non-slash) message and pressing Enter still sends immediately.

### Story 16 — Automated setup script (`setup.ps1`)
- Running `.\setup.ps1` from a freshly cloned repo installs Python dependencies (`pip install -r requirements.txt`) and adds a `mistralbot` function to the user's `$PROFILE`, pointing at that clone's `chat.py` (using `$PSScriptRoot`, so it's correct regardless of where the repo was cloned).
- Idempotent: running it again detects the marker comment already in `$PROFILE` and skips re-adding the function instead of duplicating it.
- README documents `setup.ps1` as the primary setup path, with manual `pip install` as a fallback for users who don't want it touching their profile.
- No unit tests — shell script, not application logic; verified manually only.
- *Manual smoke test:* in a fresh clone, run `.\setup.ps1`, confirm dependencies install and `$PROFILE` gains the `mistralbot` function; run it a second time and confirm no duplicate block is added; open a new PowerShell window and confirm `mistralbot` launches the app from any directory.

### Story 17 — Local file reading (`files.py`, `/read`, `/ls`, permission gate, path completion)
- `files.read_file` reads plain-text files as text, and PDFs (by `.pdf` extension) via `pypdf`, joining extracted per-page text.
- `files.list_dir` returns a sorted directory listing with subdirectories suffixed `/`.
- The first use of `/read` or `/ls` in a chat session prompts `1) Allow once  2) Allow this session  3) Deny` (`chat.request_file_permission`); "Allow this session" suppresses the prompt for all further `/read`/`/ls` calls that session; anything other than 1/2 denies. Both commands share this one gate.
- `/read <path>` loads the file's contents into `messages` and on-disk history as a single user-role turn, prints a `Loaded <path> (<N> chars) into context.` confirmation, and does **not** trigger a model reply — the next normal message is what asks about it.
- `/ls <dir>` prints the directory listing to the console only; it never touches `messages`/history.
- Typing `/read ` or `/ls ` and pressing Tab autocompletes filesystem paths (`chat.PathAwareCompleter`) instead of showing slash-command suggestions; `/ls` only offers directories.
- Bad paths (missing file/dir, reading a directory as a file) print a clean `[red]Error: ...[/red]` rather than crashing the REPL.
- Unit tests: `test_files.py` covers `read_file` (text, PDF via mocked `pypdf.PdfReader`, missing path, directory-as-file), `list_dir` (sorting, dir suffix, missing path), `format_file_context`. `test_chat.py` covers `request_file_permission`'s three branches plus the unrecognized-input case, and `PathAwareCompleter`'s dispatch to file/dir/slash-command completion.
- *Manual smoke test:* run `python chat.py`, type `/ls .` — confirm the permission prompt appears, choose `1` (allow once), confirm the directory listing prints; run `/read <a .txt file>` and confirm the prompt appears *again* (only "once" was granted last time). Restart, this time choose `2` (allow this session) on the first prompt, then run several more `/read`/`/ls` commands and confirm no further prompts appear. `/read` a `.txt` or `.py` file, then ask a normal follow-up question about it (e.g. "what does this file do?") and confirm the answer reflects the actual file content. `/read` a small PDF and confirm a sensible non-zero char count in the confirmation, then ask a follow-up question about its content. Try `/read` on a nonexistent path and confirm a clean error, no crash. Type `/read ` (trailing space) and press Tab — confirm filesystem paths autocomplete rather than slash commands.

## Notes
- Stories are ordered so each one is runnable/demoable on its own — no story depends on a later one.
- Story 11 is written last since it documents behavior from Stories 1-10, but the `HELP.md` content should be updated incrementally as each earlier story lands, not written all at once at the end (already true in practice — see the Ctrl+C caveat and `--max-tokens` docs added ahead of schedule).
- If Tavily or Mistral free-tier limits get hit during smoke testing, note it and we'll adjust (e.g. add basic rate-limit backoff as a follow-up story) rather than over-building retry logic speculatively now.
- The `/max-tokens` in-chat command (part of Story 7) was implemented ahead of its story slot, same as `--max-tokens` before it — small, unambiguous increments get built as soon as they're requested rather than strictly waiting for backlog order.
