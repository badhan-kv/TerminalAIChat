"""Mistral chat completion calls."""

import random
import time
from datetime import datetime

from mistralai.client import Mistral
from mistralai.client.errors import MistralError

DEFAULT_MODEL = "ministral-8b-latest"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT_MS = 60_000

# Mistral returns 429 (code 1300) for transient rate-limit spikes, which we retry
# with exponential backoff. It ALSO returns 429 with a flat `x-ratelimit-limit-
# req-minute: 0` for a model the account's tier has no allowance for — as of
# Sep 2026 the free tier lost mistral-small/medium/large; only the ministral-*,
# codestral, and open-mistral-nemo families still work. A 0 cap never recovers,
# so we fail fast telling the user to switch models with /model.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 4
MAX_BACKOFF_SECONDS = 30

MODEL_NOT_ON_TIER_HINT = (
    "Mistral returned a rate limit of 0 requests/minute for model '{model}' — "
    "your account tier has no allowance for it (the free tier no longer includes "
    "mistral-small/medium/large). Switch with /model — ministral-8b-latest, "
    "ministral-3b-latest, open-mistral-nemo, and codestral-latest still work. "
    "Your API key is fine; retrying will not help."
)


def _retry_after_seconds(exc: MistralError) -> float | None:
    """Honor a Retry-After header (seconds) if the server sent one."""
    try:
        return float(exc.headers.get("retry-after"))
    except (AttributeError, TypeError, ValueError):
        return None


def _is_zero_allowance(exc: MistralError) -> bool:
    """True when the 429 is a flat 0-req/min cap (unactivated org), not a spike."""
    try:
        return exc.headers.get("x-ratelimit-limit-req-minute") == "0"
    except AttributeError:
        return False


def _with_retries(call, *, model="", on_retry=None):
    """Run `call()`, retrying transient HTTP errors with exponential backoff.

    `on_retry(attempt, delay, exc)` is invoked before each sleep so callers can
    surface a "rate limited, retrying" notice.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            return call()
        except MistralError as exc:
            if exc.status_code == 429 and _is_zero_allowance(exc):
                raise RuntimeError(MODEL_NOT_ON_TIER_HINT.format(model=model)) from exc
            if exc.status_code not in RETRYABLE_STATUS or attempt == MAX_RETRIES:
                raise
            delay = _retry_after_seconds(exc)
            if delay is None:
                delay = min(2**attempt, MAX_BACKOFF_SECONDS) + random.uniform(0, 0.5)
            if on_retry is not None:
                on_retry(attempt + 1, delay, exc)
            time.sleep(delay)

# Models the free tier can actually call as of Sep 2026 (verified against the
# API: mistral-small/medium/large now return 429 with a 0 req/min cap or 403).
FREE_TIER_MODELS = [
    "ministral-8b-latest",
    "ministral-3b-latest",
    "ministral-14b-latest",
    "open-mistral-nemo",
    "codestral-latest",
]

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current, real-time, or recent information not "
            "available in the model's training data (news, prices, current "
            "events, recent releases, etc.)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"],
        },
    },
}


def make_client(api_key: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Mistral:
    return Mistral(api_key=api_key, timeout_ms=timeout_ms)


def current_date_system_message() -> dict:
    """A system message grounding the model in the real current date/time.

    Without this, the model falls back on its training-data cutoff to guess
    "today", which is often days/months off and makes it misjudge how recent
    web-search results actually are.
    """
    now = datetime.now()
    return {
        "role": "system",
        "content": (
            f"The current date is {now.strftime('%A, %B %d, %Y')} "
            f"({now.strftime('%Y-%m-%d')}), local time {now.strftime('%H:%M')}. "
            "Treat this as authoritative for any question involving 'today', "
            "'now', 'current', 'latest', or recent events, and when judging how "
            "recent web search results are — do not rely on your training cutoff "
            "to infer the date."
        ),
    }


def send_message(
    client: Mistral,
    model: str,
    messages: list[dict],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    on_retry=None,
) -> str:
    """Send full message history, return the assistant's reply text."""
    full_messages = [current_date_system_message()] + messages
    response = _with_retries(
        lambda: client.chat.complete(model=model, messages=full_messages, max_tokens=max_tokens),
        model=model,
        on_retry=on_retry,
    )
    return response.choices[0].message.content


def get_tool_calls(
    client: Mistral,
    model: str,
    messages: list[dict],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    on_retry=None,
):
    """Ask the model (non-streaming) whether it wants to call the web_search tool
    before answering. Returns the response message; `.tool_calls` is falsy if
    the model chose to answer directly.
    """
    full_messages = [current_date_system_message()] + messages
    response = _with_retries(
        lambda: client.chat.complete(
            model=model,
            messages=full_messages,
            max_tokens=max_tokens,
            tools=[WEB_SEARCH_TOOL],
            tool_choice="auto",
        ),
        model=model,
        on_retry=on_retry,
    )
    return response.choices[0].message


def stream_message(
    client: Mistral,
    model: str,
    messages: list[dict],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    on_retry=None,
):
    """Send full message history, yield reply text incrementally as it's generated.

    The rate-limit retry only covers establishing the stream; a 429 mid-stream
    (rare) still propagates.
    """
    full_messages = [current_date_system_message()] + messages
    event_stream = _with_retries(
        lambda: client.chat.stream(model=model, messages=full_messages, max_tokens=max_tokens),
        model=model,
        on_retry=on_retry,
    )
    with event_stream as events:
        for event in events:
            choices = event.data.choices
            if not choices:
                continue
            content = choices[0].delta.content
            if isinstance(content, str) and content:
                yield content
