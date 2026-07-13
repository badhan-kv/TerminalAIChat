import json
from pathlib import Path

import history


def test_start_session_creates_empty_json_file(tmp_path):
    path = history.start_session(base_dir=tmp_path)

    assert path.exists()
    assert path.parent == tmp_path
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_start_session_creates_base_dir_if_missing(tmp_path):
    base_dir = tmp_path / "history"
    assert not base_dir.exists()

    path = history.start_session(base_dir=base_dir)

    assert base_dir.exists()
    assert path.parent == base_dir


def test_append_turn_writes_one_record_per_call(tmp_path):
    path = history.start_session(base_dir=tmp_path)

    history.append_turn(path, "user", "hello")
    history.append_turn(path, "assistant", "hi there")

    turns = json.loads(path.read_text(encoding="utf-8"))
    assert turns == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_append_turn_is_flushed_to_disk_immediately(tmp_path):
    path = history.start_session(base_dir=tmp_path)
    history.append_turn(path, "user", "first")

    # Simulate reading from a fresh process (no in-memory state) after a crash.
    turns = json.loads(path.read_text(encoding="utf-8"))
    assert turns == [{"role": "user", "content": "first"}]


def _make_session(base_dir, stem, turns):
    path = base_dir / f"{stem}.json"
    path.write_text(json.dumps(turns), encoding="utf-8")
    return path


def test_list_sessions_empty_dir_returns_empty_list(tmp_path):
    assert history.list_sessions(base_dir=tmp_path / "missing") == []


def test_list_sessions_returns_newest_first_with_summary_fields(tmp_path):
    _make_session(tmp_path, "2026-01-01_100000", [{"role": "user", "content": "hello there"}])
    _make_session(
        tmp_path,
        "2026-01-02_100000",
        [
            {"role": "user", "content": "second session question"},
            {"role": "assistant", "content": "answer"},
        ],
    )

    sessions = history.list_sessions(base_dir=tmp_path)

    assert [s["timestamp"] for s in sessions] == ["2026-01-02_100000", "2026-01-01_100000"]
    assert sessions[0]["preview"] == "second session question"
    assert sessions[0]["turn_count"] == 2


def test_list_sessions_preview_falls_back_to_empty_when_no_user_turn(tmp_path):
    _make_session(tmp_path, "2026-01-01_100000", [{"role": "assistant", "content": "hi"}])

    sessions = history.list_sessions(base_dir=tmp_path)

    assert sessions[0]["preview"] == ""


def test_search_sessions_matches_case_insensitive_substring_in_any_turn(tmp_path):
    _make_session(tmp_path, "2026-01-01_100000", [{"role": "user", "content": "about PYTHON code"}])
    _make_session(tmp_path, "2026-01-02_100000", [{"role": "user", "content": "about javascript"}])

    matches = history.search_sessions("python", base_dir=tmp_path)

    assert len(matches) == 1
    assert matches[0]["timestamp"] == "2026-01-01_100000"


def test_search_sessions_matches_assistant_turns_too(tmp_path):
    _make_session(
        tmp_path,
        "2026-01-01_100000",
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "distinctive keyword here"}],
    )

    matches = history.search_sessions("distinctive keyword", base_dir=tmp_path)

    assert len(matches) == 1


def test_search_sessions_no_matches_returns_empty_list(tmp_path):
    _make_session(tmp_path, "2026-01-01_100000", [{"role": "user", "content": "hi"}])

    matches = history.search_sessions("nonexistent", base_dir=tmp_path)

    assert matches == []


def test_sessions_before_filters_by_timestamp(tmp_path):
    _make_session(tmp_path, "2026-01-01_100000", [{"role": "user", "content": "old"}])
    _make_session(tmp_path, "2026-06-01_100000", [{"role": "user", "content": "new"}])

    matches = history.sessions_before("2026-03-01", base_dir=tmp_path)

    assert len(matches) == 1
    assert matches[0].stem == "2026-01-01_100000"


def test_sessions_before_empty_dir_returns_empty_list(tmp_path):
    assert history.sessions_before("2026-03-01", base_dir=tmp_path / "missing") == []


def test_sessions_before_invalid_date_raises_value_error():
    try:
        history.sessions_before("not-a-date", base_dir=Path("."))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_delete_sessions_removes_files_and_returns_count(tmp_path):
    path1 = _make_session(tmp_path, "2026-01-01_100000", [{"role": "user", "content": "a"}])
    path2 = _make_session(tmp_path, "2026-01-02_100000", [{"role": "user", "content": "b"}])

    deleted = history.delete_sessions([path1, path2])

    assert deleted == 2
    assert not path1.exists()
    assert not path2.exists()


def test_delete_sessions_skips_missing_files(tmp_path):
    missing = tmp_path / "nope.json"

    deleted = history.delete_sessions([missing])

    assert deleted == 0


def test_load_session_returns_turns(tmp_path):
    path = _make_session(tmp_path, "2026-01-01_100000", [{"role": "user", "content": "x"}])

    assert history.load_session(path) == [{"role": "user", "content": "x"}]
