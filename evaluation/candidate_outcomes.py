"""Versioned outcomes for conditional candidate-proposal replay."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

CONDITIONAL_OUTCOME_SCHEMA_VERSION = "candidate-conditional-outcome-v2"

OutcomeStatus = Literal[
    "filled_resolved",
    "unfilled_expired",
    "censored_order_horizon",
    "censored_exit_horizon",
    "unresolved_data",
]


def _timestamp(value: str, field: str) -> datetime:
    """Parse a non-empty ISO timestamp with an explicit timezone.

    Args:
        value: ISO 8601 timestamp text.
        field: Field name used in validation errors.

    Returns:
        Parsed timezone-aware timestamp.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _finite(value: float | None, field: str) -> float | None:
    """Return a finite optional number or reject invalid evidence.

    Args:
        value: Optional number recorded in the candidate outcome.
        field: Field name used in validation errors.

    Returns:
        Finite float, or ``None`` when the value is absent.
    """
    if value is None:
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field} must be finite")
    return numeric


@dataclass(frozen=True, slots=True)
class CandidateConditionalOutcome:
    """One fixed-proposal, fixed-bracket outcome with explicit missingness."""

    proposal_id: str
    status: OutcomeStatus
    evaluated_until: str
    order_expires_at: str
    stop_choice: str
    target_choice: str
    fill_time: str | None = None
    fill_price: float | None = None
    exit_time: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    net_r: float | None = None
    unresolved_reason: str | None = None
    outcome_id: str = ""
    schema_version: str = CONDITIONAL_OUTCOME_SCHEMA_VERSION
    estimand: str = "conditional_fixed_entry"

    def __post_init__(self) -> None:
        """Validate outcome identity, chronology, and status-specific fields."""
        if self.schema_version != CONDITIONAL_OUTCOME_SCHEMA_VERSION:
            raise ValueError("unsupported conditional outcome schema version")
        if not self.proposal_id.strip():
            raise ValueError("proposal_id is required")
        if not self.stop_choice.strip() or not self.target_choice.strip():
            raise ValueError("outcome requires explicit stop and target choices")
        if self.estimand != "conditional_fixed_entry":
            raise ValueError("outcome must declare the conditional_fixed_entry estimand")
        if self.status not in {
            "filled_resolved",
            "unfilled_expired",
            "censored_order_horizon",
            "censored_exit_horizon",
            "unresolved_data",
        }:
            raise ValueError("unsupported conditional outcome status")

        evaluated = _timestamp(self.evaluated_until, "evaluated_until")
        expires = _timestamp(self.order_expires_at, "order_expires_at")
        fill_time = _timestamp(self.fill_time, "fill_time") if self.fill_time else None
        exit_time = _timestamp(self.exit_time, "exit_time") if self.exit_time else None
        fill_price = _finite(self.fill_price, "fill_price")
        exit_price = _finite(self.exit_price, "exit_price")
        net_r = _finite(self.net_r, "net_r")

        if self.status == "filled_resolved":
            if any(
                value is None for value in (fill_time, fill_price, exit_time, exit_price, net_r)
            ):
                raise ValueError("resolved outcome requires fill, exit, and net R")
            if not self.exit_reason or self.unresolved_reason:
                raise ValueError("resolved outcome requires only an exit reason")
            assert fill_time is not None and exit_time is not None
            if fill_time > expires or fill_time > evaluated:
                raise ValueError("resolved fill chronology is invalid")
            if exit_time < fill_time or exit_time > evaluated:
                raise ValueError("resolved exit chronology is invalid")
        elif self.status == "censored_exit_horizon":
            if (
                fill_time is None
                or fill_price is None
                or any(
                    value is not None for value in (exit_time, exit_price, net_r, self.exit_reason)
                )
            ):
                raise ValueError("censored exit requires a fill and no realized exit label")
            if self.unresolved_reason:
                raise ValueError("censored exit cannot carry an unresolved-data reason")
            if fill_time > expires or fill_time > evaluated:
                raise ValueError("censored fill chronology is invalid")
        elif self.status == "unresolved_data":
            if not self.unresolved_reason or any(
                value is not None for value in (exit_time, exit_price, net_r, self.exit_reason)
            ):
                raise ValueError("unresolved outcome requires a reason and cannot carry returns")
            if (fill_time is None) != (fill_price is None):
                raise ValueError("known unresolved fill requires both time and price")
            if fill_time is not None and (fill_time > expires or fill_time > evaluated):
                raise ValueError("unresolved fill chronology is invalid")
        else:
            if any(
                value is not None
                for value in (
                    fill_time,
                    fill_price,
                    exit_time,
                    exit_price,
                    net_r,
                    self.exit_reason,
                    self.unresolved_reason,
                )
            ):
                raise ValueError("unfilled and order-censored outcomes cannot carry execution")
            if self.status == "unfilled_expired" and evaluated < expires:
                raise ValueError("unfilled outcome cannot be final before expiry")
            if self.status == "censored_order_horizon" and evaluated >= expires:
                raise ValueError("order censoring must end before expiry")

        if not self.outcome_id:
            identity = {
                "proposal_id": self.proposal_id,
                "stop_choice": self.stop_choice,
                "target_choice": self.target_choice,
                "schema_version": self.schema_version,
            }
            digest = hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            object.__setattr__(self, "outcome_id", f"co2-{digest[:24]}")

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible, versioned outcome record.

        Returns:
            Outcome fields as a mapping suitable for JSON serialization.
        """
        return asdict(self)


__all__ = [
    "CONDITIONAL_OUTCOME_SCHEMA_VERSION",
    "CandidateConditionalOutcome",
    "OutcomeStatus",
]
