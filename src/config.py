"""Environment settings and the candidate profile sent to Claude."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# claude-3-5-sonnet-latest was retired on 2025-10-28. Sonnet 5.5 is the active replacement.
DEFAULT_MODEL = "claude-sonnet-5-5"
HN_JOBS_FEED = "https://hnrss.org/jobs"
HN_WHO_IS_HIRING_FEED = "https://hnrss.org/whoishiring/jobs?q=engineer"
KEEJOB_IT_FEED = "https://www.keejob.com/offres-emploi/metiers/recrutement-informatique-multimedia/"
KEEJOB_DEV_FEED = "https://www.keejob.com/offres-emploi/?keywords=developpeur"
TANIT_IT_FEED = "https://www.tanitjobs.com/categories/705/informatique-jobs/"
TANIT_TECH_FEED = "https://www.tanitjobs.com/categories/381/technologie-de-l-information-jobs/"
FREEWORK_REACT_FEED = "https://www.free-work.com/fr/tech-it/jobs?query=react"
FREEWORK_NEST_FEED = "https://www.free-work.com/fr/tech-it/jobs?query=nestjs"
FREEWORK_NODE_FEED = "https://www.free-work.com/fr/tech-it/jobs?query=node.js"
FREEWORK_NEXT_FEED = "https://www.free-work.com/fr/tech-it/jobs?query=next.js"
DEFAULT_FEEDS: tuple[str, ...] = (
    HN_JOBS_FEED,
    HN_WHO_IS_HIRING_FEED,
    KEEJOB_IT_FEED,
    KEEJOB_DEV_FEED,
    TANIT_IT_FEED,
    TANIT_TECH_FEED,
    FREEWORK_REACT_FEED,
    FREEWORK_NEST_FEED,
    FREEWORK_NODE_FEED,
    FREEWORK_NEXT_FEED,
)
REQUIRED_ENV: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class DeveloperProfile:
    """Target candidate used to judge each listing."""

    title: str
    summary: str
    skills: tuple[str, ...]
    preferences: tuple[str, ...]

    def as_prompt_block(self) -> str:
        skills = ", ".join(self.skills)
        preferences = "\n".join(f"- {item}" for item in self.preferences)
        return (
            f"Role target: {self.title}\n"
            f"Summary: {self.summary}\n"
            f"Core skills: {skills}\n"
            f"Preferences:\n{preferences}"
        )


DEVELOPER_PROFILE = DeveloperProfile(
    title="Full-Stack & AI Engineer",
    summary=(
        "Full-stack and AI engineer with 5+ years shipping production web and AI products. "
        "Core stack is React, Next.js, Node.js, NestJS, and PostgreSQL, including LLM "
        "pipelines, AI SaaS, dashboards, and payments."
    ),
    skills=(
        "React",
        "Next.js",
        "Node.js",
        "NestJS",
        "PostgreSQL",
        "TypeScript",
        "AI engineering",
        "Prisma",
    ),
    preferences=(
        "Roles for React, Next.js, Node.js, NestJS, PostgreSQL, or AI engineering",
        "Remote or remote-friendly startup work",
        "Full-stack product engineering, backend APIs, or applied AI (LLM products and AI SaaS)",
        "Production ownership: architecture, REST APIs, dashboards, and delivery",
        "Junior, intern, sales, recruiting, mobile-only, and unrelated stacks are poor fits",
    ),
)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from the environment."""

    anthropic_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    model: str = DEFAULT_MODEL
    match_threshold: int = 8
    request_delay_seconds: float = 1.5
    max_jobs_per_run: int = 20
    seen_jobs_path: Path = PROJECT_ROOT / "data" / "seen_jobs.json"
    feeds: tuple[str, ...] = DEFAULT_FEEDS

    @classmethod
    def from_env(cls, *, require_credentials: bool = True) -> Settings:
        missing = [name for name in REQUIRED_ENV if not os.getenv(name, "").strip()]
        if require_credentials and missing:
            names = ", ".join(missing)
            raise ConfigError(
                f"Missing required environment variables: {names}. "
                "Copy .env.example to .env or add the GitHub Actions secrets."
            )

        match_threshold = _read_int("MATCH_THRESHOLD", 8)
        if not 1 <= match_threshold <= 10:
            raise ConfigError("MATCH_THRESHOLD must be an integer from 1 to 10.")

        max_jobs = _read_int("MAX_JOBS_PER_RUN", 20)
        if max_jobs < 1:
            raise ConfigError("MAX_JOBS_PER_RUN must be a positive integer.")

        delay = _read_float("REQUEST_DELAY_SECONDS", 1.5)
        if delay < 0:
            raise ConfigError("REQUEST_DELAY_SECONDS must be zero or greater.")

        seen_raw = os.getenv("SEEN_JOBS_PATH", "").strip()
        seen_path = Path(seen_raw) if seen_raw else PROJECT_ROOT / "data" / "seen_jobs.json"
        if not seen_path.is_absolute():
            seen_path = PROJECT_ROOT / seen_path

        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            model=os.getenv("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL,
            match_threshold=match_threshold,
            request_delay_seconds=delay,
            max_jobs_per_run=max_jobs,
            seen_jobs_path=seen_path,
            feeds=_parse_feeds(os.getenv("JOB_FEEDS", "")),
        )


def _parse_feeds(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return DEFAULT_FEEDS
    feeds = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not feeds:
        return DEFAULT_FEEDS
    for feed in feeds:
        if not feed.startswith(("https://", "http://")):
            raise ConfigError(f"JOB_FEEDS entries must be http(s) URLs, got {feed!r}.")
    return feeds


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}.") from exc


_TARGET_STACK_RE = re.compile(
    r"\b(?:react(?:\.js|js)?|next(?:\.js|js)|node(?:\.js|js)?|nest(?:\.js|js)|"
    r"postgres(?:ql)?|ai engineer|ai engineering|applied ai|generative ai|"
    r"machine learning|llm|(?<!\.)ai)\b",
    re.IGNORECASE,
)


def job_targets_stack(title: str, description: str) -> bool:
    """Return True when the listing is in the React / Next / Node / Nest / Postgres / AI lane."""
    return _TARGET_STACK_RE.search(f"{title}\n{description}") is not None


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from exc
