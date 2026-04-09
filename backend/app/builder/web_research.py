"""Web research utility for the AI Scenario Builder.

Fetches and extracts text content from URLs so the builder LLM can
generate scenarios grounded in real company/product information.

# Feature: ai-scenario-builder
# Requirements: web-research-for-builder
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Timeout for HTTP requests (seconds)
_REQUEST_TIMEOUT = 15.0

# Max content length to extract (characters) — keeps LLM context manageable
_MAX_CONTENT_LENGTH = 6000

# URL pattern: matches http(s) URLs in user text
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")

# "Research" intent pattern: user explicitly asks to research something
_RESEARCH_INTENT_RE = re.compile(
    r"\b(?:research|look\s*up|check\s*out|find\s*(?:info|information|out)\s*about|"
    r"learn\s*about|investigate|analyze|review)\b",
    re.IGNORECASE,
)

# Tags whose content we want to skip entirely
_SKIP_TAGS = frozenset({
    "script", "style", "nav", "header", "footer", "aside",
    "noscript", "svg", "iframe", "form",
})

# Tags that typically contain meaningful content
_CONTENT_TAGS = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th",
    "blockquote", "figcaption", "summary", "dt", "dd", "span", "a",
    "strong", "em", "b", "i", "div", "section", "article", "main",
})


class _TextExtractor(HTMLParser):
    """Simple HTML parser that extracts visible text content."""

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0
        self._current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        self._current_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        # Add line break after block-level elements
        if tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "div", "tr"}:
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self._pieces.append(text + " ")

    def get_text(self) -> str:
        raw = "".join(self._pieces)
        # Collapse whitespace
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def extract_urls(text: str) -> list[str]:
    """Extract all HTTP(S) URLs from a text string."""
    return _URL_RE.findall(text)


def has_research_intent(text: str) -> bool:
    """Check if the user message expresses intent to research something."""
    return bool(_RESEARCH_INTENT_RE.search(text))


def _extract_text_from_html(html: str) -> str:
    """Parse HTML and return cleaned visible text."""
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.get_text()
    if len(text) > _MAX_CONTENT_LENGTH:
        text = text[:_MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"
    return text


def _extract_meta(html: str) -> dict[str, str]:
    """Extract title and meta description from HTML."""
    meta: dict[str, str] = {}

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        meta["title"] = title_match.group(1).strip()

    desc_match = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not desc_match:
        desc_match = re.search(
            r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']',
            html,
            re.IGNORECASE | re.DOTALL,
        )
    if desc_match:
        meta["description"] = desc_match.group(1).strip()

    og_desc = re.search(
        r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\'](.*?)["\']',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if og_desc and "description" not in meta:
        meta["description"] = og_desc.group(1).strip()

    return meta


async def fetch_url_content(url: str) -> dict[str, Any]:
    """Fetch a URL and extract text content.

    Returns a dict with:
        - url: the fetched URL
        - success: bool
        - title: page title (if found)
        - description: meta description (if found)
        - content: extracted text content
        - error: error message (if failed)
    """
    result: dict[str, Any] = {"url": url, "success": False}

    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; JuntoAI-Builder/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                result["error"] = f"Non-HTML content type: {content_type}"
                return result

            html = response.text
            meta = _extract_meta(html)
            text = _extract_text_from_html(html)

            result["success"] = True
            result["title"] = meta.get("title", "")
            result["description"] = meta.get("description", "")
            result["content"] = text

    except httpx.TimeoutException:
        result["error"] = f"Request timed out after {_REQUEST_TIMEOUT}s"
        logger.warning("Web research timeout for %s", url)
    except httpx.HTTPStatusError as exc:
        result["error"] = f"HTTP {exc.response.status_code}"
        logger.warning("Web research HTTP error for %s: %s", url, exc.response.status_code)
    except Exception as exc:
        result["error"] = str(exc)
        logger.warning("Web research failed for %s: %s", url, exc)

    return result


async def research_urls(urls: list[str]) -> list[dict[str, Any]]:
    """Fetch multiple URLs concurrently and return their content."""
    import asyncio

    # Cap at 3 URLs to avoid excessive fetching
    urls_to_fetch = urls[:3]
    tasks = [fetch_url_content(url) for url in urls_to_fetch]
    return list(await asyncio.gather(*tasks))


def format_research_context(results: list[dict[str, Any]]) -> str:
    """Format web research results into a context block for the LLM.

    Returns an empty string if no results were successful.
    """
    successful = [r for r in results if r.get("success")]
    if not successful:
        failed_urls = [r["url"] for r in results]
        return (
            f"\n\n[SYSTEM NOTE: Web research attempted but failed for: "
            f"{', '.join(failed_urls)}. Generate the scenario based on "
            f"the URL/company name alone using your knowledge.]"
        )

    parts: list[str] = []
    for r in successful:
        section = f"### Research: {r['url']}\n"
        if r.get("title"):
            section += f"**Title**: {r['title']}\n"
        if r.get("description"):
            section += f"**Description**: {r['description']}\n"
        section += f"\n{r['content']}"
        parts.append(section)

    return (
        "\n\n[SYSTEM NOTE: The following web research was conducted on URLs "
        "the user mentioned. Use this REAL information to create accurate, "
        "grounded agent personas, company details, and negotiation scenarios. "
        "Do NOT hallucinate details — use what's provided below.]\n\n"
        + "\n\n---\n\n".join(parts)
    )
