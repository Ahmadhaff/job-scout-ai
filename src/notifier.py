"""Send match alerts through the Telegram Bot API."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from .evaluator import Evaluation
from .fetchers import JobListing

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20.0
# Telegram MarkdownV2 reserved characters.
_MARKDOWN_V2_SPECIALS = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


class NotifierError(RuntimeError):
    """Raised when Telegram rejects or cannot receive an alert."""


class TelegramNotifier:
    """Thin client for sendMessage."""

    def __init__(self, token: str, chat_id: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if not token or not chat_id:
            raise NotifierError("Telegram token and chat id are required.")
        self._token = token
        self._chat_id = chat_id
        self._timeout = timeout

    def send_job_alert(
        self,
        job: JobListing,
        evaluation: Evaluation,
        *,
        resume_attached: bool = False,
    ) -> None:
        message = format_alert(
            title=job.title,
            link=job.link,
            match_score=evaluation.match_score,
            is_startup=evaluation.is_startup,
            summary=evaluation.summary,
            resume_attached=resume_attached,
        )
        self.send_message(message)

    def send_document(self, path: Path, *, caption: str) -> None:
        endpoint = f"https://api.telegram.org/bot{self._token}/sendDocument"
        safe_caption = re.sub(r"\s+", " ", caption).strip()[:1000]
        try:
            with path.open("rb") as handle:
                response = requests.post(
                    endpoint,
                    data={"chat_id": self._chat_id, "caption": safe_caption},
                    files={"document": (path.name, handle, "application/pdf")},
                    timeout=max(self._timeout, 60.0),
                )
        except requests.RequestException as exc:
            raise NotifierError(f"Telegram document upload failed ({exc.__class__.__name__}).") from None
        except OSError as exc:
            raise NotifierError(f"Could not read résumé file {path.name}.") from exc

        if response.status_code != 200:
            detail = response.text[:300].replace("\n", " ")
            raise NotifierError(f"Telegram API returned HTTP {response.status_code}: {detail}")
        try:
            body = response.json()
        except ValueError as exc:
            raise NotifierError("Telegram API returned invalid JSON.") from exc
        if not isinstance(body, dict) or not body.get("ok"):
            description = "unknown error"
            if isinstance(body, dict):
                description = str(body.get("description") or description)
            raise NotifierError(f"Telegram API error: {description}")
        logger.debug("Telegram résumé delivered (%s).", path.name)

    def send_message(self, text: str) -> None:
        endpoint = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
        }
        try:
            response = requests.post(endpoint, json=payload, timeout=self._timeout)
        except requests.RequestException as exc:
            # Do not chain the requests error: its message includes the bot token in the URL.
            raise NotifierError(f"Telegram request failed ({exc.__class__.__name__}).") from None

        if response.status_code != 200:
            detail = response.text[:300].replace("\n", " ")
            raise NotifierError(f"Telegram API returned HTTP {response.status_code}: {detail}")

        try:
            body = response.json()
        except ValueError as exc:
            raise NotifierError("Telegram API returned invalid JSON.") from exc
        if not isinstance(body, dict) or not body.get("ok"):
            description = "unknown error"
            if isinstance(body, dict):
                description = str(body.get("description") or description)
            raise NotifierError(f"Telegram API error: {description}")
        logger.debug("Telegram alert delivered (%s chars).", len(text))


def format_alert(
    *,
    title: str,
    link: str,
    match_score: int,
    is_startup: bool,
    summary: str,
    resume_attached: bool = False,
) -> str:
    """Build a MarkdownV2 Telegram message for one high-scoring role."""
    startup = "Yes" if is_startup else "No"
    lines = [
        r"*job\-scout\-ai*",
        f"*{escape_markdown_v2(_trim(title, 240))}*",
        f"Match: {match_score}/10",
        f"Startup: {startup}",
        "",
        escape_markdown_v2(_trim(summary, 900)),
    ]
    if resume_attached:
        lines.extend(["", r"Tailored resume PDF follows\."])
    if link:
        lines.extend(["", f"[View role]({escape_link_destination(link)})"])
    return "\n".join(lines)


def escape_markdown_v2(text: str) -> str:
    """Escape text for Telegram MarkdownV2."""
    return _MARKDOWN_V2_SPECIALS.sub(r"\\\1", text)


def escape_link_destination(url: str) -> str:
    """Escape the characters Telegram requires inside a MarkdownV2 link target."""
    return url.replace("\\", "\\\\").replace(")", "\\)")


def _trim(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"
