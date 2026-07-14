"""Local filesystem access: read a file's contents (with PDF-to-text
conversion) and list a directory's entries.
"""

import os
from pathlib import Path

from pypdf import PdfReader


def read_file(path: str) -> str:
    """Read a file's contents as text.

    PDFs (by extension) are converted to text locally via pypdf. Other files
    are read as text with invalid bytes replaced rather than raising, since
    this project makes no assumption about which file types are safe.

    Raises FileNotFoundError / IsADirectoryError for bad paths, same as the
    underlying filesystem calls.
    """
    resolved = Path(path).expanduser()
    if resolved.is_dir():
        raise IsADirectoryError(f"{path} is a directory, not a file")
    if resolved.suffix.lower() == ".pdf":
        reader = PdfReader(str(resolved))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def list_dir(path: str) -> list[str]:
    """List a directory's entries, sorted, with subdirectories suffixed '/'."""
    resolved = Path(path).expanduser()
    entries = sorted(os.listdir(resolved))
    return [
        f"{name}/" if (resolved / name).is_dir() else name
        for name in entries
    ]


def format_file_context(path: str, content: str) -> str:
    """Format loaded file content as a message string for chat context."""
    return f"Contents of '{path}':\n{content}"
