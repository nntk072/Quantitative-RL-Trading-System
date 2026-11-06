"""Versioned candidate-proposal and conditional-outcome research records.

These records describe hypothetical fixed-entry proposals. They do not imply
policy actions or full closed-loop policy value. Unfilled and censored proposals
must never carry realized return labels.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from decisioning.trade_setup import TradeSetupCandidate

CANDIDATE_PROPOSAL_SCHEMA_VERSION = "candidate-proposal-v2"

EntryType = Literal["market", "limit"]
PolicyEligibility = Literal["eligible", "not_evaluated"]


def _timestamp(value: str, field: str) -> datetime:
    """Parse an ISO timestamp and require an explicit timezone.

    Args:
        value: Timestamp text in ISO 8601 format.
        field: Field name included in validation errors.

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


def _finite(value: float | None, field: str, *, required: bool = False) -> float | None:
    """Parse an optional finite number and enforce requiredness when set.

    Args:
        value: Numeric input, or ``None`` when the field is absent.
        field: Field name included in validation errors.
        required: Whether ``None`` is rejected.

    Returns:
        Finite floating-point value, or ``None`` for an allowed absent value.
    """
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field} must be finite")
    return numeric


@dataclass(frozen=True, slots=True)
class CandidateProposal:
    """One causal, bounded entry hypothesis for a stable semantic setup."""

    candidate_id: int
    idea_family: str
    source_timeframe: str
    direction: int
    source_event_id: str
    signal_confirmed_at: str
    quote_observed_at: str
    valid_from: str
    expires_at: str
    entry_type: EntryType
    proposed_entry_price: float
    permissible_stop_choices: tuple[tuple[str, float], ...]
    permissible_target_choices: tuple[tuple[str, float], ...]
    price_increment: float
    max_wait_seconds: float
    source_zone_low: float | None = None
    source_zone_high: float | None = None
    atr_scale: float | None = None
    spread_at_proposal: float | None = None
    source_geometry_id: str = "market_quote"
    current_session: str = "unknown"
    current_regime: str = "unknown"
    latency_estimate_ms: float | None = None
    estimated_round_trip_cost_points: float | None = None
    evidence_quality_flags: tuple[str, ...] = ()
    causal_feature_availability: tuple[str, ...] = ()
    policy_eligibility: PolicyEligibility = "not_evaluated"
    eligible_action_fill_time: str | None = None
    session_close_time: str | None = None
    proposal_id: str = ""
    schema_version: str = CANDIDATE_PROPOSAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate causal chronology and executable price geometry."""
        if self.schema_version != CANDIDATE_PROPOSAL_SCHEMA_VERSION:
            raise ValueError("unsupported candidate proposal schema version")
        if isinstance(self.candidate_id, bool) or int(self.candidate_id) <= 0:
            raise ValueError("candidate_id must identify a non-no-trade setup")
        if self.direction not in (-1, 1):
            raise ValueError("direction must be -1 or 1")
        if not self.idea_family.strip() or not self.source_timeframe.strip():
            raise ValueError("idea_family and source_timeframe are required")
        if not self.source_event_id.strip():
            raise ValueError("source_event_id is required for candidate identity")
        if not self.source_geometry_id.strip():
            raise ValueError("source_geometry_id is required for proposal identity")
        if self.entry_type not in {"market", "limit"}:
            raise ValueError("entry_type must be market or limit")

        confirmed = _timestamp(self.signal_confirmed_at, "signal_confirmed_at")
        quote_observed = _timestamp(self.quote_observed_at, "quote_observed_at")
        valid_from = _timestamp(self.valid_from, "valid_from")
        expires_at = _timestamp(self.expires_at, "expires_at")
        if valid_from < confirmed:
            raise ValueError("candidate cannot become valid before signal confirmation")
        if quote_observed > valid_from:
            raise ValueError("proposal quote cannot be observed after candidate validity begins")
        if expires_at <= valid_from:
            raise ValueError("expires_at must be after valid_from")

        entry = _finite(self.proposed_entry_price, "proposed_entry_price", required=True)
        increment = _finite(self.price_increment, "price_increment", required=True)
        wait = _finite(self.max_wait_seconds, "max_wait_seconds", required=True)
        assert entry is not None and increment is not None and wait is not None
        if increment <= 0.0 or wait <= 0.0:
            raise ValueError("price_increment and max_wait_seconds must be positive")
        if (expires_at - valid_from).total_seconds() > wait + 1e-9:
            raise ValueError("candidate expiry cannot exceed its declared maximum wait")

        def on_grid(price: float) -> bool:
            """Check whether a price is aligned to the declared increment.

            Args:
                price: Candidate price to check.

            Returns:
                Whether the price is an integer multiple of the increment.
            """
            return math.isclose(price / increment, round(price / increment), abs_tol=1e-8)

        if not on_grid(entry):
            raise ValueError("proposed entry must align to price_increment")

        stops = tuple((str(name), float(price)) for name, price in self.permissible_stop_choices)
        targets = tuple(
            (str(name), float(price)) for name, price in self.permissible_target_choices
        )
        if not stops or not targets:
            raise ValueError(
                "candidate proposal requires at least one legal stop and target choice"
            )
        if len({name for name, _ in stops}) != len(stops) or len(
            {name for name, _ in targets}
        ) != len(targets):
            raise ValueError("stop and target choice names must be unique")
        if any(not name.strip() or not math.isfinite(price) for name, price in stops + targets):
            raise ValueError("stop and target choices require named finite prices")
        if any(not on_grid(price) for _, price in stops + targets):
            raise ValueError("stop and target choices must align to price_increment")
        if any(self.direction * (entry - price) <= 0.0 for _, price in stops):
            raise ValueError("all stop choices must be on the loss side of entry")
        oriented_targets = tuple(self.direction * (price - entry) for _, price in targets)
        if any(value <= 0.0 for value in oriented_targets):
            raise ValueError("all target choices must be beyond entry")
        if any(right <= left for left, right in zip(oriented_targets, oriented_targets[1:])):
            raise ValueError("target choices must be ordered away from entry")

        low = _finite(self.source_zone_low, "source_zone_low")
        high = _finite(self.source_zone_high, "source_zone_high")
        if (low is None) != (high is None):
            raise ValueError("source zone requires both low and high")
        if low is not None and high is not None and low > high:
            raise ValueError("source zone bounds must be ordered")
        if self.entry_type == "limit" and low is not None and high is not None:
            if not low <= entry <= high:
                raise ValueError("limit entry must lie within its declared source zone")
        atr = _finite(self.atr_scale, "atr_scale")
        spread = _finite(self.spread_at_proposal, "spread_at_proposal")
        latency = _finite(self.latency_estimate_ms, "latency_estimate_ms")
        round_trip_cost = _finite(
            self.estimated_round_trip_cost_points, "estimated_round_trip_cost_points"
        )
        if atr is not None and atr <= 0.0:
            raise ValueError("atr_scale must be positive")
        if spread is not None and spread < 0.0:
            raise ValueError("spread_at_proposal cannot be negative")
        if latency is not None and latency < 0.0:
            raise ValueError("latency_estimate_ms cannot be negative")
        if round_trip_cost is not None and round_trip_cost < 0.0:
            raise ValueError("estimated_round_trip_cost_points cannot be negative")
        if not self.current_session.strip() or not self.current_regime.strip():
            raise ValueError("current_session and current_regime must be explicit or 'unknown'")
        if self.policy_eligibility not in {"eligible", "not_evaluated"}:
            raise ValueError("policy_eligibility must be eligible or not_evaluated")
        action_fill = (
            _timestamp(self.eligible_action_fill_time, "eligible_action_fill_time")
            if self.eligible_action_fill_time
            else None
        )
        session_close = (
            _timestamp(self.session_close_time, "session_close_time")
            if self.session_close_time
            else None
        )
        if self.policy_eligibility == "eligible":
            if action_fill is None or session_close is None:
                raise ValueError(
                    "eligible policy proposal requires action fill and session close times"
                )
            if action_fill < valid_from or session_close <= action_fill:
                raise ValueError("eligible action chronology is invalid")
        elif action_fill is not None or session_close is not None:
            raise ValueError("unclassified policy eligibility cannot carry eligibility times")

        object.__setattr__(self, "candidate_id", int(self.candidate_id))
        object.__setattr__(self, "direction", int(self.direction))
        object.__setattr__(self, "permissible_stop_choices", stops)
        object.__setattr__(self, "permissible_target_choices", targets)
        object.__setattr__(self, "evidence_quality_flags", tuple(self.evidence_quality_flags))
        object.__setattr__(
            self, "causal_feature_availability", tuple(self.causal_feature_availability)
        )
        if not self.proposal_id:
            payload = asdict(self)
            payload.pop("proposal_id")
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            object.__setattr__(self, "proposal_id", f"cp2-{digest[:24]}")

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible, versioned record.

        Returns:
            Candidate fields as a mapping suitable for JSON serialization.
        """
        return asdict(self)


def build_decision_proposals(
    candidate: TradeSetupCandidate,
    *,
    source_event_id: str,
    signal_confirmed_at: str,
    quote_observed_at: str,
    valid_from: str,
    expires_at: str,
    bid: float,
    ask: float,
    price_increment: float,
    max_wait_seconds: float,
    geometry_for_entry: Callable[
        [float], tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]] | None
    ],
    source_zone: tuple[float, float] | None = None,
    source_geometry_id: str = "market_quote",
    include_market: bool = True,
    atr_scale: float | None = None,
    current_session: str = "unknown",
    current_regime: str = "unknown",
    latency_estimate_ms: float | None = None,
    estimated_round_trip_cost_points: float | None = None,
    evidence_quality_flags: tuple[str, ...] = (),
    causal_feature_availability: tuple[str, ...] = (),
    policy_eligibility: PolicyEligibility = "not_evaluated",
    eligible_action_fill_time: str | None = None,
    session_close_time: str | None = None,
) -> tuple[CandidateProposal, ...]:
    """Build a bounded market and optional zone-midpoint proposal set.

    Stop and target geometry is rebuilt independently for each proposed entry
    by ``geometry_for_entry``. The caller should use the production structural
    order builder and return ``None`` when no legal geometry exists.

    Args:
        candidate: Eligible setup selected for proposal generation.
        source_event_id: Stable identity of the source setup event.
        signal_confirmed_at: Time when the setup became observable.
        quote_observed_at: Time when the proposal quote was observed.
        valid_from: Earliest time at which the proposal can be acted on.
        expires_at: Latest time at which the proposal remains valid.
        bid: Bid quote used for market entry and spread calculations.
        ask: Ask quote used for market entry and spread calculations.
        price_increment: Minimum valid price step for generated order prices.
        max_wait_seconds: Maximum allowed time from validity to expiry.
        geometry_for_entry: Builder returning permissible stops and targets for a price.
        source_zone: Optional low and high boundaries for a zone-midpoint limit.
        source_geometry_id: Stable identity for the geometry source.
        include_market: Whether to include a quote-side market proposal.
        atr_scale: Optional ATR scale recorded with the proposal.
        current_session: Session label at proposal time.
        current_regime: Regime label at proposal time.
        latency_estimate_ms: Optional execution-latency estimate.
        estimated_round_trip_cost_points: Optional estimated round-trip cost.
        evidence_quality_flags: Quality limitations attached to the proposal.
        causal_feature_availability: Feature availability evidence at decision time.
        policy_eligibility: Whether policy eligibility was evaluated for the setup.
        eligible_action_fill_time: Fill time for an eligible action, when known.
        session_close_time: Session boundary that can invalidate the proposal.

    Returns:
        Market and zone-limit proposals with independently built order geometry.
    """
    if candidate.is_no_trade:
        raise ValueError("NO_TRADE does not produce an executable candidate proposal")
    if candidate.idea is None or candidate.setup_timeframe is None:
        raise ValueError("executable candidate requires idea and source timeframe")
    bid_value = _finite(bid, "bid", required=True)
    ask_value = _finite(ask, "ask", required=True)
    increment = _finite(price_increment, "price_increment", required=True)
    assert bid_value is not None and ask_value is not None and increment is not None
    if bid_value <= 0.0 or ask_value < bid_value:
        raise ValueError("proposal quote must be positive and non-crossed")
    if increment <= 0.0:
        raise ValueError("price_increment must be positive")
    direction = int(candidate.direction)
    if direction not in (-1, 1):
        raise ValueError("executable candidate direction must be -1 or 1")
    market_entry = ask_value if direction > 0 else bid_value
    quote_spread = ask_value - bid_value
    entries: list[tuple[EntryType, float]] = [("market", market_entry)] if include_market else []
    if source_zone is not None:
        low = _finite(source_zone[0], "source_zone_low", required=True)
        high = _finite(source_zone[1], "source_zone_high", required=True)
        assert low is not None and high is not None
        if low > high:
            raise ValueError("source zone bounds must be ordered")
        zone_midpoint = (low + high) / 2.0 / increment
        limit_entry = round(zone_midpoint) * increment
        # A limit that is already marketable at proposal time is an immediate
        # order and cannot be treated as a pending-entry hypothesis.
        pending_side = limit_entry < ask_value if direction > 0 else limit_entry > bid_value
        if low <= limit_entry <= high and pending_side:
            entries.append(("limit", float(limit_entry)))

    proposals: list[CandidateProposal] = []
    for entry_type, entry_price in entries:
        geometry = geometry_for_entry(entry_price)
        if geometry is None:
            continue
        stop_choices, target_choices = geometry
        proposals.append(
            CandidateProposal(
                candidate_id=candidate.candidate_id,
                idea_family=candidate.idea,
                source_timeframe=candidate.setup_timeframe,
                direction=direction,
                source_event_id=source_event_id,
                signal_confirmed_at=signal_confirmed_at,
                quote_observed_at=quote_observed_at,
                valid_from=valid_from,
                expires_at=expires_at,
                entry_type=entry_type,
                proposed_entry_price=float(entry_price),
                permissible_stop_choices=tuple(stop_choices),
                permissible_target_choices=tuple(target_choices),
                price_increment=increment,
                max_wait_seconds=max_wait_seconds,
                source_zone_low=None if source_zone is None else source_zone[0],
                source_zone_high=None if source_zone is None else source_zone[1],
                atr_scale=atr_scale,
                spread_at_proposal=quote_spread,
                source_geometry_id=source_geometry_id,
                current_session=current_session,
                current_regime=current_regime,
                latency_estimate_ms=latency_estimate_ms,
                estimated_round_trip_cost_points=estimated_round_trip_cost_points,
                evidence_quality_flags=evidence_quality_flags,
                causal_feature_availability=causal_feature_availability,
                policy_eligibility=policy_eligibility,
                eligible_action_fill_time=eligible_action_fill_time,
                session_close_time=session_close_time,
            )
        )
    return tuple(proposals)


__all__ = [
    "CANDIDATE_PROPOSAL_SCHEMA_VERSION",
    "CandidateProposal",
    "build_decision_proposals",
]
