from unittest.mock import MagicMock, patch

import pytest

import files


def test_read_file_returns_text_contents(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("hello world", encoding="utf-8")

    assert files.read_file(str(p)) == "hello world"


def test_read_file_raises_on_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        files.read_file(str(tmp_path / "missing.txt"))


def test_read_file_raises_on_directory(tmp_path):
    with pytest.raises(IsADirectoryError):
        files.read_file(str(tmp_path))


@patch("files.PdfReader")
def test_read_file_extracts_text_from_pdf(mock_reader_cls, tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    page1, page2 = MagicMock(), MagicMock()
    page1.extract_text.return_value = "Page one"
    page2.extract_text.return_value = "Page two"
    mock_reader_cls.return_value.pages = [page1, page2]

    result = files.read_file(str(p))

    mock_reader_cls.assert_called_once_with(str(p))
    assert result == "Page one\nPage two"


@patch("files.PdfReader")
def test_read_file_pdf_handles_none_extract_text(mock_reader_cls, tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    page = MagicMock()
    page.extract_text.return_value = None
    mock_reader_cls.return_value.pages = [page]

    result = files.read_file(str(p))

    assert result == ""


def test_list_dir_returns_sorted_entries_with_dir_suffix(tmp_path):
    (tmp_path / "b.txt").write_text("x")
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sub").mkdir()

    result = files.list_dir(str(tmp_path))

    assert result == ["a.txt", "b.txt", "sub/"]


def test_list_dir_raises_on_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        files.list_dir(str(tmp_path / "missing"))


def test_format_file_context_shape():
    result = files.format_file_context("notes.txt", "hello world")

    assert result == "Contents of 'notes.txt':\nhello world"
