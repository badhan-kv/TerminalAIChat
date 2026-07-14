from pathlib import Path
from unittest.mock import MagicMock, patch

from prompt_toolkit.document import Document

import chat


@patch("chat.search.search")
@patch("chat.search.format_results")
def test_run_search_formats_results_on_success(mock_format, mock_search):
    mock_search.return_value = [{"title": "T", "url": "U", "content": "C"}]
    mock_format.return_value = "1. T (U)\n   C"

    result = chat.run_search("some query", "api-key")

    mock_search.assert_called_once_with("some query", "api-key")
    assert result == "1. T (U)\n   C"


@patch("chat.search.search", side_effect=Exception("network down"))
def test_run_search_degrades_gracefully_on_failure(mock_search):
    result = chat.run_search("some query", "api-key")

    assert "Web search failed" in result
    assert "network down" in result


def _fake_tool_call(call_id="call_1", name="web_search", arguments='{"query": "latest news"}'):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


@patch("chat.run_search", return_value="1. Result (http://x.com)\n   snippet")
@patch("chat.mistral_client.get_tool_calls")
def test_maybe_auto_search_appends_tool_messages_when_model_calls_tool(mock_get_tool_calls, mock_run_search):
    tool_call = _fake_tool_call()
    mock_get_tool_calls.return_value = MagicMock(content="", tool_calls=[tool_call])
    messages = [{"role": "user", "content": "what's today's news?"}]

    chat.maybe_auto_search(client=MagicMock(), model="mistral-small-latest", messages=messages, tavily_key="key", max_tokens=1024)

    mock_run_search.assert_called_once_with("latest news", "key")
    assert messages[1]["role"] == "assistant"
    assert messages[1]["tool_calls"][0]["id"] == "call_1"
    assert messages[2] == {
        "role": "tool",
        "name": "web_search",
        "tool_call_id": "call_1",
        "content": "1. Result (http://x.com)\n   snippet",
    }


@patch("chat.run_search")
@patch("chat.mistral_client.get_tool_calls")
def test_maybe_auto_search_does_nothing_when_model_answers_directly(mock_get_tool_calls, mock_run_search):
    mock_get_tool_calls.return_value = MagicMock(content="direct answer", tool_calls=None)
    messages = [{"role": "user", "content": "what is 2+2?"}]

    chat.maybe_auto_search(client=MagicMock(), model="mistral-small-latest", messages=messages, tavily_key="key", max_tokens=1024)

    mock_run_search.assert_not_called()
    assert len(messages) == 1


def test_exclude_active_session_removes_the_active_path():
    active, other = Path("active.json"), Path("other.json")

    result = chat.exclude_active_session([active, other], active)

    assert result == [other]


def test_exclude_active_session_leaves_list_unchanged_when_no_match():
    p1, p2 = Path("a.json"), Path("b.json")

    result = chat.exclude_active_session([p1, p2], Path("c.json"))

    assert result == [p1, p2]


def test_slash_command_completer_lists_all_commands_for_bare_slash():
    completer = chat.SlashCommandCompleter(["/exit", "/clear", "/model"])

    completions = [c.text for c in completer.get_completions(Document("/"), None)]

    assert set(completions) == {"/exit", "/clear", "/model"}


def test_slash_command_completer_narrows_by_prefix():
    completer = chat.SlashCommandCompleter(["/exit", "/clear", "/model"])

    completions = [c.text for c in completer.get_completions(Document("/mo"), None)]

    assert completions == ["/model"]


def test_slash_command_completer_no_completions_for_non_slash_text():
    completer = chat.SlashCommandCompleter(["/exit", "/clear"])

    completions = list(completer.get_completions(Document("hello"), None))

    assert completions == []


def test_slash_command_completer_no_completions_once_args_typed():
    completer = chat.SlashCommandCompleter(["/model"])

    completions = list(completer.get_completions(Document("/model foo"), None))

    assert completions == []


def test_preselect_first_completion_selects_index_zero_when_unset():
    buffer = MagicMock()
    buffer.complete_state.complete_index = None
    buffer.complete_state.completions = ["/model", "/max-tokens"]

    chat.preselect_first_completion(buffer)

    assert buffer.complete_state.complete_index == 0


def test_preselect_first_completion_leaves_explicit_selection_alone():
    buffer = MagicMock()
    buffer.complete_state.complete_index = 1
    buffer.complete_state.completions = ["/model", "/max-tokens"]

    chat.preselect_first_completion(buffer)

    assert buffer.complete_state.complete_index == 1


def test_preselect_first_completion_noop_when_no_completions_open():
    buffer = MagicMock()
    buffer.complete_state = None

    chat.preselect_first_completion(buffer)  # must not raise

    assert buffer.complete_state is None


def test_handle_enter_completes_preselected_suggestion_for_partial_command():
    buffer = MagicMock()
    buffer.document.text = "/mo"
    buffer.complete_state.completions = [MagicMock(text="/model")]
    buffer.complete_state.complete_index = 0

    chat.handle_enter(buffer, chat.SLASH_COMMANDS)

    buffer.apply_completion.assert_called_once_with(buffer.complete_state.completions[0])
    buffer.validate_and_handle.assert_not_called()


def test_handle_enter_submits_when_text_is_already_an_exact_command():
    buffer = MagicMock()
    buffer.document.text = "/exit"
    buffer.complete_state.completions = [MagicMock(text="/exit")]
    buffer.complete_state.complete_index = 0

    chat.handle_enter(buffer, chat.SLASH_COMMANDS)

    buffer.validate_and_handle.assert_called_once()
    buffer.apply_completion.assert_not_called()


def test_handle_enter_submits_normally_for_non_slash_text():
    buffer = MagicMock()
    buffer.document.text = "hello there"
    buffer.complete_state = None

    chat.handle_enter(buffer, chat.SLASH_COMMANDS)

    buffer.validate_and_handle.assert_called_once()


def test_request_file_permission_skips_prompt_when_already_allowed():
    proceed, new_flag = chat.request_file_permission(True)

    assert proceed is True
    assert new_flag is True


@patch("builtins.input", return_value="1")
def test_request_file_permission_allow_once_does_not_set_session_flag(mock_input):
    proceed, new_flag = chat.request_file_permission(False)

    assert proceed is True
    assert new_flag is False


@patch("builtins.input", return_value="2")
def test_request_file_permission_allow_session_sets_flag(mock_input):
    proceed, new_flag = chat.request_file_permission(False)

    assert proceed is True
    assert new_flag is True


@patch("builtins.input", return_value="3")
def test_request_file_permission_deny(mock_input):
    proceed, new_flag = chat.request_file_permission(False)

    assert proceed is False
    assert new_flag is False


@patch("builtins.input", return_value="anything else")
def test_request_file_permission_unrecognized_input_denies(mock_input):
    proceed, new_flag = chat.request_file_permission(False)

    assert proceed is False
    assert new_flag is False


def test_path_aware_completer_delegates_to_path_completion_for_read():
    completer = chat.PathAwareCompleter(["/exit", "/read"])

    with patch.object(completer.file_completer, "get_completions", return_value=iter([])) as mock_get:
        list(completer.get_completions(Document("/read some/pa"), None))

    mock_get.assert_called_once()
    sub_document = mock_get.call_args[0][0]
    assert sub_document.text == "some/pa"


def test_path_aware_completer_delegates_to_dir_only_completion_for_ls():
    completer = chat.PathAwareCompleter(["/exit", "/ls"])

    with patch.object(completer.dir_completer, "get_completions", return_value=iter([])) as mock_get:
        list(completer.get_completions(Document("/ls sub"), None))

    mock_get.assert_called_once()
    sub_document = mock_get.call_args[0][0]
    assert sub_document.text == "sub"


def test_path_aware_completer_falls_back_to_slash_commands():
    completer = chat.PathAwareCompleter(["/exit", "/model"])

    completions = [c.text for c in completer.get_completions(Document("/mo"), None)]

    assert completions == ["/model"]
