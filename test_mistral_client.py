from unittest.mock import MagicMock, patch

import httpx
import pytest
from mistralai.client.errors import SDKError

import mistral_client


def _rate_limit_error(retry_after: str | None = None, limit_req_minute: str = "60") -> SDKError:
    headers = {"x-ratelimit-limit-req-minute": limit_req_minute}
    if retry_after is not None:
        headers["retry-after"] = retry_after
    response = httpx.Response(429, headers=headers, text='{"code":"1300"}')
    return SDKError("API error occurred", response)

FAKE_SYSTEM_MESSAGE = {"role": "system", "content": "The current date is a fake fixed date."}


def _fake_client(reply_text: str) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=reply_text))]
    client.chat.complete.return_value = response
    return client


def test_send_message_returns_reply_text():
    client = _fake_client("Hello there!")
    messages = [{"role": "user", "content": "Hi"}]

    result = mistral_client.send_message(client, "mistral-small-latest", messages)

    assert result == "Hello there!"


@patch("mistral_client.current_date_system_message", return_value=FAKE_SYSTEM_MESSAGE)
def test_send_message_passes_model_and_full_history(mock_system_message):
    client = _fake_client("ok")
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]

    mistral_client.send_message(client, "mistral-large-latest", messages)

    client.chat.complete.assert_called_once_with(
        model="mistral-large-latest",
        messages=[FAKE_SYSTEM_MESSAGE] + messages,
        max_tokens=mistral_client.DEFAULT_MAX_TOKENS,
    )


@patch("mistral_client.current_date_system_message", return_value=FAKE_SYSTEM_MESSAGE)
def test_send_message_passes_custom_max_tokens(mock_system_message):
    client = _fake_client("ok")
    messages = [{"role": "user", "content": "hi"}]

    mistral_client.send_message(client, "mistral-small-latest", messages, max_tokens=64)

    client.chat.complete.assert_called_once_with(
        model="mistral-small-latest", messages=[FAKE_SYSTEM_MESSAGE] + messages, max_tokens=64
    )


def test_send_message_grounds_model_in_real_current_date():
    """Regression test: the model must be told the real current date on every
    call, not left to infer it from training data (which caused it to think
    "today" was several days in the past).
    """
    client = _fake_client("ok")
    messages = [{"role": "user", "content": "hi"}]

    mistral_client.send_message(client, "mistral-small-latest", messages)

    sent_messages = client.chat.complete.call_args.kwargs["messages"]
    assert sent_messages[0]["role"] == "system"
    assert "current date" in sent_messages[0]["content"].lower()
    assert sent_messages[1:] == messages


def _fake_tool_call(call_id="call_1", name="web_search", arguments='{"query": "latest news"}'):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


@patch("mistral_client.current_date_system_message", return_value=FAKE_SYSTEM_MESSAGE)
def test_get_tool_calls_returns_message_with_tool_calls(mock_system_message):
    client = MagicMock()
    response = MagicMock()
    tool_call = _fake_tool_call()
    response.choices = [MagicMock(message=MagicMock(tool_calls=[tool_call]))]
    client.chat.complete.return_value = response
    messages = [{"role": "user", "content": "what's today's news?"}]

    message = mistral_client.get_tool_calls(client, "mistral-small-latest", messages)

    assert message.tool_calls == [tool_call]
    client.chat.complete.assert_called_once_with(
        model="mistral-small-latest",
        messages=[FAKE_SYSTEM_MESSAGE, mistral_client.WEB_SEARCH_AVAILABLE_MESSAGE] + messages,
        max_tokens=mistral_client.DEFAULT_MAX_TOKENS,
        tools=[mistral_client.WEB_SEARCH_TOOL],
        tool_choice="auto",
    )


def test_get_tool_calls_returns_message_with_no_tool_calls():
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(tool_calls=None))]
    client.chat.complete.return_value = response
    messages = [{"role": "user", "content": "what is 2+2?"}]

    message = mistral_client.get_tool_calls(client, "mistral-small-latest", messages)

    assert not message.tool_calls


def _fake_event(content):
    event = MagicMock()
    choice = MagicMock()
    choice.delta.content = content
    event.data.choices = [choice]
    return event


def _fake_streaming_client(chunks: list) -> MagicMock:
    client = MagicMock()
    event_stream_cm = MagicMock()
    event_stream_cm.__enter__.return_value = iter(chunks)
    event_stream_cm.__exit__.return_value = False
    client.chat.stream.return_value = event_stream_cm
    return client


def test_stream_message_yields_text_chunks_in_order():
    events = [_fake_event("Hel"), _fake_event("lo"), _fake_event(" world")]
    client = _fake_streaming_client(events)
    messages = [{"role": "user", "content": "hi"}]

    result = list(mistral_client.stream_message(client, "mistral-small-latest", messages))

    assert result == ["Hel", "lo", " world"]


def test_stream_message_skips_empty_and_non_string_content():
    events = [
        _fake_event(None),
        _fake_event(""),
        _fake_event("real chunk"),
    ]
    client = _fake_streaming_client(events)
    messages = [{"role": "user", "content": "hi"}]

    result = list(mistral_client.stream_message(client, "mistral-small-latest", messages))

    assert result == ["real chunk"]


def test_stream_message_skips_events_with_no_choices():
    empty_event = MagicMock()
    empty_event.data.choices = []
    events = [empty_event, _fake_event("chunk")]
    client = _fake_streaming_client(events)
    messages = [{"role": "user", "content": "hi"}]

    result = list(mistral_client.stream_message(client, "mistral-small-latest", messages))

    assert result == ["chunk"]


@patch("mistral_client.current_date_system_message", return_value=FAKE_SYSTEM_MESSAGE)
def test_stream_message_passes_model_max_tokens_and_history(mock_system_message):
    client = _fake_streaming_client([_fake_event("hi")])
    messages = [{"role": "user", "content": "hi"}]

    list(mistral_client.stream_message(client, "mistral-large-latest", messages, max_tokens=64))

    client.chat.stream.assert_called_once_with(
        model="mistral-large-latest", messages=[FAKE_SYSTEM_MESSAGE] + messages, max_tokens=64
    )


@patch("mistral_client.time.sleep")
def test_send_message_retries_on_rate_limit_then_succeeds(mock_sleep):
    client = MagicMock()
    ok = MagicMock()
    ok.choices = [MagicMock(message=MagicMock(content="recovered"))]
    client.chat.complete.side_effect = [_rate_limit_error(), _rate_limit_error(), ok]

    result = mistral_client.send_message(client, "mistral-small-latest", [{"role": "user", "content": "hi"}])

    assert result == "recovered"
    assert client.chat.complete.call_count == 3
    assert mock_sleep.call_count == 2


@patch("mistral_client.time.sleep")
def test_send_message_gives_up_after_max_retries(mock_sleep):
    client = MagicMock()
    client.chat.complete.side_effect = _rate_limit_error()

    with pytest.raises(SDKError):
        mistral_client.send_message(client, "mistral-small-latest", [{"role": "user", "content": "hi"}])

    assert client.chat.complete.call_count == mistral_client.MAX_RETRIES + 1


@patch("mistral_client.time.sleep")
def test_retry_honors_retry_after_header(mock_sleep):
    client = MagicMock()
    ok = MagicMock()
    ok.choices = [MagicMock(message=MagicMock(content="ok"))]
    client.chat.complete.side_effect = [_rate_limit_error(retry_after="7"), ok]

    mistral_client.send_message(client, "mistral-small-latest", [{"role": "user", "content": "hi"}])

    mock_sleep.assert_called_once_with(7.0)


def test_zero_allowance_429_fails_fast_without_retrying():
    client = MagicMock()
    client.chat.complete.side_effect = _rate_limit_error(limit_req_minute="0")

    with pytest.raises(RuntimeError, match="rate limit of 0.*mistral-small-latest"):
        mistral_client.send_message(client, "mistral-small-latest", [{"role": "user", "content": "hi"}])

    assert client.chat.complete.call_count == 1


def test_non_retryable_error_propagates_immediately():
    client = MagicMock()
    client.chat.complete.side_effect = SDKError("bad request", httpx.Response(400, text="{}"))

    with pytest.raises(SDKError):
        mistral_client.send_message(client, "mistral-small-latest", [{"role": "user", "content": "hi"}])

    assert client.chat.complete.call_count == 1


def test_current_date_system_message_contains_todays_date():
    from datetime import datetime

    message = mistral_client.current_date_system_message()

    assert message["role"] == "system"
    assert datetime.now().strftime("%Y-%m-%d") in message["content"]
