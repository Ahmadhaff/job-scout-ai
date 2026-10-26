"""Fetch and normalize public job feeds into structured listings."""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

import feedparser
import requests

logger = logging.getLogger(__name__)

USER_AGENT = "job-scout-ai/0.1 (personal job feed reader)"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_DESCRIPTION_CHARS = 8000


class FetchError(RuntimeError):
    """Raised when every configured feed fails."""


@dataclass(frozen=True)
class JobListing:
    """One normalized role from an RSS or Atom feed."""

    id: str
    title: str
    link: str
    description: str
    source: str


class _HTMLTextExtractor(HTMLParser):
    """Collect visible text while dropping script and style blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style"}:
            self._skip_depth += 1
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "li"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def html_to_text(value: str) -> str:
    """Convert an HTML fragment to plain text."""
    parser = _HTMLTextExtractor()
    parser.feed(value)
    parser.close()
    text = parser.text().replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def listing_from_entry(
    entry: Mapping[str, Any],
    source: str,
) -> JobListing | None:
    """Map one feed entry to a listing, or return None when it has no usable content."""
    title = re.sub(r"\s+", " ", html_to_text(str(entry.get("title") or ""))).strip()
    link = str(entry.get("link") or "").strip()
    description = html_to_text(_entry_html(entry))
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    if len(title) < 3 and len(description) < 40:
        return None
    if not title:
        title = "Untitled role"
    entry_id = str(entry.get("id") or entry.get("guid") or "")
    return JobListing(
        id=stable_job_id(entry_id, link, title),
        title=title,
        link=link,
        description=description,
        source=source,
    )


def dedupe_jobs(jobs: Iterable[JobListing]) -> list[JobListing]:
    """Drop duplicate listings, keeping the first copy."""
    unique: list[JobListing] = []
    seen: set[str] = set()
    for job in jobs:
        if job.id in seen:
            continue
        seen.add(job.id)
        unique.append(job)
    return unique


def fetch_jobs(
    feed_urls: Iterable[str],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[JobListing]:
    """Download each feed and return unique listings.

    A single feed failure is logged and skipped. If every feed fails, raise FetchError.
    """
    urls = [url.strip() for url in feed_urls if url.strip()]
    if not urls:
        raise FetchError("No feed URLs configured.")

    collected: list[JobListing] = []
    failures = 0
    for url in urls:
        try:
            batch = _fetch_source(url, timeout=timeout)
        except FetchError as exc:
            failures += 1
            logger.error("Feed failed (%s): %s", url, exc)
            continue
        logger.info("Fetched %s listings from %s", len(batch), url)
        collected.extend(batch)

    if failures == len(urls):
        raise FetchError("All job feeds failed.")

    jobs = dedupe_jobs(collected)
    logger.info("Collected %s unique listings from %s feeds", len(jobs), len(urls))
    return jobs


def _fetch_source(url: str, *, timeout: float) -> list[JobListing]:
    from .boards import fetch_board, is_board_url

    if is_board_url(url):
        return fetch_board(url, timeout=timeout)
    return _fetch_feed(url, timeout=timeout)


def _fetch_feed(url: str, *, timeout: float) -> list[JobListing]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise FetchError(f"request failed ({exc.__class__.__name__})") from exc
    if response.status_code != 200:
        raise FetchError(f"HTTP {response.status_code}")

    parsed = feedparser.parse(response.content)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        reason = getattr(parsed, "bozo_exception", "malformed feed")
        raise FetchError(f"could not parse feed ({reason})")
    if getattr(parsed, "bozo", False):
        logger.warning("Feed parsed with a warning (%s): %s", url, parsed.bozo_exception)

    listings: list[JobListing] = []
    for entry in parsed.entries:
        listing = listing_from_entry(entry, source=url)
        if listing is not None:
            listings.append(listing)
    return listings


def _entry_html(entry: Mapping[str, Any]) -> str:
    summary = entry.get("summary") or entry.get("description")
    if isinstance(summary, str) and summary.strip():
        return summary
    content = entry.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            value = first.get("value")
            if isinstance(value, str):
                return value
    return ""


def stable_job_id(entry_id: str, link: str, title: str) -> str:
    basis = entry_id or link or title
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]
