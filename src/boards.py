"""Fetch public listing pages from Keejob, Tanitjobs, and Free-Work."""

from __future__ import annotations

import logging
import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from .fetchers import (
    MAX_DESCRIPTION_CHARS,
    USER_AGENT,
    FetchError,
    JobListing,
    html_to_text,
    stable_job_id,
)

logger = logging.getLogger(__name__)

MAX_DETAIL_PAGES = 12
DETAIL_DELAY_SECONDS = 0.4

_SOFTWARE_TITLE_RE = re.compile(
    r"d[ée]veloppeur|developer|full[\s-]?stack|front[\s-]?end|back[\s-]?end|"
    r"software|logiciel|react|next|node|nest|web|data|intelligence artificielle|\bai\b",
    re.IGNORECASE,
)
_KEEJOB_JOB_RE = re.compile(
    r'href="(/offres-emploi/(\d+)/[^"?#]+)(?:\?[^"]*)?"[^>]*>\s*([^<]{3,180}?)\s*</a>',
    re.IGNORECASE,
)
_TANIT_CARD_RE = re.compile(r'class="sj-job-card\b', re.IGNORECASE)
_TANIT_LINK_RE = re.compile(
    r'href="(https://www\.tanitjobs\.com/job/\d+/[^"]+)"[^>]*>\s*([^<]{3,180}?)\s*</a>',
    re.IGNORECASE,
)
_FREEWORK_JOB_RE = re.compile(
    r'href="(/fr/tech-it/job-mission/[^"]+)"[^>]*>([\s\S]{0,900}?)</a>',
    re.IGNORECASE,
)
_FREEWORK_TAG_RE = re.compile(
    r'class="[^"]*\btag\b[^"]*"[^>]*>\s*([^<]{1,40})\s*</span>',
    re.IGNORECASE,
)


def is_board_url(url: str) -> bool:
    """Return True when the URL is an HTML listing page rather than an RSS feed."""
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.endswith("keejob.com") or host.endswith("free-work.com"):
        return True
    return host.endswith("tanitjobs.com") and "/rss" not in parts.path


def fetch_board(url: str, *, timeout: float) -> list[JobListing]:
    """Download one board listing page and return normalized jobs."""
    host = urlsplit(url).netloc.lower()
    html = _get(url, timeout=timeout)
    if host.endswith("keejob.com"):
        return _fetch_keejob(url, html, timeout=timeout)
    if host.endswith("tanitjobs.com"):
        return _parse_tanit(url, html)
    if host.endswith("free-work.com"):
        return _parse_freework(url, html)
    raise FetchError(f"unsupported board: {host}")


def _fetch_keejob(page_url: str, html: str, *, timeout: float) -> list[JobListing]:
    cards = _parse_keejob_cards(page_url, html)
    listings: list[JobListing] = []
    details = 0
    for card in cards:
        description = card[2]
        if details < MAX_DETAIL_PAGES and _SOFTWARE_TITLE_RE.search(card[0]):
            if details:
                time.sleep(DETAIL_DELAY_SECONDS)
            try:
                detail_html = _get(card[1], timeout=timeout)
            except FetchError as exc:
                logger.warning("Keejob detail skipped (%s): %s", card[1], exc)
            else:
                detail = _text_inside_class(detail_html, "prose")
                if len(detail) > len(description):
                    description = detail
                details += 1
        listing = _listing(card[0], card[1], description, page_url)
        if listing is not None:
            listings.append(listing)
    return listings


def _parse_keejob_cards(page_url: str, html: str) -> list[tuple[str, str, str]]:
    cards: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for match in _KEEJOB_JOB_RE.finditer(html):
        title = _clean(match.group(3))
        link = _canonical(page_url, match.group(1))
        if not title or link in seen:
            continue
        seen.add(link)
        company = _keejob_company(html, match.end())
        description = f"{company}. {title}".strip(". ") if company else title
        cards.append((title, link, description))
    return cards


def _keejob_company(html: str, start: int) -> str:
    window = html[start : start + 700]
    match = re.search(
        r'href="/offres-emploi/entreprises/[^"]+"[^>]*>\s*([^<]{2,120}?)\s*</a>',
        window,
        re.IGNORECASE,
    )
    return _clean(match.group(1)) if match else ""


def _parse_tanit(page_url: str, html: str) -> list[JobListing]:
    listings: list[JobListing] = []
    seen: set[str] = set()
    parts = _TANIT_CARD_RE.split(html)
    for part in parts[1:]:
        match = _TANIT_LINK_RE.search(part)
        if match is None:
            continue
        link = _canonical(page_url, match.group(1))
        title = _clean(match.group(2))
        if not title or link in seen:
            continue
        # The first anchor is often the logo. Prefer the title block when present.
        title_match = re.search(
            r'sj-card-title[\s\S]{0,400}?href="https://www\.tanitjobs\.com/job/\d+/[^"]+"[^>]*>\s*([^<]{3,180}?)\s*</a>',
            part,
            re.IGNORECASE,
        )
        if title_match:
            title = _clean(title_match.group(1))
            link_match = re.search(
                r'sj-card-title[\s\S]{0,200}?href="(https://www\.tanitjobs\.com/job/\d+/[^"]+)"',
                part,
                re.IGNORECASE,
            )
            if link_match:
                link = _canonical(page_url, link_match.group(1))
        if link in seen:
            continue
        seen.add(link)
        company = ""
        company_match = re.search(
            r'sj-card-company[\s\S]{0,400}?<a[^>]*>\s*([^<]{2,120}?)\s*</a>',
            part,
            re.IGNORECASE,
        )
        if company_match:
            company = _clean(company_match.group(1))
        snippet = ""
        snippet_match = re.search(r'sj-card-desc[^>]*>\s*([\s\S]*?)</div>', part, re.IGNORECASE)
        if snippet_match:
            snippet = html_to_text(snippet_match.group(1))
        description = " ".join(piece for piece in (company, snippet) if piece)
        listing = _listing(title, link, description or title, page_url)
        if listing is not None:
            listings.append(listing)
    return listings


def _parse_freework(page_url: str, html: str) -> list[JobListing]:
    listings: list[JobListing] = []
    seen: set[str] = set()
    for match in _FREEWORK_JOB_RE.finditer(html):
        link = _canonical(page_url, match.group(1))
        title = _clean(re.sub(r"<[^>]+>", " ", match.group(2)))
        if not title or link in seen or "/forum/" in link:
            continue
        seen.add(link)
        window = html[match.end() : match.end() + 2500]
        skills = []
        for skill in _FREEWORK_TAG_RE.findall(window):
            cleaned = _clean(skill)
            if cleaned and cleaned not in skills:
                skills.append(cleaned)
            if len(skills) == 12:
                break
        description = title if not skills else f"{title}. Skills: {', '.join(skills)}"
        listing = _listing(title, link, description, page_url)
        if listing is not None:
            listings.append(listing)
    return listings


def _listing(title: str, link: str, description: str, source: str) -> JobListing | None:
    title = _clean(title)
    description = html_to_text(description)
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    if len(title) < 3:
        return None
    return JobListing(
        id=stable_job_id("", link, title),
        title=title,
        link=link,
        description=description,
        source=source,
    )


def _text_inside_class(html: str, class_token: str) -> str:
    parser = _ClassText(class_token)
    parser.feed(html)
    parser.close()
    return html_to_text(parser.text())


class _ClassText(HTMLParser):
    """Collect text from elements whose class contains a token, keeping the longest block."""

    def __init__(self, token: str) -> None:
        super().__init__(convert_charrefs=True)
        self._token = token
        self._depth = 0
        self._current: list[str] = []
        self._blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = dict(attrs).get("class") or ""
        if self._depth:
            self._depth += 1
        elif _class_has_token(classes, self._token):
            self._depth = 1
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if not self._depth:
            return
        self._depth -= 1
        if self._depth == 0:
            self._blocks.append("".join(self._current))
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._depth:
            self._current.append(data)

    def text(self) -> str:
        if not self._blocks:
            return ""
        return max(self._blocks, key=len)


def _get(url: str, *, timeout: float) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise FetchError(f"request failed ({exc.__class__.__name__})") from exc
    if response.status_code != 200:
        raise FetchError(f"HTTP {response.status_code}")
    return response.text


def _class_has_token(classes: str, token: str) -> bool:
    for item in classes.split():
        if item == token or item.startswith(f"{token}-") or item.startswith(f"{token}:"):
            return True
    return False


def _canonical(base: str, href: str) -> str:
    absolute = urljoin(base, href)
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _clean(value: str) -> str:
    text = html_to_text(value)
    return re.sub(r"\s+", " ", text).strip()
