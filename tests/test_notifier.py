"""Tests for Telegram MarkdownV2 alerts."""

from __future__ import annotations

import unittest

from src.notifier import escape_markdown_v2, format_alert


class NotifierFormatTests(unittest.TestCase):
    def test_escape_specials(self) -> None:
        escaped = escape_markdown_v2("Senior_Engineer (Go).")
        self.assertIn(r"\_", escaped)
        self.assertIn(r"\(", escaped)
        self.assertIn(r"\.", escaped)

    def test_format_alert(self) -> None:
        text = format_alert(
            title="Backend Engineer (Go)",
            link="https://example.com/jobs/1",
            match_score=9,
            is_startup=True,
            summary="Strong Go match at a small startup. The role is remote and senior.",
        )
        self.assertIn("Match: 9/10", text)
        self.assertIn("Startup: Yes", text)
        self.assertIn(r"Backend Engineer \(Go\)", text)
        self.assertIn(r"Strong Go match at a small startup\.", text)
        self.assertIn("[View role](https://example.com/jobs/1)", text)

    def test_link_parentheses_are_escaped(self) -> None:
        text = format_alert(
            title="Platform Engineer",
            link="https://example.com/job_(go)",
            match_score=8,
            is_startup=False,
            summary="Solid backend work, with less evidence that the company is a startup.",
        )
        self.assertIn(r"[View role](https://example.com/job_(go\))", text)
        self.assertIn("Startup: No", text)


if __name__ == "__main__":
    unittest.main()
