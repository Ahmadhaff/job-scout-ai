"""Render a one-page résumé in the same structure as the English CV."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .resume_facts import Candidate, ResumeError

LINK_COLOR = "#1a4f8b"
RULE_COLOR = HexColor("#222222")


def render_resume(candidate: Candidate, destination: Path) -> Path:
    """Write a one-page A4 PDF and return its path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=32,
        bottomMargin=28,
        title=f"{candidate.name} — {candidate.headline}",
        author=candidate.name,
    )
    styles = _styles()
    story = _story(candidate, document.width, styles)
    document.build(story)
    if not destination.is_file() or destination.stat().st_size < 1000:
        raise ResumeError(f"Résumé PDF was not written to {destination}.")
    return destination


def _story(candidate: Candidate, width: float, styles: dict[str, ParagraphStyle]) -> list:
    story: list = [
        Paragraph(_esc(candidate.name), styles["name"]),
        Paragraph(_esc(candidate.headline), styles["headline"]),
        Paragraph(_esc(candidate.education), styles["education"]),
        Paragraph(_contact_line(candidate), styles["contact"]),
        Spacer(1, 4),
    ]
    story.extend(_section("Profile", width, styles))
    story.append(Paragraph(_esc(candidate.profile), styles["profile"]))
    story.extend(_section("Skills", width, styles))
    for group in candidate.skills:
        story.append(
            Paragraph(f"<b>{_esc(group.label)}:</b> {_esc(group.items)}", styles["skill"])
        )
    story.extend(_section("Experience", width, styles))
    for role in candidate.roles:
        story.append(
            _pair(
                f"<b>{_esc(role.title)}</b>",
                _esc(role.location),
                styles["role"],
                styles["place"],
                width,
            )
        )
        story.append(
            _pair(
                f"<i>{_esc(role.company)}</i>",
                f"<i>{_esc(role.dates)}</i>",
                styles["company"],
                styles["meta_right"],
                width,
            )
        )
        for bullet in role.bullets:
            story.append(Paragraph(f"• {_esc(bullet)}", styles["bullet"]))
        story.append(Spacer(1, 3))
    story.extend(_section("Featured Projects", width, styles))
    for project in candidate.projects:
        story.append(
            _pair(
                f"<b>{_esc(project.name)}</b> | <i>{_esc(project.stack)}</i>",
                _esc(project.dates),
                styles["project"],
                styles["meta_right"],
                width,
            )
        )
        for bullet in project.bullets:
            story.append(Paragraph(f"• {_esc(bullet)}", styles["bullet"]))
    return story


def _section(title: str, width: float, styles: dict[str, ParagraphStyle]) -> list:
    rule = HRFlowable(width=width, thickness=0.6, color=RULE_COLOR, spaceBefore=1, spaceAfter=3)
    return [Spacer(1, 6), Paragraph(_esc(title), styles["section"]), rule]


def _pair(
    left: str,
    right: str,
    left_style: ParagraphStyle,
    right_style: ParagraphStyle,
    width: float,
) -> Table:
    table = Table(
        [[Paragraph(left, left_style), Paragraph(right, right_style)]],
        colWidths=[width * 0.72, width * 0.28],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _contact_line(candidate: Candidate) -> str:
    email = (
        f'<link href="mailto:{candidate.email}">'
        f'<font color="{LINK_COLOR}">{_esc(candidate.email)}</font></link>'
    )
    parts = [f"{_esc(candidate.location)} | {email}"]
    for link in candidate.links:
        parts.append(
            f'<link href="{link.url}"><font color="{LINK_COLOR}">{_esc(link.label)}</font></link>'
        )
    return " | ".join(parts)


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "name": ParagraphStyle(
            "name",
            fontName="Times-Bold",
            fontSize=18,
            leading=21,
            alignment=TA_CENTER,
            textColor=black,
            spaceAfter=1,
        ),
        "headline": ParagraphStyle(
            "headline",
            fontName="Times-Bold",
            fontSize=11,
            leading=13,
            alignment=TA_CENTER,
            textColor=black,
            spaceBefore=1,
            spaceAfter=1,
        ),
        "education": ParagraphStyle(
            "education",
            fontName="Times-Roman",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=black,
        ),
        "contact": ParagraphStyle(
            "contact",
            fontName="Times-Roman",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=black,
            spaceBefore=1,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="Times-Bold",
            fontSize=12,
            leading=14,
            alignment=TA_LEFT,
            textColor=black,
            spaceBefore=0,
            spaceAfter=0,
        ),
        "profile": ParagraphStyle(
            "profile",
            fontName="Times-Roman",
            fontSize=9.5,
            leading=12,
            alignment=TA_JUSTIFY,
            textColor=black,
        ),
        "skill": ParagraphStyle(
            "skill",
            fontName="Times-Roman",
            fontSize=9.5,
            leading=12,
            alignment=TA_LEFT,
            textColor=black,
            spaceAfter=1,
        ),
        "role": ParagraphStyle(
            "role",
            fontName="Times-Bold",
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
            textColor=black,
        ),
        "company": ParagraphStyle(
            "company",
            fontName="Times-Italic",
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            textColor=black,
        ),
        "project": ParagraphStyle(
            "project",
            fontName="Times-Roman",
            fontSize=9,
            leading=11.5,
            alignment=TA_LEFT,
            textColor=black,
            spaceBefore=2,
        ),
        "place": ParagraphStyle(
            "place",
            fontName="Times-Roman",
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
            textColor=black,
        ),
        "meta_right": ParagraphStyle(
            "meta_right",
            fontName="Times-Italic",
            fontSize=9,
            leading=11,
            alignment=TA_RIGHT,
            textColor=black,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName="Times-Roman",
            fontSize=9.5,
            leading=11.5,
            alignment=TA_LEFT,
            textColor=black,
            leftIndent=12,
            firstLineIndent=0,
            spaceBefore=0,
            spaceAfter=0,
        ),
    }


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
