"""Tavily web search API wrapper."""

import os
from pathlib import Path

import requests

TAVILY_URL = "https://api.tavily.com/search"

# Machines behind a TLS-inspecting proxy present a self-signed root that isn't in
# certifi's bundle, so requests fails with CERTIFICATE_VERIFY_FAILED even though
# the network is fine. Honor the usual CA-bundle env vars, then fall back to a
# root cert kept at ~/Documents/root-cert.pem if one is there.
_FALLBACK_CA_CERT = Path.home() / "Documents" / "root-cert.pem"


def _ca_bundle():
    """Return a CA-bundle path for requests' `verify=`, or True for the default."""
    for env_var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        path = os.environ.get(env_var)
        if path and Path(path).is_file():
            return path
    if _FALLBACK_CA_CERT.is_file():
        return str(_FALLBACK_CA_CERT)
    return True


def search(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    """Run a Tavily search, return a list of {title, url, content} dicts.

    Raises requests.RequestException on network/HTTP failure.
    """
    response = requests.post(
        TAVILY_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={"query": query, "max_results": max_results},
        timeout=15,
        verify=_ca_bundle(),
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        }
        for r in results
    ]


def format_results(results: list[dict]) -> str:
    """Format search results as text suitable for injecting into a chat prompt."""
    if not results:
        return "No web search results found."
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r['title']} ({r['url']})\n   {r['content']}")
    return "\n".join(lines)
