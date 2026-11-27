"""Promotion rules for optional performance candidates (PERFORMANCE-POLICY).

The checker is pure decision logic. It takes a trial summary supplied by the
caller, compares it with the promotion matrix and returns ``promote``,
``reject`` or ``insufficient_evidence``. It reads no file except the summary
the caller loads, writes nothing, and never changes a default implementation.
A ``promote`` outcome only makes a candidate eligible for a separately
reviewed default switch. Any other outcome leaves the baseline in place.

The matrix is defined once here as typed constants and mirrored in
``planning/native_modernization/performance_policy/promotion_matrix.md``. A test
keeps the markdown's JSON block equal to ``matrix_to_jsonable(DEFAULT_MATRIX)``.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, cast

GateStatus = Literal["pass", "fail", "not_run"]
Outcome = Literal["promote", "reject", "insufficient_evidence"]
Metric = Literal["throughput", "wall_seconds", "resource_cost", "peak_memory_bytes"]
MeasurementKind = Literal["primary", "guard"]
ThresholdSource = Literal["planner", "lead_default"]

_GATE_STATUSES: frozenset[str] = frozenset({"pass", "fail", "not_run"})
_METRICS: frozenset[str] = frozenset(
    {"throughput", "wall_seconds", "resource_cost", "peak_memory_bytes"}
)
_KINDS: frozenset[str] = frozenset({"primary", "guard"})
_HIGHER_IS_BETTER: frozenset[str] = frozenset({"throughput"})
_SPEED_METRICS: frozenset[str] = frozenset({"throughput", "wall_seconds"})
_SCIENTIFIC_GATE = "SCIENTIFIC_COMPARISON"


class TrialSummaryError(ValueError):
    """Raised for a malformed trial summary. Malformed input is never treated as evidence."""


@dataclass(frozen=True)
class Threshold:
    """A numeric promotion rule with its provenance and the reason for its value."""

    value: float
    source: ThresholdSource
    reason: str


@dataclass(frozen=True)
class GateDefinition:
    """A correctness gate that a trial must report as pass before any speed is considered."""

    gate_id: str
    definition: str


@dataclass(frozen=True)
class CandidateClass:
    """Promotion criteria for one class of optional candidate.

    A criterion is applicable when its threshold is not None. Speed thresholds
    apply to primary throughput or wall-clock measurements. The Amdahl gate
    applies only to stage-level speed, never to integrated wall-clock speed.
    """

    class_id: str
    plan_packages: tuple[str, ...]
    required_gates: tuple[str, ...]
    speedup: Threshold | None
    stretch_speedup: Threshold | None
    memory_reduction: Threshold | None
    resource_cost_reduction: Threshold | None
    reliability_gain: Threshold | None
    amdahl_min_end_to_end: Threshold | None


@dataclass(frozen=True)
class PromotionMatrix:
    """The complete frozen promotion matrix."""

    min_repeats: Threshold
    max_relative_spread: Threshold
    min_reliability_attempts: Threshold
    max_regression: Threshold
    gates: Mapping[str, GateDefinition]
    classes: Mapping[str, CandidateClass]
    scientific_gate: str = _SCIENTIFIC_GATE

    def class_for(self, class_id: str) -> CandidateClass:
        """Return the class or raise ``TrialSummaryError`` for an unknown class."""
        try:
            return self.classes[class_id]
        except KeyError as exc:
            raise TrialSummaryError(f"unknown candidate class: {class_id}") from exc


@dataclass(frozen=True)
class Measurement:
    """Repeated timed or sized measurements of one workload for baseline and candidate.

    ``primary`` measurements carry the promotion criteria. ``guard``
    measurements are comparable required workloads checked only for regression.
    ``stage_fraction`` is the baseline share of end-to-end time spent in the
    affected stage, required for an Amdahl projection of primary speed.
    """

    workload_id: str
    metric: Metric
    kind: MeasurementKind
    baseline: tuple[float, ...]
    candidate: tuple[float, ...]
    stage_fraction: float | None = None


@dataclass(frozen=True)
class ReliabilityCounts:
    """Success counts over independent attempts for each arm."""

    baseline_successes: int
    baseline_attempts: int
    candidate_successes: int
    candidate_attempts: int


@dataclass(frozen=True)
class TrialSummary:
    """Everything the checker needs to decide one candidate trial."""

    trial_id: str
    candidate_class: str
    baseline_id: str
    candidate_id: str
    correctness_gates: Mapping[str, GateStatus]
    semantics_changed: bool
    measurements: tuple[Measurement, ...]
    reliability: ReliabilityCounts | None = None


@dataclass(frozen=True)
class TrialDecision:
    """The checker's result. ``default_implementation`` is always the baseline."""

    trial_id: str
    candidate_class: str
    outcome: Outcome
    reasons: tuple[str, ...]
    passed_criteria: tuple[str, ...] = ()
    failed_criteria: tuple[str, ...] = ()
    stretch_met: bool = False
    default_implementation: str = ""
    switch_eligible: bool = False
    notes: tuple[str, ...] = field(default=())


# ---------------------------------------------------------------------------
# Initial matrix. Every value is recorded with its source and reason. The
# planner values come from ARCHITECTURE_MODERNIZATION_PLAN.md, PERFORMANCE-POLICY.
# The lead_default values are not measured and must be recalibrated before the
# first candidate decision.
# ---------------------------------------------------------------------------

_MIN_REPEATS = Threshold(
    value=5.0,
    source="planner",
    reason=(
        "PERFORMANCE-BASELINE asks for at least 5 independent timed repetitions when "
        "feasible. Fewer repeats cannot support a median or a dispersion bound."
    ),
)
_MAX_SPREAD = Threshold(
    value=0.15,
    source="lead_default",
    reason=(
        "No measured noise floor exists because PERFORMANCE-BASELINE is blocked. "
        "Relative spread (max minus min, over the median) of 0.15 is a placeholder. "
        "Recalibrate from the first baseline repeats and record an amendment."
    ),
)
_MIN_RELIABILITY_ATTEMPTS = Threshold(
    value=20.0,
    source="lead_default",
    reason=(
        "No measured failure rate exists. 20 attempts per arm is a placeholder that "
        "prevents a success-rate gap from being decided on a handful of runs."
    ),
)
_MAX_REGRESSION = Threshold(
    value=0.05,
    source="planner",
    reason="Plan PERFORMANCE-POLICY: no unexplained regression above 5% on comparable required workloads.",
)
_STAGE_SPEEDUP = Threshold(
    value=1.5,
    source="planner",
    reason="Plan PERFORMANCE-POLICY: target of at least 1.5x sustained improvement in the affected stage.",
)
_STRETCH_SPEEDUP = Threshold(
    value=3.0,
    source="planner",
    reason=(
        "Plan PERFORMANCE-POLICY: native batch environment stretch target of at least 3x step "
        "throughput. Reported as stretch_met only. It does not gate promotion."
    ),
)
_MEMORY_REDUCTION = Threshold(
    value=0.25,
    source="planner",
    reason="Plan PERFORMANCE-POLICY: at least 25% less peak memory is an alternative criterion.",
)
_RELIABILITY_GAIN = Threshold(
    value=0.05,
    source="lead_default",
    reason=(
        "The plan says only 'meaningful measured reliability gain' with no number. A "
        "5-point success-rate gain is a placeholder. No failure-rate baseline exists yet."
    ),
)
_INTEGRATED_SPEEDUP = Threshold(
    value=1.3,
    source="planner",
    reason="Plan PERFORMANCE-POLICY: integrated target of at least 1.3x wall-clock throughput.",
)
_RESOURCE_COST_REDUCTION = Threshold(
    value=0.25,
    source="planner",
    reason="Plan PERFORMANCE-POLICY: integrated alternative of at least 25% lower resource cost.",
)
_AMDAHL_MIN = Threshold(
    value=1.05,
    source="lead_default",
    reason=(
        "The plan says to discard complex changes with negligible end-to-end benefit but gives no "
        "number. 1.05 uses the same 5% scale as the regression limit. The projection uses "
        "Amdahl's law with the measured baseline stage fraction."
    ),
)

_GATE_DEFINITIONS: tuple[GateDefinition, ...] = (
    GateDefinition(
        "ORACLE_EXACT",
        "Semantic-oracle parity. Integers, enums, timestamps, order, position and risk decisions are "
        "exact. Numeric fields match within a tolerance frozen per field before comparison.",
    ),
    GateDefinition(
        "TAPE_REPLAY",
        "A fixed action tape reproduces the full event trace, including ordering keys.",
    ),
    GateDefinition(
        "BATCH_SINGLE",
        "Batch and single outputs are equal under the same tape and seeds, and resets are "
        "independent across environments.",
    ),
    GateDefinition(
        "CAUSAL_PREFIX",
        "Future-append and prefix invariance hold. Features at time t do not change when data "
        "after t is appended or perturbed. No incomplete higher-timeframe value is used.",
    ),
    GateDefinition(
        "FIT_SCOPE",
        "A held-out perturbation leaves train-fitted state and normalization unchanged.",
    ),
    GateDefinition(
        "ROUNDTRIP_RECONCILE",
        "Source and converted data reconcile row by row on counts, values, timestamps and "
        "identities. Every dropped or corrected record is explained.",
    ),
    GateDefinition(
        "LEARNER_FIXED_BATCH",
        "Loss, gradient, mask, log-probability and value parity on a frozen batch fall within the "
        "declared tolerance. No NaN or Inf appears.",
    ),
    GateDefinition(
        "CHECKPOINT_COMPAT",
        "A checkpoint round trip succeeds and retained checkpoints still infer. Incompatible "
        "formats are rejected, not loaded.",
    ),
    GateDefinition(
        "RESOURCE_BOUNDS",
        "Workers and threads stay bounded. Admission refusal fixtures pass. No per-task scheduler "
        "fan-out occurs.",
    ),
    GateDefinition(
        "DETERMINISM",
        "Repeated runs with the same seeds and inputs give identical outputs, or outputs within a "
        "declared numerical tolerance.",
    ),
    GateDefinition(
        "RISK_PRECISION",
        "Hard-risk, account and ledger arithmetic is not reduced in precision, and fast-math is "
        "not enabled there. Risk decisions are exact.",
    ),
    GateDefinition(
        "TRAIN_ONLY_WORKLOAD",
        "The benchmark workload uses train-only data. No locked or exposed 2026 reporting "
        "interval is read.",
    ),
    GateDefinition(
        _SCIENTIFIC_GATE,
        "Required only when semantics_changed is true. An independent scientific comparison on "
        "the registered design passed.",
    ),
)

DEFAULT_MATRIX = PromotionMatrix(
    min_repeats=_MIN_REPEATS,
    max_relative_spread=_MAX_SPREAD,
    min_reliability_attempts=_MIN_RELIABILITY_ATTEMPTS,
    max_regression=_MAX_REGRESSION,
    gates={gate.gate_id: gate for gate in _GATE_DEFINITIONS},
    classes={
        "feature_kernel": CandidateClass(
            class_id="feature_kernel",
            plan_packages=("FEATURE-KERNELS",),
            required_gates=("CAUSAL_PREFIX", "FIT_SCOPE", "ORACLE_EXACT", "DETERMINISM"),
            speedup=_STAGE_SPEEDUP,
            stretch_speedup=None,
            memory_reduction=_MEMORY_REDUCTION,
            resource_cost_reduction=None,
            reliability_gain=_RELIABILITY_GAIN,
            amdahl_min_end_to_end=_AMDAHL_MIN,
        ),
        "native_environment": CandidateClass(
            class_id="native_environment",
            plan_packages=("NATIVE-ENVIRONMENT", "NATIVE-EXECUTION", "BATCHED-ENVIRONMENT"),
            required_gates=(
                "ORACLE_EXACT",
                "TAPE_REPLAY",
                "BATCH_SINGLE",
                "RISK_PRECISION",
                "DETERMINISM",
            ),
            speedup=_STAGE_SPEEDUP,
            stretch_speedup=_STRETCH_SPEEDUP,
            memory_reduction=_MEMORY_REDUCTION,
            resource_cost_reduction=None,
            reliability_gain=_RELIABILITY_GAIN,
            amdahl_min_end_to_end=_AMDAHL_MIN,
        ),
        "learner_backend": CandidateClass(
            class_id="learner_backend",
            plan_packages=("LEARNER-OPTIMIZATION", "ROLLOUT-BUFFERS"),
            required_gates=(
                "LEARNER_FIXED_BATCH",
                "CHECKPOINT_COMPAT",
                "RISK_PRECISION",
                "DETERMINISM",
            ),
            speedup=_STAGE_SPEEDUP,
            stretch_speedup=None,
            memory_reduction=_MEMORY_REDUCTION,
            resource_cost_reduction=None,
            reliability_gain=_RELIABILITY_GAIN,
            amdahl_min_end_to_end=_AMDAHL_MIN,
        ),
        "data_storage": CandidateClass(
            class_id="data_storage",
            plan_packages=("DATA-INGESTION", "DATA-QUERY", "SHARED-DATA-ABI"),
            required_gates=("ROUNDTRIP_RECONCILE", "DETERMINISM", "TRAIN_ONLY_WORKLOAD"),
            speedup=_STAGE_SPEEDUP,
            stretch_speedup=None,
            memory_reduction=_MEMORY_REDUCTION,
            resource_cost_reduction=None,
            reliability_gain=_RELIABILITY_GAIN,
            amdahl_min_end_to_end=_AMDAHL_MIN,
        ),
        "resource_runtime": CandidateClass(
            class_id="resource_runtime",
            plan_packages=("RESOURCE-RUNTIME", "EXECUTION-DAG"),
            required_gates=("RESOURCE_BOUNDS", "DETERMINISM", "TRAIN_ONLY_WORKLOAD"),
            speedup=_STAGE_SPEEDUP,
            stretch_speedup=None,
            memory_reduction=_MEMORY_REDUCTION,
            resource_cost_reduction=None,
            reliability_gain=_RELIABILITY_GAIN,
            amdahl_min_end_to_end=_AMDAHL_MIN,
        ),
        "integrated_pipeline": CandidateClass(
            class_id="integrated_pipeline",
            plan_packages=("INTEGRATED-BENCHMARK",),
            required_gates=(
                "ORACLE_EXACT",
                "BATCH_SINGLE",
                "LEARNER_FIXED_BATCH",
                "CHECKPOINT_COMPAT",
                "ROUNDTRIP_RECONCILE",
                "RESOURCE_BOUNDS",
                "RISK_PRECISION",
                "DETERMINISM",
                "TRAIN_ONLY_WORKLOAD",
            ),
            speedup=_INTEGRATED_SPEEDUP,
            stretch_speedup=None,
            memory_reduction=None,
            resource_cost_reduction=_RESOURCE_COST_REDUCTION,
            reliability_gain=_RELIABILITY_GAIN,
            amdahl_min_end_to_end=None,
        ),
    },
)


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


def relative_spread(values: Sequence[float]) -> float:
    """Return (max - min) / median for repeated positive measurements."""
    median = statistics.median(values)
    return (max(values) - min(values)) / median


def projected_end_to_end_speedup(stage_fraction: float, stage_speedup: float) -> float:
    """Return the end-to-end speedup by Amdahl's law for one stage."""
    if not 0.0 < stage_fraction <= 1.0:
        raise TrialSummaryError(f"stage_fraction must be in (0, 1], got {stage_fraction}")
    if not math.isfinite(stage_speedup) or stage_speedup <= 0.0:
        raise TrialSummaryError(f"stage_speedup must be positive and finite, got {stage_speedup}")
    return 1.0 / ((1.0 - stage_fraction) + stage_fraction / stage_speedup)


def _ratio(measurement: Measurement) -> float:
    """Return candidate over baseline median."""
    return statistics.median(measurement.candidate) / statistics.median(measurement.baseline)


def _improvement(measurement: Measurement) -> float:
    """Return the improvement factor for speed metrics or the fractional reduction otherwise."""
    ratio = _ratio(measurement)
    if measurement.metric == "throughput":
        return ratio
    if measurement.metric == "wall_seconds":
        return 1.0 / ratio
    return 1.0 - ratio


def _validate_gate_map(summary: TrialSummary, matrix: PromotionMatrix) -> None:
    for gate_id, status in summary.correctness_gates.items():
        if gate_id not in matrix.gates:
            raise TrialSummaryError(f"unknown correctness gate: {gate_id}")
        if status not in _GATE_STATUSES:
            raise TrialSummaryError(f"gate {gate_id} has invalid status: {status}")


def _validate_measurement(measurement: Measurement) -> None:
    if not measurement.workload_id:
        raise TrialSummaryError("measurement workload_id must be non-empty")
    if measurement.metric not in _METRICS:
        raise TrialSummaryError(f"unknown metric: {measurement.metric}")
    if measurement.kind not in _KINDS:
        raise TrialSummaryError(f"unknown measurement kind: {measurement.kind}")
    for arm, values in (("baseline", measurement.baseline), ("candidate", measurement.candidate)):
        if not values:
            raise TrialSummaryError(f"{measurement.workload_id} {arm} has no repeats")
        if any(not math.isfinite(value) or value <= 0.0 for value in values):
            raise TrialSummaryError(
                f"{measurement.workload_id} {arm} repeats must be finite and positive"
            )
    if measurement.stage_fraction is not None and not 0.0 < measurement.stage_fraction <= 1.0:
        raise TrialSummaryError(f"{measurement.workload_id} stage_fraction must be in (0, 1]")


def _validate_summary(summary: TrialSummary, matrix: PromotionMatrix) -> CandidateClass:
    cls = matrix.class_for(summary.candidate_class)
    if not summary.trial_id or not summary.baseline_id or not summary.candidate_id:
        raise TrialSummaryError("trial_id, baseline_id and candidate_id must be non-empty")
    if summary.baseline_id == summary.candidate_id:
        raise TrialSummaryError("candidate_id must differ from baseline_id")
    _validate_gate_map(summary, matrix)
    seen: set[str] = set()
    for measurement in summary.measurements:
        _validate_measurement(measurement)
        key = f"{measurement.kind}:{measurement.workload_id}:{measurement.metric}"
        if key in seen:
            raise TrialSummaryError(f"duplicate measurement: {key}")
        seen.add(key)
    reliability = summary.reliability
    if reliability is not None:
        for arm, successes, attempts in (
            ("baseline", reliability.baseline_successes, reliability.baseline_attempts),
            ("candidate", reliability.candidate_successes, reliability.candidate_attempts),
        ):
            if attempts <= 0 or not 0 <= successes <= attempts:
                raise TrialSummaryError(f"reliability {arm} counts are inconsistent")
    return cls


def _evidence_gaps(
    summary: TrialSummary, matrix: PromotionMatrix, cls: CandidateClass
) -> list[str]:
    gaps: list[str] = []
    min_repeats = int(matrix.min_repeats.value)
    max_spread = matrix.max_relative_spread.value
    for measurement in summary.measurements:
        label = f"{measurement.kind} {measurement.workload_id}/{measurement.metric}"
        for arm, values in (
            ("baseline", measurement.baseline),
            ("candidate", measurement.candidate),
        ):
            if len(values) < min_repeats:
                gaps.append(f"{label}: {arm} has {len(values)} repeats, needs {min_repeats}")
            spread = relative_spread(values)
            if spread > max_spread:
                gaps.append(f"{label}: {arm} relative spread {spread:.3f} above {max_spread:g}")
        is_primary_speed = measurement.kind == "primary" and measurement.metric in _SPEED_METRICS
        if (
            is_primary_speed
            and cls.amdahl_min_end_to_end is not None
            and measurement.stage_fraction is None
        ):
            gaps.append(f"{label}: stage_fraction is required for the Amdahl gate")
    reliability = summary.reliability
    if reliability is not None:
        min_attempts = int(matrix.min_reliability_attempts.value)
        for arm, attempts in (
            ("baseline", reliability.baseline_attempts),
            ("candidate", reliability.candidate_attempts),
        ):
            if attempts < min_attempts:
                gaps.append(f"reliability {arm} has {attempts} attempts, needs {min_attempts}")
    return gaps


def _regressions(summary: TrialSummary, matrix: PromotionMatrix) -> list[str]:
    limit = matrix.max_regression.value
    found: list[str] = []
    for measurement in summary.measurements:
        ratio = _ratio(measurement)
        if measurement.metric in _HIGHER_IS_BETTER:
            regressed = ratio < 1.0 - limit
        else:
            regressed = ratio > 1.0 + limit
        if regressed:
            found.append(
                f"{measurement.kind} {measurement.workload_id}/{measurement.metric} "
                f"candidate/baseline median ratio {ratio:.3f} breaches the {limit:.0%} limit"
            )
    return found


@dataclass(frozen=True)
class _Criterion:
    name: str
    status: Literal["pass", "fail", "unmeasured"]
    note: str


def _metric_criterion(
    name: str,
    threshold: Threshold,
    primaries: Sequence[Measurement],
) -> _Criterion:
    if not primaries:
        return _Criterion(name, "unmeasured", f"no primary measurement for {name}")
    failing = [m.workload_id for m in primaries if _improvement(m) < threshold.value]
    if failing:
        return _Criterion(
            name, "fail", f"{name} below {threshold.value:g} on {', '.join(sorted(failing))}"
        )
    return _Criterion(name, "pass", f"{name} at or above {threshold.value:g} on all primaries")


def _speed_criterion(
    summary: TrialSummary, cls: CandidateClass
) -> tuple[_Criterion | None, bool, list[str]]:
    """Return the speed criterion, whether stretch is met, and Amdahl notes."""
    if cls.speedup is None:
        return None, False, []
    primaries = [
        m for m in summary.measurements if m.kind == "primary" and m.metric in _SPEED_METRICS
    ]
    criterion = _metric_criterion("speed", cls.speedup, primaries)
    if criterion.status != "pass" or cls.amdahl_min_end_to_end is None:
        stretch_met = _stretch_met(cls, primaries)
        return criterion, stretch_met, []
    amdahl_min = cls.amdahl_min_end_to_end.value
    notes: list[str] = []
    negligible: list[str] = []
    for measurement in primaries:
        fraction = measurement.stage_fraction
        if fraction is None:
            raise TrialSummaryError("stage_fraction must be checked before the Amdahl gate")
        projected = projected_end_to_end_speedup(fraction, _improvement(measurement))
        notes.append(f"{measurement.workload_id} projected end-to-end speedup {projected:.3f}")
        if projected < amdahl_min:
            negligible.append(measurement.workload_id)
    stretch_met = _stretch_met(cls, primaries)
    if negligible:
        failed = _Criterion(
            "speed",
            "fail",
            "stage speedup does not project to end-to-end "
            f"{amdahl_min:g} on {', '.join(sorted(negligible))}",
        )
        return failed, stretch_met, notes
    return criterion, stretch_met, notes


def _stretch_met(cls: CandidateClass, primaries: Sequence[Measurement]) -> bool:
    if cls.stretch_speedup is None or not primaries:
        return False
    return all(_improvement(m) >= cls.stretch_speedup.value for m in primaries)


def _criteria(
    summary: TrialSummary, cls: CandidateClass
) -> tuple[list[_Criterion], bool, list[str]]:
    criteria: list[_Criterion] = []
    speed, stretch_met, notes = _speed_criterion(summary, cls)
    if speed is not None:
        criteria.append(speed)
    primaries = [m for m in summary.measurements if m.kind == "primary"]
    if cls.memory_reduction is not None:
        memory = [m for m in primaries if m.metric == "peak_memory_bytes"]
        criteria.append(_metric_criterion("memory", cls.memory_reduction, memory))
    if cls.resource_cost_reduction is not None:
        cost = [m for m in primaries if m.metric == "resource_cost"]
        criteria.append(_metric_criterion("resource_cost", cls.resource_cost_reduction, cost))
    if cls.reliability_gain is not None:
        reliability = summary.reliability
        if reliability is None:
            criteria.append(_Criterion("reliability", "unmeasured", "no reliability counts"))
        else:
            base = reliability.baseline_successes / reliability.baseline_attempts
            cand = reliability.candidate_successes / reliability.candidate_attempts
            gain = cand - base
            status: Literal["pass", "fail"] = (
                "pass" if gain >= cls.reliability_gain.value else "fail"
            )
            criteria.append(
                _Criterion(
                    "reliability",
                    status,
                    f"success-rate gain {gain:+.3f} against threshold {cls.reliability_gain.value:g}",
                )
            )
    return criteria, stretch_met, notes


def _gate_failures(summary: TrialSummary) -> list[str]:
    return sorted(gate for gate, status in summary.correctness_gates.items() if status == "fail")


def _required_gates(
    summary: TrialSummary, matrix: PromotionMatrix, cls: CandidateClass
) -> list[str]:
    required = list(cls.required_gates)
    if summary.semantics_changed:
        required.append(matrix.scientific_gate)
    return sorted(set(required))


def _decision(
    summary: TrialSummary,
    outcome: Outcome,
    reasons: Sequence[str],
    *,
    passed: Sequence[str] = (),
    failed: Sequence[str] = (),
    stretch_met: bool = False,
    notes: Sequence[str] = (),
) -> TrialDecision:
    return TrialDecision(
        trial_id=summary.trial_id,
        candidate_class=summary.candidate_class,
        outcome=outcome,
        reasons=tuple(reasons),
        passed_criteria=tuple(passed),
        failed_criteria=tuple(failed),
        stretch_met=stretch_met,
        default_implementation=summary.baseline_id,
        switch_eligible=outcome == "promote",
        notes=tuple(notes),
    )


def evaluate_trial(
    summary: TrialSummary, matrix: PromotionMatrix = DEFAULT_MATRIX
) -> TrialDecision:
    """Decide one candidate trial against the matrix.

    Order of checks: malformed input raises. A failed correctness gate rejects.
    A required gate that did not run gives insufficient evidence. Missing or
    noisy repeats, or missing reliability attempts, give insufficient evidence.
    Any measured regression beyond the limit rejects. Otherwise any passing
    criterion promotes. If no criterion passes and some applicable criterion
    was never measured, the result is insufficient evidence. If every
    applicable criterion was measured and failed, the result is a rejection.
    """
    cls = _validate_summary(summary, matrix)

    failed_gates = _gate_failures(summary)
    if failed_gates:
        return _decision(
            summary,
            "reject",
            [f"correctness gate failed: {gate}" for gate in failed_gates],
        )

    required = _required_gates(summary, matrix, cls)
    unrun = [gate for gate in required if summary.correctness_gates.get(gate, "not_run") != "pass"]
    if unrun:
        return _decision(
            summary,
            "insufficient_evidence",
            [f"correctness gate not run: {gate}" for gate in unrun],
        )

    gaps = _evidence_gaps(summary, matrix, cls)
    if gaps:
        return _decision(summary, "insufficient_evidence", gaps)

    regressions = _regressions(summary, matrix)
    if regressions:
        return _decision(summary, "reject", regressions)

    criteria, stretch_met, notes = _criteria(summary, cls)
    passed = [c.name for c in criteria if c.status == "pass"]
    failed = [c for c in criteria if c.status == "fail"]
    unmeasured = [c for c in criteria if c.status == "unmeasured"]
    if passed:
        return _decision(
            summary,
            "promote",
            [c.note for c in criteria if c.status == "pass"],
            passed=passed,
            failed=[c.name for c in failed],
            stretch_met=stretch_met,
            notes=notes,
        )
    if unmeasured:
        return _decision(
            summary,
            "insufficient_evidence",
            [c.note for c in unmeasured],
            failed=[c.name for c in failed],
            stretch_met=stretch_met,
            notes=notes,
        )
    return _decision(
        summary,
        "reject",
        [c.note for c in failed] or ["no promotion criterion passed"],
        failed=[c.name for c in failed],
        stretch_met=stretch_met,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Parsing and serialization
# ---------------------------------------------------------------------------


def _require_mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise TrialSummaryError(f"{where} must be a JSON object")
    return cast(Mapping[str, object], value)


def _require_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise TrialSummaryError(f"{key} must be a string")
    return value


def _require_int(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TrialSummaryError(f"{key} must be an integer")
    return value


def _float_tuple(value: object, where: str) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise TrialSummaryError(f"{where} must be a list of numbers")
    out: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TrialSummaryError(f"{where} must contain only numbers")
        out.append(float(item))
    return tuple(out)


def _parse_measurement(raw: object) -> Measurement:
    data = _require_mapping(raw, "measurement")
    stage = data.get("stage_fraction")
    if stage is not None and (isinstance(stage, bool) or not isinstance(stage, (int, float))):
        raise TrialSummaryError("stage_fraction must be a number or null")
    kind = _require_str(data, "kind")
    metric = _require_str(data, "metric")
    if kind not in _KINDS:
        raise TrialSummaryError(f"unknown measurement kind: {kind}")
    if metric not in _METRICS:
        raise TrialSummaryError(f"unknown metric: {metric}")
    return Measurement(
        workload_id=_require_str(data, "workload_id"),
        metric=cast(Metric, metric),
        kind=cast(MeasurementKind, kind),
        baseline=_float_tuple(data.get("baseline"), "baseline"),
        candidate=_float_tuple(data.get("candidate"), "candidate"),
        stage_fraction=None if stage is None else float(stage),
    )


def trial_summary_from_mapping(raw: Mapping[str, object]) -> TrialSummary:
    """Build a ``TrialSummary`` from a decoded JSON object, validating its shape."""
    data = _require_mapping(raw, "trial summary")
    if _require_int(data, "schema_version") != 1:
        raise TrialSummaryError("unsupported trial summary schema_version")
    gates_raw = _require_mapping(data.get("correctness_gates"), "correctness_gates")
    gates: dict[str, GateStatus] = {}
    for gate_id, status in gates_raw.items():
        if not isinstance(status, str) or status not in _GATE_STATUSES:
            raise TrialSummaryError(f"gate {gate_id} has invalid status: {status}")
        gates[gate_id] = cast(GateStatus, status)
    measurements_raw = data.get("measurements")
    if not isinstance(measurements_raw, list):
        raise TrialSummaryError("measurements must be a list")
    reliability: ReliabilityCounts | None = None
    reliability_raw = data.get("reliability")
    if reliability_raw is not None:
        rel = _require_mapping(reliability_raw, "reliability")
        reliability = ReliabilityCounts(
            baseline_successes=_require_int(rel, "baseline_successes"),
            baseline_attempts=_require_int(rel, "baseline_attempts"),
            candidate_successes=_require_int(rel, "candidate_successes"),
            candidate_attempts=_require_int(rel, "candidate_attempts"),
        )
    semantics = data.get("semantics_changed")
    if not isinstance(semantics, bool):
        raise TrialSummaryError("semantics_changed must be a boolean")
    return TrialSummary(
        trial_id=_require_str(data, "trial_id"),
        candidate_class=_require_str(data, "candidate_class"),
        baseline_id=_require_str(data, "baseline_id"),
        candidate_id=_require_str(data, "candidate_id"),
        correctness_gates=gates,
        semantics_changed=semantics,
        measurements=tuple(_parse_measurement(item) for item in measurements_raw),
        reliability=reliability,
    )


def load_trial_summary(path: Path) -> TrialSummary:
    """Read a trial summary JSON file. The file is only read, never written."""
    decoded = json.loads(path.read_text(encoding="utf-8"))
    return trial_summary_from_mapping(_require_mapping(decoded, "trial summary file"))


def _threshold_json(threshold: Threshold | None) -> dict[str, object] | None:
    if threshold is None:
        return None
    return {"value": threshold.value, "source": threshold.source, "reason": threshold.reason}


def matrix_to_jsonable(matrix: PromotionMatrix = DEFAULT_MATRIX) -> dict[str, object]:
    """Serialize the matrix for the markdown mirror and for review."""
    return {
        "schema_version": 1,
        "min_repeats": _threshold_json(matrix.min_repeats),
        "max_relative_spread": _threshold_json(matrix.max_relative_spread),
        "min_reliability_attempts": _threshold_json(matrix.min_reliability_attempts),
        "max_regression": _threshold_json(matrix.max_regression),
        "scientific_gate": matrix.scientific_gate,
        "gates": {gate.gate_id: gate.definition for gate in matrix.gates.values()},
        "classes": {
            cls.class_id: {
                "plan_packages": list(cls.plan_packages),
                "required_gates": list(cls.required_gates),
                "speedup": _threshold_json(cls.speedup),
                "stretch_speedup": _threshold_json(cls.stretch_speedup),
                "memory_reduction": _threshold_json(cls.memory_reduction),
                "resource_cost_reduction": _threshold_json(cls.resource_cost_reduction),
                "reliability_gain": _threshold_json(cls.reliability_gain),
                "amdahl_min_end_to_end": _threshold_json(cls.amdahl_min_end_to_end),
            }
            for cls in matrix.classes.values()
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print the decision for one trial summary file as JSON.

    The command reads the summary file and prints the decision. It writes nothing
    else. Exit status 0 means a decision was printed, whatever its outcome. Exit
    status 2 means the summary could not be read or is malformed.
    """
    parser = argparse.ArgumentParser(description="Decide one performance candidate trial.")
    parser.add_argument("summary", type=Path, help="Trial summary JSON file.")
    args = parser.parse_args(argv)
    try:
        decision = evaluate_trial(load_trial_summary(args.summary))
    except (OSError, ValueError) as exc:
        print(f"invalid trial summary: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(decision), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
