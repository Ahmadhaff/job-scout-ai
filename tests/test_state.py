"""Tests for the seen-listing store."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.state import SeenJobStore, StateError


class SeenJobStoreTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen_jobs.json"
            store = SeenJobStore(path)
            store.load()
            self.assertFalse(store.contains("job-1"))
            store.add("job-1")
            store.save()

            restored = SeenJobStore(path)
            restored.load()
            self.assertTrue(restored.contains("job-1"))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["ids"], ["job-1"])

    def test_malformed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen_jobs.json"
            path.write_text("{", encoding="utf-8")
            store = SeenJobStore(path)
            with self.assertRaises(StateError):
                store.load()


if __name__ == "__main__":
    unittest.main()
