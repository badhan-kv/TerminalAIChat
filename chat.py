"""mistralBot entry point / REPL loop."""

import argparse
import json
import re
import sys

from prompt_toolkit import Application, PromptSession
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

import config
import files
import history
import mistral_client
import search

console = Console()

PICKER_STYLE = Style.from_dict({"selected": "reverse"})

SLASH_COMMANDS = [
    "/clear",
    "/delete",
    "/delete-history",
    "/exit",
    "/help",
    "/history",
    "/ls",
    "/logout",
    "/max-tokens",
    "/model",
    "/read",
    "/resume",
    "/search",
    "/search-history",
]

HELP_TEXT = """\
[bold]Commands[/bold]
  /exit                                  quit
  /clear                                 reset in-memory context (on-disk history unaffected)
  /logout                                delete cached API keys and quit
  /model                                 open interactive model picker
  /model <name>                          set model directly
  /max-tokens <n>                        set generation cap for subsequent replies
  /search <query>                        force a web search for this turn
  /ls <dir>                              list a directory's contents (Tab-completes paths)
  /read <path>                           load a file's contents into context (Tab-completes paths)
  /history                               list past sessions, newest first
  /search-history "<text>"               list sessions where any turn contains <text>
  /resume <n>                            resume session <n> from the last listing
  /delete <chat #>                       delete session <n> from the last listing (confirm)
  /delete <keyword>                      delete sessions containing <keyword> (confirm)
  /delete-history contains "<text>"      delete sessions containing <text> (confirm)
  /delete-history before <YYYY-MM-DD>    delete sessions older than that date (confirm)
  /help                                  show this help

[bold]File access[/bold]  /read and /ls prompt for permission (allow once / allow this session / deny)
                    the first time either is used in a session; PDFs are converted to text locally.
[bold]Launch flags[/bold]  --model <name>   --max-tokens <n>   (see python chat.py --help)
[bold]Autocomplete[/bold]  type / to see a command dropdown; Tab/Enter completes the highlighted one.
Full reference: HELP.md"""


class SlashCommandCompleter(Completer):
    """Completes slash commands as the user types. Offers no completions once
    a space has been typed (command arguments aren't autocompleted).
    """

    def __init__(self, commands: list[str]):
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        for command in self.commands:
            if command.startswith(text):
                yield Completion(command, start_position=-len(text))


class PathAwareCompleter(Completer):
    """Delegates to slash-command completion normally, but switches to
    filesystem path completion once the buffer starts with '/read ' or
    '/ls ' (directories-only for '/ls'), so paths Tab-complete like a
    terminal.
    """

    def __init__(self, commands: list[str]):
        self.command_completer = SlashCommandCompleter(commands)
        self.file_completer = PathCompleter(expanduser=True)
        self.dir_completer = PathCompleter(expanduser=True, only_directories=True)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        for prefix, completer in (("/read ", self.file_completer), ("/ls ", self.dir_completer)):
            if text.startswith(prefix):
                path_text = text[len(prefix):]
                sub_document = Document(path_text, len(path_text))
                yield from completer.get_completions(sub_document, complete_event)
                return
        yield from self.command_completer.get_completions(document, complete_event)


def preselect_first_completion(buffer) -> None:
    """Highlight the first dropdown entry as soon as completions appear, so
    Enter has something sensible to complete instead of falling through to
    the partially-typed text as a raw chat message.
    """
    state = buffer.complete_state
    if state is not None and state.complete_index is None and state.completions:
        state.complete_index = 0


def handle_enter(buffer, commands: list[str]) -> None:
    """Enter completes a highlighted/preselected slash-command suggestion into
    the input line (matching Tab's behavior) instead of submitting the
    partially-typed text. Once the buffer holds a complete, exact command (or
    isn't a slash command at all), Enter submits normally.
    """
    state = buffer.complete_state
    if state is not None and state.completions and buffer.document.text not in commands:
        completion = state.completions[state.complete_index or 0]
        buffer.apply_completion(completion)
        return
    buffer.validate_and_handle()


def make_repl_key_bindings(commands: list[str]) -> KeyBindings:
    kb = KeyBindings()
    kb.add("enter")(lambda event: handle_enter(event.current_buffer, commands))
    return kb


def pick_model(current_model: str, models: list[str] = mistral_client.FREE_TIER_MODELS) -> str | None:
    """Show an arrow-key/number-selectable list of models in the terminal.

    Up/Down + Enter selects the highlighted entry; a digit key 1-9 jumps to
    and selects that entry directly; Esc/Ctrl-C cancels. Returns the chosen
    model name, or None if cancelled.
    """
    state = {"index": models.index(current_model) if current_model in models else 0}
    result = {"value": None}

    def get_text():
        lines = []
        for i, m in enumerate(models):
            prefix = "> " if i == state["index"] else "  "
            marker = " (current)" if m == current_model else ""
            style = "class:selected" if i == state["index"] else ""
            lines.append((style, f"{prefix}{i + 1}. {m}{marker}\n"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    def _move_up(event):
        state["index"] = (state["index"] - 1) % len(models)
        event.app.invalidate()

    @kb.add("down")
    def _move_down(event):
        state["index"] = (state["index"] + 1) % len(models)
        event.app.invalidate()

    @kb.add("enter")
    def _confirm(event):
        result["value"] = models[state["index"]]
        event.app.exit()

    def _select_digit(event, idx):
        if idx < len(models):
            result["value"] = models[idx]
            event.app.exit()

    for digit in "123456789":
        kb.add(digit)(lambda event, idx=int(digit) - 1: _select_digit(event, idx))

    @kb.add("c-c")
    @kb.add("escape")
    def _cancel(event):
        event.app.exit()

    app = Application(
        layout=Layout(HSplit([Window(FormattedTextControl(get_text))])),
        key_bindings=kb,
        style=PICKER_STYLE,
        full_screen=False,
    )
    app.run()
    return result["value"]


def notify_retry(attempt: int, delay: float, exc) -> None:
    """Tell the user we hit a rate limit / transient error and are backing off."""
    reason = "rate limited" if exc.status_code == 429 else f"server error {exc.status_code}"
    console.print(
        f"[yellow]Mistral {reason}; retrying in {delay:.1f}s "
        f"(attempt {attempt}/{mistral_client.MAX_RETRIES})…[/yellow]"
    )


def stream_reply(client, model: str, messages: list[dict], max_tokens: int) -> str:
    """Stream a reply to the console with live markdown rendering, return full text."""
    full_text = ""
    with Live(console=console, refresh_per_second=15) as live:
        for chunk in mistral_client.stream_message(
            client, model, messages, max_tokens, on_retry=notify_retry
        ):
            full_text += chunk
            live.update(Markdown(full_text))
    return full_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="mistralBot terminal chat")
    parser.add_argument(
        "--model",
        type=str,
        default=mistral_client.DEFAULT_MODEL,
        help=f"Mistral model to use (default: {mistral_client.DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=mistral_client.DEFAULT_MAX_TOKENS,
        help=(
            "Maximum tokens the model may generate per reply "
            f"(default: {mistral_client.DEFAULT_MAX_TOKENS}). Longer replies get cut off "
            "at this length; this caps generation length but does not guarantee a lower "
            "token bill if you Ctrl+C cancel early — see HELP.md."
        ),
    )
    return parser.parse_args()


def request_file_permission(file_access_allowed: bool) -> tuple[bool, bool]:
    """Gate local filesystem access behind an explicit prompt.

    If already granted for this session, returns immediately without
    prompting. Otherwise asks once and returns (proceed, new_session_flag).
    """
    if file_access_allowed:
        return True, True
    console.print(
        "[yellow]This command reads from the local filesystem. "
        "1) Allow once  2) Allow this session  3) Deny[/yellow]"
    )
    choice = input("> ").strip()
    if choice == "1":
        return True, False
    if choice == "2":
        return True, True
    console.print("[dim]Denied.[/dim]")
    return False, file_access_allowed


def run_search(query: str, api_key: str) -> str:
    """Run a Tavily search and return formatted results text, or a not-found note on failure."""
    try:
        results = search.search(query, api_key)
    except Exception as e:
        return f"Web search failed: {e}"
    return search.format_results(results)


# Queries that need live data but that a weak model often answers from stale
# training data (or refuses outright). When the latest user turn matches, we
# force the web_search tool instead of leaving the choice to the model.
_TIME_SENSITIVE_RE = re.compile(
    r"\b(weather|forecast|temperature|news|headline|today|tonight|tomorrow|"
    r"currently|right now|latest|current|price|stock|score|who won|"
    r"this (week|month|year)|as of)\b",
    re.IGNORECASE,
)

# Phrases a model emits when it declines instead of calling the tool. If we see
# these in a direct (non-tool) answer, we retry once with the tool forced.
_REFUSAL_MARKERS = (
    "can't access",
    "cannot access",
    "don't have access",
    "do not have access",
    "unable to access",
    "can't browse",
    "cannot browse",
    "real-time",
    "real time",
    "no internet",
    "not connected to the internet",
    "as an ai",
)


def _looks_like_refusal(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def _latest_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def maybe_auto_search(client, model: str, messages: list[dict], tavily_key: str, max_tokens: int) -> None:
    """Ask the model if it wants to call web_search; if so, run it and append
    the tool-call/tool-result messages to `messages` in place so the next
    completion call is grounded.

    The choice isn't left entirely to the model: obviously time-sensitive
    queries force the tool up front, and a direct answer that reads as an
    "I can't access the internet" refusal triggers one forced retry.
    """
    forced = bool(_TIME_SENSITIVE_RE.search(_latest_user_text(messages)))
    message = mistral_client.get_tool_calls(
        client, model, messages, max_tokens, on_retry=notify_retry, force=forced
    )
    if not message.tool_calls and not forced and _looks_like_refusal(message.content):
        console.print("[dim]Model declined to search; retrying with web search forced.[/dim]")
        message = mistral_client.get_tool_calls(
            client, model, messages, max_tokens, on_retry=notify_retry, force=True
        )
    if not message.tool_calls:
        return

    messages.append(
        {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ],
        }
    )
    for tc in message.tool_calls:
        query = json.loads(tc.function.arguments).get("query", "")
        console.print(f"[dim]Model requested a web search: {query}[/dim]")
        results_text = run_search(query, tavily_key)
        messages.append(
            {
                "role": "tool",
                "name": tc.function.name,
                "tool_call_id": tc.id,
                "content": results_text,
            }
        )


def print_sessions(sessions: list[dict]) -> None:
    """Print a numbered, newest-first list of session summaries."""
    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return
    for i, s in enumerate(sessions, start=1):
        preview = s["preview"] or "(no user message)"
        console.print(f"[cyan]{i}.[/cyan] {s['timestamp']}  ({s['turn_count']} turns)  {preview}")


def exclude_active_session(paths: list, session_path) -> list:
    """Remove the currently-active session file from a deletion candidate list
    so /delete-history can never remove the file the session is still writing to.
    """
    if session_path in paths:
        console.print("[dim]Your active session file is excluded from deletion.[/dim]")
        return [p for p in paths if p != session_path]
    return paths


def confirm_and_delete(paths: list, label: str) -> int:
    """Print matching count, ask for y/n confirmation, then delete on yes.

    Returns how many files were actually deleted (0 if none matched or cancelled).
    """
    if not paths:
        console.print("[dim]No matching sessions found.[/dim]")
        return 0
    console.print(f"[yellow]{len(paths)} session(s) match {label}. Delete them? (y/n)[/yellow]")
    confirm = input("> ").strip().lower()
    if confirm != "y":
        console.print("[dim]Cancelled.[/dim]")
        return 0
    deleted = history.delete_sessions(paths)
    console.print(f"[yellow]Deleted {deleted} session file(s).[/yellow]")
    return deleted


def main() -> None:
    args = parse_args()
    creds = config.get_credentials()
    client = mistral_client.make_client(creds["MISTRAL_API_KEY"])
    tavily_key = creds["TAVILY_API_KEY"]
    model = args.model
    max_tokens = args.max_tokens
    messages: list[dict] = []
    session_path = history.start_session()
    last_listed_sessions: list[dict] = []
    file_access_allowed = False
    prompt_session = PromptSession(
        completer=PathAwareCompleter(SLASH_COMMANDS),
        complete_while_typing=True,
        key_bindings=make_repl_key_bindings(SLASH_COMMANDS),
    )
    prompt_session.default_buffer.on_completions_changed += preselect_first_completion

    console.print("mistralBot ready. Type /exit to quit, /logout to clear saved keys.")

    while True:
        try:
            user_input = prompt_session.prompt("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input == "/exit":
            break
        if user_input == "/help":
            console.print(HELP_TEXT)
            continue
        if user_input == "/clear":
            messages = []
            console.print("[yellow]Conversation memory cleared. On-disk history file is unaffected.[/yellow]")
            continue
        if user_input == "/logout":
            config.logout()
            console.print("Saved credentials cleared. Restart to re-enter them.")
            break
        if user_input.startswith("/model"):
            arg = user_input[len("/model"):].strip()
            if not arg:
                chosen = pick_model(model)
                if chosen is None:
                    console.print("[yellow]Model selection cancelled.[/yellow]")
                    continue
                model = chosen
            else:
                model = arg
            console.print(f"[yellow]model set to {model} for subsequent replies.[/yellow]")
            continue
        if user_input.startswith("/max-tokens"):
            arg = user_input[len("/max-tokens"):].strip()
            if not arg.isdigit() or int(arg) <= 0:
                console.print("[yellow]Usage: /max-tokens <positive integer>[/yellow]")
                continue
            max_tokens = int(arg)
            console.print(f"[yellow]max_tokens set to {max_tokens} for subsequent replies.[/yellow]")
            continue

        if user_input == "/history":
            last_listed_sessions = history.list_sessions()
            print_sessions(last_listed_sessions)
            continue
        if user_input.startswith("/search-history"):
            text = user_input[len("/search-history"):].strip().strip('"')
            if not text:
                console.print('[yellow]Usage: /search-history "<text>"[/yellow]')
                continue
            last_listed_sessions = history.search_sessions(text)
            print_sessions(last_listed_sessions)
            continue
        if user_input.startswith("/resume"):
            arg = user_input[len("/resume"):].strip()
            if not arg.isdigit():
                console.print("[yellow]Usage: /resume <n>[/yellow]")
                continue
            idx = int(arg)
            sessions = last_listed_sessions or history.list_sessions()
            last_listed_sessions = sessions
            if not (1 <= idx <= len(sessions)):
                console.print(f"[yellow]No session #{idx}. Run /history to see available sessions.[/yellow]")
                continue
            target = sessions[idx - 1]
            turns = history.load_session(target["path"])
            messages = [{"role": t["role"], "content": t["content"]} for t in turns]
            if target["path"] != session_path and not history.load_session(session_path):
                session_path.unlink(missing_ok=True)
            session_path = target["path"]
            console.print(f"[yellow]Resumed session {target['timestamp']} ({len(turns)} turns).[/yellow]")
            continue
        if user_input.startswith("/delete-history"):
            arg = user_input[len("/delete-history"):].strip()
            if arg.startswith("contains"):
                text = arg[len("contains"):].strip().strip('"')
                if not text:
                    console.print('[yellow]Usage: /delete-history contains "<text>"[/yellow]')
                    continue
                paths = [s["path"] for s in history.search_sessions(text)]
                paths = exclude_active_session(paths, session_path)
                if confirm_and_delete(paths, f'containing "{text}"'):
                    last_listed_sessions = []
            elif arg.startswith("before"):
                date_str = arg[len("before"):].strip()
                try:
                    paths = history.sessions_before(date_str)
                except ValueError:
                    console.print("[yellow]Usage: /delete-history before <YYYY-MM-DD>[/yellow]")
                    continue
                paths = exclude_active_session(paths, session_path)
                if confirm_and_delete(paths, f"before {date_str}"):
                    last_listed_sessions = []
            else:
                console.print(
                    '[yellow]Usage: /delete-history contains "<text>" | /delete-history before <YYYY-MM-DD>[/yellow]'
                )
            continue
        if user_input.startswith("/delete"):
            arg = user_input[len("/delete"):].strip()
            if not arg:
                console.print("[yellow]Usage: /delete <keyword> | /delete <chat #>[/yellow]")
                continue
            if arg.isdigit():
                idx = int(arg)
                sessions = last_listed_sessions or history.list_sessions()
                last_listed_sessions = sessions
                if not (1 <= idx <= len(sessions)):
                    console.print(f"[yellow]No session #{idx}. Run /history to see available sessions.[/yellow]")
                    continue
                paths = [sessions[idx - 1]["path"]]
                label = f"#{idx}"
            else:
                paths = [s["path"] for s in history.search_sessions(arg)]
                label = f'containing "{arg}"'
            paths = exclude_active_session(paths, session_path)
            if confirm_and_delete(paths, label):
                last_listed_sessions = []
            continue

        if user_input.startswith("/ls"):
            arg = user_input[len("/ls"):].strip()
            if not arg:
                console.print("[yellow]Usage: /ls <dir>[/yellow]")
                continue
            proceed, file_access_allowed = request_file_permission(file_access_allowed)
            if not proceed:
                continue
            try:
                entries = files.list_dir(arg)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                continue
            if not entries:
                console.print("[dim](empty directory)[/dim]")
            else:
                for entry in entries:
                    console.print(entry)
            continue
        if user_input.startswith("/read"):
            arg = user_input[len("/read"):].strip()
            if not arg:
                console.print("[yellow]Usage: /read <path>[/yellow]")
                continue
            proceed, file_access_allowed = request_file_permission(file_access_allowed)
            if not proceed:
                continue
            try:
                file_content = files.read_file(arg)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                continue
            context = files.format_file_context(arg, file_content)
            messages.append({"role": "user", "content": context})
            history.append_turn(session_path, "user", context)
            console.print(f"[yellow]Loaded {arg} ({len(file_content)} chars) into context.[/yellow]")
            continue

        if user_input.startswith("/search"):
            query = user_input[len("/search"):].strip()
            if not query:
                console.print("[yellow]Usage: /search <query>[/yellow]")
                continue
            console.print(f"[dim]Searching the web for: {query}[/dim]")
            results_text = run_search(query, tavily_key)
            content = (
                f"Web search results for '{query}':\n{results_text}\n\n"
                f"Using these results, answer: {query}"
            )
            auto_search = False
        else:
            content = user_input
            auto_search = True

        turn_start = len(messages)
        messages.append({"role": "user", "content": content})
        history.append_turn(session_path, "user", content)
        try:
            if auto_search:
                maybe_auto_search(client, model, messages, tavily_key, max_tokens)
            reply = stream_reply(client, model, messages, max_tokens)
        except KeyboardInterrupt:
            console.print("\n[yellow]Generation cancelled.[/yellow]")
            del messages[turn_start:]
            continue
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            del messages[turn_start:]
            continue

        messages.append({"role": "assistant", "content": reply})
        history.append_turn(session_path, "assistant", reply)


if __name__ == "__main__":
    sys.exit(main())
