"""Tests for feed normalization."""

from __future__ import annotations

import unittest

from src.fetchers import JobListing, dedupe_jobs, html_to_text, listing_from_entry


class HtmlToTextTests(unittest.TestCase):
    def test_strips_tags_and_skips_script(self) -> None:
        raw = "<p>Build <b>Go</b> services.</p><script>alert(1)</script>"
        text = html_to_text(raw)
        self.assertIn("Build Go services.", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("<b>", text)

    def test_decodes_entities(self) -> None:
        self.assertIn("Node & Python", html_to_text("Node &amp; Python"))


class ListingTests(unittest.TestCase):
    def test_listing_from_entry(self) -> None:
        entry = {
            "title": "Senior Backend Engineer",
            "link": "https://example.com/jobs/1",
            "id": "job-1",
            "summary": "<p>Build <b>Go</b> services.</p><script>alert(1)</script>",
        }
        job = listing_from_entry(entry, source="https://hnrss.org/jobs")
        self.assertIsNotNone(job)
        assert job is not None
        self.assertEqual(job.title, "Senior Backend Engineer")
        self.assertEqual(job.link, "https://example.com/jobs/1")
        self.assertIn("Go", job.description)
        self.assertNotIn("alert", job.description)
        again = listing_from_entry(entry, source="other")
        self.assertIsNotNone(again)
        assert again is not None
        self.assertEqual(job.id, again.id)

    def test_skips_empty_entries(self) -> None:
        self.assertIsNone(listing_from_entry({"title": " ", "summary": ""}, source="feed"))

    def test_dedupe_keeps_first_id(self) -> None:
        first = JobListing("same", "First", "https://example.com/a", "One role description.", "feed")
        second = JobListing("same", "Second", "https://example.com/b", "Another role description.", "feed")
        third = JobListing("other", "Third", "https://example.com/c", "Third role description.", "feed")
        unique = dedupe_jobs([first, second, third])
        self.assertEqual([job.title for job in unique], ["First", "Third"])


if __name__ == "__main__":
    unittest.main()
