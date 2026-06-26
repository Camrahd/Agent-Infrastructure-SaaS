"""Tools available to LangGraph agents.

Each tool is a LangChain ``@tool`` so it can be bound directly to a chat model
via ``llm.bind_tools([...])``. Keep tool functions small, side-effect-light,
and string-returning — the agent loop expects plain text observations.

Add new tools below ``web_search`` and re-export them from ``ALL_TOOLS`` so
they are picked up wherever the agent graph is assembled.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from langchain_core.tools import tool

_USER_AGENT = "agent-infra-backend/0.1 (+https://localhost)"
_DEFAULT_TIMEOUT_S = 20.0
_MAX_RESULT_CHARS = 20_000  # keep observations inside LLM context windows


def _http_get(url: str, *, timeout: float = _DEFAULT_TIMEOUT_S) -> str:
    """GET ``url`` and return the response body decoded as text.

    Raises ``urllib.error.URLError`` / ``HTTPError`` on failure — callers
    should catch these and return a user-readable error string so the LLM
    can react instead of crashing the agent loop.
    """
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


@tool
def web_search(query: str, num_results: int = 5) -> str:
    """Search the public web via DuckDuckGo's HTML endpoint.

    Use this when you need current public information such as cloud pricing,
    LLM model release notes, or vendor documentation that is not already
    in your training data. Returns up to ``num_results`` hits as plain text
    in the form::

        1. <title>
           <url>
           <snippet>

    Args:
        query: Natural-language search query (e.g. "AWS ECS Fargate pricing
            per vCPU hour").
        num_results: Number of hits to return, between 1 and 20. Defaults to 5.

    Returns:
        Formatted search results, or an error / "no results" string that the
        agent can reason about without raising.
    """
    if not query or not query.strip():
        return "Error: query must be a non-empty string."
    if not isinstance(num_results, int) or not 1 <= num_results <= 20:
        return "Error: num_results must be an integer between 1 and 20."

    search_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
        {"q": query.strip(), "kl": "us-en"}
    )
    try:
        html = _http_get(search_url)
    except Exception as exc:  # URLError, HTTPError, TimeoutError, ...
        return f"Error searching for {query!r}: {exc}"

    # DuckDuckGo HTML result markup (stable for several years):
    #   <a class="result__a" href="...">title</a>
    #   <a class="result__snippet">snippet text</a>
    # We don't pull in BeautifulSoup — a regex over the well-known class
    # names is enough for our purposes and keeps the dep footprint minimal.
    title_re = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_re = re.compile(
        r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    titles = list(title_re.finditer(html))[:num_results]
    snippets = list(snippet_re.finditer(html))[:num_results]

    blocks: list[str] = []
    for index, (title_match, snippet_match) in enumerate(zip(titles, snippets), start=1):
        # Strip any nested tags inside title/snippet, then collapse whitespace.
        title = _strip_tags(title_match.group("title"))
        snippet = _strip_tags(snippet_match.group("snippet"))
        href = title_match.group("href").strip()
        blocks.append(f"{index}. {title}\n   {href}\n   {snippet}")

    if not blocks:
        return f"No results found for {query!r}."
    rendered = "\n\n".join(blocks)
    return rendered[:_MAX_RESULT_CHARS]


def _strip_tags(raw_html: str) -> str:
    """Remove HTML tags and collapse whitespace from a fragment."""
    text = re.sub(r"<[^>]+>", "", raw_html)
    return re.sub(r"\s+", " ", text).strip()


# Public registry — import this from the agent graph code instead of
# importing individual tools, so adding a new tool only requires editing
# this file and not every agent that uses it.
ALL_TOOLS = [web_search]


__all__ = ["web_search", "ALL_TOOLS"]
