"""Tavily web search API wrapper."""

import requests

TAVILY_URL = "https://api.tavily.com/search"


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
