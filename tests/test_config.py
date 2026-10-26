"""Tests for profile text and environment parsing."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.config import DEVELOPER_PROFILE, REQUIRED_ENV, ConfigError, Settings, job_targets_stack


class ProfileTests(unittest.TestCase):
    def test_profile_mentions_target_stack(self) -> None:
        text = DEVELOPER_PROFILE.as_prompt_block()
        for skill in ("React", "Next.js", "Node.js", "NestJS", "PostgreSQL", "AI"):
            self.assertIn(skill, text)
        self.assertIn("Full-Stack & AI Engineer", text)
        self.assertIn("Remote", text)


class SettingsTests(unittest.TestCase):
    def test_missing_credentials(self) -> None:
        cleared = {name: "" for name in REQUIRED_ENV}
        with patch.dict(os.environ, cleared, clear=True):
            with self.assertRaises(ConfigError):
                Settings.from_env()

    def test_dry_run_allows_missing_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env(require_credentials=False)
        self.assertEqual(settings.model, "claude-sonnet-5-5")
        self.assertEqual(settings.match_threshold, 8)
        self.assertGreaterEqual(len(settings.feeds), 1)

    def test_target_stack_gate(self) -> None:
        self.assertTrue(job_targets_stack("Senior React Engineer", "Next.js and PostgreSQL"))
        self.assertTrue(job_targets_stack("Backend", "NestJS APIs on Node.js"))
        self.assertTrue(job_targets_stack("AI Engineer", "LLM product work"))
        self.assertFalse(job_targets_stack("Consultant", "comete.ai aide les industriels"))
        self.assertFalse(job_targets_stack("Account Executive", "Sell our CRM to retailers"))
        self.assertFalse(job_targets_stack("iOS Engineer", "Ship the Swift app next week"))

    def test_rejects_threshold_out_of_range(self) -> None:
        with patch.dict(os.environ, {"MATCH_THRESHOLD": "11"}, clear=True):
            with self.assertRaises(ConfigError):
                Settings.from_env(require_credentials=False)


if __name__ == "__main__":
    unittest.main()
