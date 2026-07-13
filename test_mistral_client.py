from unittest.mock import MagicMock

import mistral_client


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


def test_send_message_passes_model_and_full_history():
    client = _fake_client("ok")
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]

    mistral_client.send_message(client, "mistral-large-latest", messages)

    client.chat.complete.assert_called_once_with(
        model="mistral-large-latest",
        messages=messages,
        max_tokens=mistral_client.DEFAULT_MAX_TOKENS,
    )


def test_send_message_passes_custom_max_tokens():
    client = _fake_client("ok")
    messages = [{"role": "user", "content": "hi"}]

    mistral_client.send_message(client, "mistral-small-latest", messages, max_tokens=64)

    client.chat.complete.assert_called_once_with(
        model="mistral-small-latest", messages=messages, max_tokens=64
    )


def _fake_tool_call(call_id="call_1", name="web_search", arguments='{"query": "latest news"}'):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def test_get_tool_calls_returns_message_with_tool_calls():
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
        messages=messages,
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


def test_stream_message_passes_model_max_tokens_and_history():
    client = _fake_streaming_client([_fake_event("hi")])
    messages = [{"role": "user", "content": "hi"}]

    list(mistral_client.stream_message(client, "mistral-large-latest", messages, max_tokens=64))

    client.chat.stream.assert_called_once_with(
        model="mistral-large-latest", messages=messages, max_tokens=64
    )
