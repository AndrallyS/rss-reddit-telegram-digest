"""Simple source health tracking."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from app.models import SourceHealthRecord


class HealthTracker:
    def __init__(self, failure_threshold: int = 3) -> None:
        self.failure_threshold = failure_threshold
        self._records: dict[str, SourceHealthRecord] = {}

    def _get(self, source_name: str) -> SourceHealthRecord:
        if source_name not in self._records:
            self._records[source_name] = SourceHealthRecord(source_name=source_name)
        return self._records[source_name]

    def mark_disabled(self, source_name: str, reason: str) -> None:
        record = self._get(source_name)
        record.status = "disabled"
        record.last_error = reason

    def record_success(self, source_name: str) -> None:
        record = self._get(source_name)
        record.status = "healthy"
        record.consecutive_failures = 0
        record.last_error = None
        record.last_success_at = datetime.now(tz=UTC).isoformat()

    def record_failure(self, source_name: str, error: str) -> None:
        record = self._get(source_name)
        record.consecutive_failures += 1
        record.last_error = error
        record.status = (
            "degraded"
            if record.consecutive_failures < self.failure_threshold
            else "unavailable"
        )

    def as_dict(self) -> dict[str, dict[str, object]]:
        return {name: asdict(record) for name, record in self._records.items()}

