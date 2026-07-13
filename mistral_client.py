"""Mistral chat completion calls."""

from mistralai.client import Mistral

DEFAULT_MODEL = "mistral-small-latest"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT_MS = 60_000

FREE_TIER_MODELS = [
    "mistral-small-latest",
    "mistral-medium-latest",
    "mistral-large-latest",
    "ministral-8b-latest",
    "ministral-3b-latest",
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


def send_message(
    client: Mistral, model: str, messages: list[dict], max_tokens: int = DEFAULT_MAX_TOKENS
) -> str:
    """Send full message history, return the assistant's reply text."""
    response = client.chat.complete(model=model, messages=messages, max_tokens=max_tokens)
    return response.choices[0].message.content


def get_tool_calls(
    client: Mistral, model: str, messages: list[dict], max_tokens: int = DEFAULT_MAX_TOKENS
):
    """Ask the model (non-streaming) whether it wants to call the web_search tool
    before answering. Returns the response message; `.tool_calls` is falsy if
    the model chose to answer directly.
    """
    response = client.chat.complete(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        tools=[WEB_SEARCH_TOOL],
        tool_choice="auto",
    )
    return response.choices[0].message


def stream_message(
    client: Mistral, model: str, messages: list[dict], max_tokens: int = DEFAULT_MAX_TOKENS
):
    """Send full message history, yield reply text incrementally as it's generated."""
    event_stream = client.chat.stream(model=model, messages=messages, max_tokens=max_tokens)
    with event_stream as events:
        for event in events:
            choices = event.data.choices
            if not choices:
                continue
            content = choices[0].delta.content
            if isinstance(content, str) and content:
                yield content
