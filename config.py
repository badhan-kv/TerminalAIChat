"""Credential storage: prompt once, cache locally, clear via /logout."""

import json
import os
from getpass import getpass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "mistralBot"
CONFIG_PATH = CONFIG_DIR / "config.json"

REQUIRED_KEYS = ("MISTRAL_API_KEY", "TAVILY_API_KEY")


def load_config() -> dict | None:
    if not CONFIG_PATH.exists():
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not all(k in data and data[k] for k in REQUIRED_KEYS):
        return None
    return data


def save_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def prompt_for_credentials() -> dict:
    print("First-time setup: enter your free-tier API keys (input hidden).")
    mistral_key = getpass("Mistral API key: ").strip()
    tavily_key = getpass("Tavily API key: ").strip()
    return {"MISTRAL_API_KEY": mistral_key, "TAVILY_API_KEY": tavily_key}


def get_credentials() -> dict:
    """Load cached credentials, or prompt and cache them if missing."""
    data = load_config()
    if data is not None:
        return data
    data = prompt_for_credentials()
    save_config(data)
    return data


def logout() -> bool:
    """Delete the cached credentials file. Returns True if a file was removed."""
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        return True
    return False
