"""Parser tests for Claude's structured match response."""

from __future__ import annotations

import unittest

from src.config import DEVELOPER_PROFILE
from src.evaluator import EvaluationError, build_prompt, parse_evaluation
from src.fetchers import JobListing


class ParseEvaluationTests(unittest.TestCase):
    def test_labeled_response(self) -> None:
        raw = (
            "MATCH_SCORE: 9\n"
            "IS_STARTUP: True\n"
            "SUMMARY: The role is a remote senior backend seat at a YC startup using Go. "
            "That lines up with the candidate's stack and startup preference.\n"
        )
        result = parse_evaluation(raw)
        self.assertEqual(result.match_score, 9)
        self.assertTrue(result.is_startup)
        self.assertIn("YC startup", result.summary)

    def test_json_response(self) -> None:
        raw = """```json
{"MATCH_SCORE": "8", "IS_STARTUP": false, "SUMMARY": "The team is a large enterprise and the stack is mostly Java. The seniority matches, but the company stage does not."}
```"""
        result = parse_evaluation(raw)
        self.assertEqual(result.match_score, 8)
        self.assertFalse(result.is_startup)

    def test_preamble_still_parses(self) -> None:
        raw = (
            "Here is the evaluation.\n"
            "MATCH_SCORE: 4\n"
            "IS_STARTUP: Yes\n"
            "SUMMARY: This is an internship rather than a senior engineering role. "
            "The candidate should pass on it.\n"
        )
        result = parse_evaluation(raw)
        self.assertEqual(result.match_score, 4)
        self.assertTrue(result.is_startup)

    def test_score_out_of_range(self) -> None:
        raw = (
            "MATCH_SCORE: 12\n"
            "IS_STARTUP: True\n"
            "SUMMARY: This summary is long enough to pass the length check easily.\n"
        )
        with self.assertRaises(EvaluationError):
            parse_evaluation(raw)

    def test_summary_may_contain_braces(self) -> None:
        raw = (
            "MATCH_SCORE: 8\n"
            "IS_STARTUP: True\n"
            'SUMMARY: The post lists a Go service and a stack note {"db": "postgres"} in passing. '
            "It still reads as a senior remote startup role.\n"
        )
        result = parse_evaluation(raw)
        self.assertEqual(result.match_score, 8)
        self.assertIn("postgres", result.summary)

    def test_missing_summary(self) -> None:
        with self.assertRaises(EvaluationError):
            parse_evaluation("MATCH_SCORE: 7\nIS_STARTUP: False\n")

    def test_prompt_includes_profile_and_fields(self) -> None:
        job = JobListing(
            id="abc",
            title="Backend Engineer",
            link="https://example.com/jobs/1",
            description="Build APIs in Go and TypeScript.",
            source="https://hnrss.org/jobs",
        )
        prompt = build_prompt(job, DEVELOPER_PROFILE)
        self.assertIn("Node.js", prompt)
        self.assertIn("NestJS", prompt)
        self.assertIn("Backend Engineer", prompt)
        self.assertIn("MATCH_SCORE:", prompt)
        self.assertIn("IS_STARTUP:", prompt)
        self.assertIn("SUMMARY:", prompt)


if __name__ == "__main__":
    unittest.main()
