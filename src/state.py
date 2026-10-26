"""Remember listings that have already been scored."""

from __future__ import annotations

import json
from pathlib import Path


class StateError(RuntimeError):
    """Raised when the seen-jobs file cannot be read or written."""


class SeenJobStore:
    """JSON set of listing ids that have already been handled."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._ids: set[str] = set()

    def load(self) -> None:
        if not self.path.exists():
            self._ids = set()
            return
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise StateError(
                f"Could not read {self.path}. Fix the file or remove it to start fresh."
            ) from exc
        ids = data.get("ids") if isinstance(data, dict) else None
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise StateError(f"Seen jobs file is malformed: {self.path}")
        self._ids = set(ids)

    def contains(self, job_id: str) -> bool:
        return job_id in self._ids

    def add(self, job_id: str) -> None:
        self._ids.add(job_id)

    def save(self) -> None:
        payload = json.dumps({"ids": sorted(self._ids)}, indent=2) + "\n"
        temporary = self.path.parent / f"{self.path.name}.tmp"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(self.path)
        except OSError as exc:
            raise StateError(f"Could not save seen jobs to {self.path}.") from exc
