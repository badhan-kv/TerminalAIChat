from unittest.mock import MagicMock, patch

import requests

import search


def _fake_response(json_data, status_ok=True):
    response = MagicMock()
    response.json.return_value = json_data
    if status_ok:
        response.raise_for_status.return_value = None
    else:
        response.raise_for_status.side_effect = requests.HTTPError("boom")
    return response


@patch("search.requests.post")
def test_search_builds_correct_request(mock_post):
    mock_post.return_value = _fake_response({"results": []})

    search.search("latest news", "tvly-testkey", max_results=3)

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer tvly-testkey"
    assert kwargs["json"] == {"query": "latest news", "max_results": 3}


@patch("search.requests.post")
def test_search_parses_results(mock_post):
    mock_post.return_value = _fake_response(
        {
            "results": [
                {"title": "A", "url": "http://a.com", "content": "content a"},
                {"title": "B", "url": "http://b.com", "content": "content b"},
            ]
        }
    )

    results = search.search("query", "key")

    assert results == [
        {"title": "A", "url": "http://a.com", "content": "content a"},
        {"title": "B", "url": "http://b.com", "content": "content b"},
    ]


@patch("search.requests.post")
def test_search_handles_missing_fields(mock_post):
    mock_post.return_value = _fake_response({"results": [{}]})

    results = search.search("query", "key")

    assert results == [{"title": "", "url": "", "content": ""}]


@patch("search.requests.post")
def test_search_raises_on_http_error(mock_post):
    mock_post.return_value = _fake_response({}, status_ok=False)

    try:
        search.search("query", "key")
        assert False, "expected HTTPError"
    except requests.HTTPError:
        pass


def test_format_results_empty_list():
    assert search.format_results([]) == "No web search results found."


def test_format_results_formats_each_entry():
    results = [
        {"title": "Title One", "url": "http://x.com", "content": "Snippet one"},
        {"title": "Title Two", "url": "http://y.com", "content": "Snippet two"},
    ]

    formatted = search.format_results(results)

    assert "1. Title One (http://x.com)" in formatted
    assert "Snippet one" in formatted
    assert "2. Title Two (http://y.com)" in formatted
    assert "Snippet two" in formatted
