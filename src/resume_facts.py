"""Canonical résumé facts taken from the English CV.

Tailoring may rewrite the headline and profile, and may reorder projects.
Employers, dates, products, and metrics stay fixed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace


class ResumeError(RuntimeError):
    """Raised when résumé copy cannot be parsed or written."""


@dataclass(frozen=True)
class ContactLink:
    label: str
    url: str


@dataclass(frozen=True)
class SkillGroup:
    label: str
    items: str


@dataclass(frozen=True)
class Role:
    title: str
    location: str
    company: str
    dates: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    stack: str
    dates: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    name: str
    headline: str
    education: str
    location: str
    email: str
    links: tuple[ContactLink, ...]
    profile: str
    skills: tuple[SkillGroup, ...]
    roles: tuple[Role, ...]
    projects: tuple[Project, ...]


@dataclass(frozen=True)
class TailoredCopy:
    """Job-specific headline, profile, and project order. Facts stay on the candidate."""

    headline: str
    profile: str
    project_order: tuple[str, ...]


CANDIDATE = Candidate(
    name="Ahmad Haffoudhi",
    headline="Full-Stack Software Engineer",
    education="EPI Polytechnique, Sousse — B.S. Computer Science (Software Engineering & Cloud Systems)",
    location="Sousse, Tunisia",
    email="haffoudhi.ahmaad@gmail.com",
    links=(
        ContactLink("Portfolio", "https://ahmad-portfolio-2025.netlify.app/"),
        ContactLink("LinkedIn", "https://www.linkedin.com/in/ahmad-haffoudhi-70863b268/"),
        ContactLink("GitHub", "https://github.com/Ahmadhaff"),
    ),
    profile=(
        "Full-stack software engineer, 5+ years. Production web, mobile, and AI products "
        "(React, Next.js, NestJS, TypeScript, Flutter, PostgreSQL): APIs, payments, realtime, and SaaS."
    ),
    skills=(
        SkillGroup(
            "Languages & frameworks",
            "React, Next.js, Node.js, NestJS, TypeScript, JavaScript, Express, Python, Go, C#, "
            "FastAPI, ASP.NET Core, Angular, Flutter, React Native",
        ),
        SkillGroup(
            "Data",
            "PostgreSQL, Prisma, Redis, MySQL, MongoDB, Entity Framework Core, GORM",
        ),
        SkillGroup(
            "Integrations & architecture",
            "REST APIs, GraphQL, WebSockets, webhooks, JWT, Stripe, PayPal, CI/CD",
        ),
        SkillGroup("Infra", "Git, Docker, GitHub Actions, AWS, Vercel, Linux"),
        SkillGroup("Languages", "English (Fluent), French (Fluent), Arabic (Native)"),
    ),
    roles=(
        Role(
            title="Full-Stack & AI Developer",
            location="Remote",
            company="Exceed Your Limits Marketing",
            dates="Mar 2026 – Present",
            bullets=(
                "Building production AI and SaaS platforms (AdSignals AI, NexusAI, EYL Educate): "
                "Next.js, NestJS, TypeScript, PostgreSQL.",
                "Dashboards, REST APIs, checkout, credit / commission engines, and AI onboarding, "
                "from architecture to production.",
            ),
        ),
        Role(
            title="Full-Stack Developer",
            location="Sousse, Tunisia",
            company="Solutech Pro",
            dates="May 2023 – Jun 2026",
            bullets=(
                "Shipped Click Services, Feelsafe, Niagara Tech, OliviaShop and Bipperz: "
                "marketplaces, e-commerce, Stripe, and mobile apps.",
                "Mentored students: code review, CI/CD, and full-stack delivery. "
                "Apps published on the App Store and Google Play.",
            ),
        ),
        Role(
            title="Full-Stack Developer",
            location="Sousse, Tunisia",
            company="Freelance",
            dates="2021 – May 2023",
            bullets=(
                "Built web and mobile products for international clients: Node.js APIs, "
                "React interfaces, SQL / NoSQL databases.",
            ),
        ),
    ),
    projects=(
        Project(
            id="eyl-educate",
            name="EYL Educate",
            stack="C#, ASP.NET Core, Angular, Python, PostgreSQL",
            dates="Sep 2026 – Present",
            bullets=(
                "Education commerce: white-labeled checkout, catalogs, affiliate commissions, and AI onboarding.",
            ),
        ),
        Project(
            id="adsignals",
            name="AdSignals AI",
            stack="Next.js, NestJS, PostgreSQL, Redis, OpenAI",
            dates="Mar 2026 – Present",
            bullets=(
                "AI ads platform: campaign research, creative generation, LLM pipelines, role-based dashboards.",
            ),
        ),
        Project(
            id="nexusai",
            name="NexusAI",
            stack="Next.js, NestJS, Prisma, PostgreSQL, Redis, Stripe",
            dates="Jun 2025 – Present",
            bullets=(
                "AI generation SaaS: SSE streaming, JWT, Stripe credits, and Redis / BullMQ metering.",
            ),
        ),
        Project(
            id="oliviashop",
            name="OliviaShop",
            stack="React, Redux, Stripe, PayPal",
            dates="Apr 2025 – Present",
            bullets=("E-commerce storefront: catalog, cart, and Stripe / PayPal checkout.",),
        ),
        Project(
            id="bipperz",
            name="Bipperz",
            stack="Flutter, Firebase, Stream Chat, Stripe",
            dates="Apr 2025 – Present",
            bullets=(
                "Jobs app on the App Store and Google Play: chat, CV onboarding, Stripe, EN/DE localization.",
            ),
        ),
        Project(
            id="niagara",
            name="Niagara Tech",
            stack="React, Next.js, NestJS, Node.js, PostgreSQL, Docker",
            dates="May 2023 – Jun 2026",
            bullets=(
                "Full-stack delivery: NestJS APIs, React / Next.js apps, PostgreSQL / MongoDB, and Flutter modules.",
            ),
        ),
        Project(
            id="feelsafe",
            name="Feelsafe",
            stack="Next.js, React Native, Node.js, PostgreSQL, Socket.IO",
            dates="Sep 2024 – Feb 2025",
            bullets=(
                "Live location, alerts, OneSignal; apps published on the App Store and Google Play.",
            ),
        ),
        Project(
            id="click-services",
            name="Click Services",
            stack="Node.js, Express, MongoDB, Redis, Socket.IO, Stripe",
            dates="Feb 2023 – Jun 2023",
            bullets=(
                "Marketplace API: wallets, Stripe payments, live chat; MongoDB latency cut by 30%.",
            ),
        ),
    ),
)

_PROJECT_IDS = tuple(project.id for project in CANDIDATE.projects)
_FENCE_RE = re.compile(r"^```[a-zA-Z0-9]*\s*|\s*```$", re.MULTILINE)


def assemble(copy: TailoredCopy | None = None) -> Candidate:
    """Apply a headline, profile, and project order onto the fixed CV facts."""
    if copy is None:
        return CANDIDATE
    headline = copy.headline.strip() or CANDIDATE.headline
    profile = copy.profile.strip() or CANDIDATE.profile
    return replace(
        CANDIDATE,
        headline=headline,
        profile=profile,
        projects=order_projects(copy.project_order),
    )


def order_projects(project_order: tuple[str, ...]) -> tuple[Project, ...]:
    """Reorder known projects. Unknown ids are ignored. Missing ids keep their original place at the end."""
    by_id = {project.id: project for project in CANDIDATE.projects}
    ordered: list[Project] = []
    seen: set[str] = set()
    for project_id in project_order:
        project = by_id.get(project_id)
        if project is None or project_id in seen:
            continue
        seen.add(project_id)
        ordered.append(project)
    for project in CANDIDATE.projects:
        if project.id not in seen:
            ordered.append(project)
    return tuple(ordered)


def parse_tailored_copy(raw: str) -> TailoredCopy:
    """Parse the JSON résumé tailoring payload."""
    text = _FENCE_RE.sub("", raw.strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResumeError("Résumé tailoring response was not JSON.") from exc
    if not isinstance(data, dict):
        raise ResumeError("Résumé tailoring response was not a JSON object.")

    headline = _clean_line(data.get("headline"), field="headline", minimum=8, maximum=70)
    profile = _clean_line(data.get("profile"), field="profile", minimum=40, maximum=420)
    order = data.get("project_order")
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise ResumeError("project_order must be a list of project ids.")
    known = set(_PROJECT_IDS)
    project_order = tuple(item.strip() for item in order if item.strip() in known)
    if not project_order:
        raise ResumeError("project_order did not include a known project.")
    return TailoredCopy(headline=headline, profile=profile, project_order=project_order)


def resume_filename(title: str, job_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")[:50]
    stem = slug or job_id[:12] or "role"
    return f"Ahmad_Haffoudhi_{stem}.pdf"


def _clean_line(value: object, *, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ResumeError(f"{field} is missing.")
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) < minimum or len(cleaned) > maximum:
        raise ResumeError(f"{field} must be between {minimum} and {maximum} characters.")
    return cleaned
