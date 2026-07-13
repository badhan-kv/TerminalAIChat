"""Per-session transcript logging to a JSON file under history/."""

import json
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path(__file__).parent / "history"


def start_session(base_dir: Path = HISTORY_DIR) -> Path:
    """Create a new empty session file and return its path."""
    base_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = base_dir / f"{timestamp}.json"
    path.write_text("[]", encoding="utf-8")
    return path


def append_turn(session_path: Path, role: str, content: str) -> None:
    """Append one message to the session file, flushing immediately to disk."""
    turns = json.loads(session_path.read_text(encoding="utf-8"))
    turns.append({"role": role, "content": content})
    session_path.write_text(json.dumps(turns, indent=2), encoding="utf-8")


def load_session(path: Path) -> list[dict]:
    """Return the list of {role, content} turns stored in a session file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _session_summary(path: Path) -> dict:
    turns = load_session(path)
    preview = next((t["content"] for t in turns if t["role"] == "user"), "")
    return {
        "path": path,
        "timestamp": path.stem,
        "preview": preview[:60],
        "turn_count": len(turns),
    }


def list_sessions(base_dir: Path = HISTORY_DIR) -> list[dict]:
    """Return session summaries (path, timestamp, preview, turn_count), newest first."""
    if not base_dir.exists():
        return []
    files = sorted(base_dir.glob("*.json"), reverse=True)
    return [_session_summary(f) for f in files]


def search_sessions(text: str, base_dir: Path = HISTORY_DIR) -> list[dict]:
    """Return session summaries where any turn's content contains `text` (case-insensitive)."""
    text_lower = text.lower()
    matches = []
    for f in sorted(base_dir.glob("*.json"), reverse=True) if base_dir.exists() else []:
        turns = load_session(f)
        if any(text_lower in t["content"].lower() for t in turns):
            matches.append(_session_summary(f))
    return matches


def sessions_before(date_str: str, base_dir: Path = HISTORY_DIR) -> list[Path]:
    """Return session file paths timestamped before `date_str` (YYYY-MM-DD), newest first.

    Raises ValueError if `date_str` isn't in that format.
    """
    cutoff = datetime.strptime(date_str, "%Y-%m-%d")
    if not base_dir.exists():
        return []
    matches = [
        f for f in base_dir.glob("*.json")
        if datetime.strptime(f.stem, "%Y-%m-%d_%H%M%S") < cutoff
    ]
    return sorted(matches, reverse=True)


def delete_sessions(paths: list[Path]) -> int:
    """Delete the given session files. Returns how many were actually removed."""
    count = 0
    for p in paths:
        if p.exists():
            p.unlink()
            count += 1
    return count
