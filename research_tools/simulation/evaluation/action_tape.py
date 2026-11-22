"""Validated immutable action tapes for paired simulator replay."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "qrl.task13.action_tape.v1"


def _parse_utc(value: Any) -> datetime:
    """Parse a timezone-aware ISO timestamp and normalize it to UTC."""
    if not isinstance(value, str):
        raise ValueError("action decision_time_utc must be an ISO timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid action decision_time_utc: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("action decision_time_utc must include a UTC timezone")
    return parsed.astimezone(UTC)


def _validate_action(value: Any, *, index: int) -> int | tuple[float, ...]:
    """Validate an integer action or finite numeric vector action."""
    if isinstance(value, bool):
        raise ValueError(f"action {index} must not be boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, list) and value:
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
            raise ValueError(f"action {index} vector must contain only numbers")
        vector = [float(item) for item in value]
        if not all(math.isfinite(item) for item in vector):
            raise ValueError(f"action {index} vector must be finite")
        return tuple(vector)
    raise ValueError(f"action {index} must be an integer or non-empty numeric vector")


@dataclass(frozen=True)
class ActionTape:
    """A source file's ordered actions with a strict decision-time cursor."""

    actions: tuple[tuple[datetime, int | tuple[float, ...]], ...]
    sha256: str
    _cursor: list[int] = field(default_factory=lambda: [0], init=False, repr=False, compare=False)

    @classmethod
    def load(cls, path: Path) -> ActionTape:
        """Load and validate a versioned JSON action tape, retaining its file hash."""
        raw = path.read_bytes()
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"invalid action tape JSON at {path}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"action tape schema_version must be {SCHEMA_VERSION!r}")
        if set(payload) != {"schema_version", "actions"}:
            raise ValueError("action tape must contain only schema_version and actions")
        records = payload.get("actions")
        if not isinstance(records, list) or not records:
            raise ValueError("action tape actions must be a non-empty list")

        actions: list[tuple[datetime, int | tuple[float, ...]]] = []
        previous: datetime | None = None
        for index, record in enumerate(records):
            if not isinstance(record, dict) or set(record) != {"decision_time_utc", "action"}:
                raise ValueError(f"action {index} must contain decision_time_utc and action only")
            decision_time = _parse_utc(record["decision_time_utc"])
            if previous is not None and decision_time <= previous:
                raise ValueError(
                    "action decision timestamps must be strictly increasing and unique"
                )
            actions.append((decision_time, _validate_action(record["action"], index=index)))
            previous = decision_time
        return cls(tuple(actions), hashlib.sha256(raw).hexdigest())

    def next_action(self, decision_time_utc: str | datetime) -> int | list[float]:
        """Return the next action only when its timestamp matches exactly."""
        cursor = self._cursor[0]
        if cursor >= len(self.actions):
            raise ValueError("action tape is exhausted")
        requested = (
            _parse_utc(decision_time_utc)
            if isinstance(decision_time_utc, str)
            else decision_time_utc
        )
        if requested.tzinfo is None or requested.utcoffset() != UTC.utcoffset(requested):
            raise ValueError("decision timestamp must be timezone-aware UTC")
        expected_time, action = self.actions[cursor]
        if requested.astimezone(UTC) != expected_time:
            raise ValueError(
                f"action tape timestamp mismatch at index {cursor}: "
                f"expected {expected_time.isoformat()}, got {requested.astimezone(UTC).isoformat()}"
            )
        self._cursor[0] += 1
        return list(action) if isinstance(action, tuple) else action

    def assert_fully_consumed(self) -> None:
        """Require every frozen action to have been consumed exactly once."""
        remaining = len(self.actions) - self._cursor[0]
        if remaining:
            raise ValueError(f"action tape has {remaining} unconsumed action(s)")
