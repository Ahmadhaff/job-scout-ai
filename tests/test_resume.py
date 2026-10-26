"""Tests for résumé facts, tailoring parse, and PDF output."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.resume_facts import ResumeError, assemble, order_projects, parse_tailored_copy, resume_filename
from src.resume_pdf import render_resume


class ResumeFactTests(unittest.TestCase):
    def test_project_order_keeps_unknown_and_missing_ids_safe(self) -> None:
        ordered = order_projects(("nexusai", "not-a-project", "adsignals", "nexusai"))
        ids = [project.id for project in ordered]
        self.assertEqual(ids[0], "nexusai")
        self.assertEqual(ids[1], "adsignals")
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(set(ids)), 8)

    def test_parse_tailored_copy(self) -> None:
        raw = """```json
{
  "headline": "Full-Stack AI Engineer",
  "profile": "Full-stack engineer shipping React, Next.js, NestJS, and PostgreSQL products. Recent work includes production AI SaaS with LLM pipelines and Stripe credits.",
  "project_order": ["adsignals", "nexusai", "missing"]
}
```"""
        copy = parse_tailored_copy(raw)
        self.assertEqual(copy.headline, "Full-Stack AI Engineer")
        self.assertEqual(copy.project_order, ("adsignals", "nexusai"))
        document = assemble(copy)
        self.assertEqual(document.projects[0].id, "adsignals")
        self.assertEqual(document.roles[0].company, "Exceed Your Limits Marketing")

    def test_parse_rejects_invented_short_profile(self) -> None:
        raw = '{"headline": "Engineer", "profile": "Too short.", "project_order": ["nexusai"]}'
        with self.assertRaises(ResumeError):
            parse_tailored_copy(raw)

    def test_filename_is_safe(self) -> None:
        self.assertEqual(
            resume_filename("Senior AI Engineer (Remote)", "abc"),
            "Ahmad_Haffoudhi_Senior_AI_Engineer_Remote.pdf",
        )


class ResumePdfTests(unittest.TestCase):
    def test_render_writes_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = render_resume(assemble(), Path(directory) / "cv.pdf")
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"%PDF"))
            self.assertGreater(len(data), 2000)


if __name__ == "__main__":
    unittest.main()
