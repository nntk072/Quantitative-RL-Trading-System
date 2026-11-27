"""Known-answer tests for the PERFORMANCE-POLICY promotion checker."""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from research_tools.compute.benchmarks import performance_promotion as pp
from research_tools.compute.benchmarks.performance_promotion import (
    DEFAULT_MATRIX,
    GateStatus,
    Measurement,
    Metric,
    ReliabilityCounts,
    TrialSummary,
    TrialSummaryError,
    evaluate_trial,
    load_trial_summary,
    matrix_to_jsonable,
    projected_end_to_end_speedup,
    relative_spread,
    trial_summary_from_mapping,
)

ROOT = Path(__file__).resolve().parents[3]
MATRIX_MD = ROOT / "planning/native_modernization/performance_policy/promotion_matrix.md"


def _tight(center: float) -> tuple[float, ...]:
    """Five repeats with median ``center`` and relative spread 0.02."""
    return (center, center * 1.01, center * 0.99, center, center * 1.005)


def _primary(
    metric: Metric,
    candidate_center: float,
    *,
    baseline_center: float = 10.0,
    stage: float | None = 0.5,
    workload: str = "stage_workload",
) -> Measurement:
    return Measurement(
        workload_id=workload,
        metric=metric,
        kind="primary",
        baseline=_tight(baseline_center),
        candidate=_tight(candidate_center),
        stage_fraction=stage,
    )


def _no_gain() -> ReliabilityCounts:
    return ReliabilityCounts(
        baseline_successes=14,
        baseline_attempts=20,
        candidate_successes=14,
        candidate_attempts=20,
    )


def _gates(
    class_id: str, overrides: Mapping[str, GateStatus] | None = None
) -> dict[str, GateStatus]:
    cls = DEFAULT_MATRIX.classes.get(class_id)
    required = () if cls is None else cls.required_gates
    gates: dict[str, GateStatus] = {gate: "pass" for gate in required}
    gates.update(overrides or {})
    return gates


def _summary(
    measurements: list[Measurement],
    *,
    class_id: str = "native_environment",
    gates: Mapping[str, GateStatus] | None = None,
    semantics: bool = False,
    reliability: ReliabilityCounts | None = None,
) -> TrialSummary:
    return TrialSummary(
        trial_id="trial-1",
        candidate_class=class_id,
        baseline_id="python_reference",
        candidate_id="native_batch",
        correctness_gates=_gates(class_id, gates),
        semantics_changed=semantics,
        measurements=tuple(measurements),
        reliability=_no_gain() if reliability is None else reliability,
    )


def _native_memory_flat() -> Measurement:
    return _primary("peak_memory_bytes", 1000.0, baseline_center=1000.0, workload="memory")


# ---------------------------------------------------------------------------
# Speed, memory, reliability, Amdahl
# ---------------------------------------------------------------------------


def test_sustained_stage_speedup_with_tight_repeats_promotes() -> None:
    decision = evaluate_trial(_summary([_primary("throughput", 16.0), _native_memory_flat()]))

    assert decision.outcome == "promote"
    assert decision.passed_criteria == ("speed",)
    assert decision.failed_criteria == ("memory", "reliability")
    assert decision.default_implementation == "python_reference"
    assert decision.switch_eligible is True
    assert decision.stretch_met is False


def test_stretch_target_is_reported_but_does_not_gate() -> None:
    decision = evaluate_trial(_summary([_primary("throughput", 32.0), _native_memory_flat()]))

    assert decision.outcome == "promote"
    assert decision.stretch_met is True


def test_single_fast_run_on_noisy_repeats_is_insufficient_not_promoted() -> None:
    # Best run is 2.4x, but the median ratio is 1.55x and the spread is 0.645.
    noisy = Measurement(
        workload_id="stage_workload",
        metric="throughput",
        kind="primary",
        baseline=(10.0, 10.0, 10.0, 10.0, 10.0),
        candidate=(24.0, 14.0, 15.0, 16.0, 15.5),
        stage_fraction=0.5,
    )
    assert max(noisy.candidate) / 10.0 >= 1.5
    assert statistics.median(noisy.candidate) / 10.0 >= 1.5

    decision = evaluate_trial(_summary([noisy, _native_memory_flat()]))

    assert decision.outcome == "insufficient_evidence"
    assert any("relative spread" in reason for reason in decision.reasons)
    assert decision.switch_eligible is False


def test_median_below_threshold_with_tight_repeats_rejects_when_all_criteria_measured() -> None:
    decision = evaluate_trial(
        _summary(
            [
                _primary("throughput", 12.0, stage=1.0),
                _primary("peak_memory_bytes", 950.0, baseline_center=1000.0, workload="memory"),
            ],
            reliability=ReliabilityCounts(14, 20, 14, 20),
        )
    )

    assert decision.outcome == "reject"
    assert decision.passed_criteria == ()
    assert "speed" in decision.failed_criteria
    assert decision.default_implementation == "python_reference"


def test_unmeasured_applicable_criterion_keeps_failed_speed_insufficient() -> None:
    decision = evaluate_trial(_summary([_primary("throughput", 12.0, stage=1.0)]))

    assert decision.outcome == "insufficient_evidence"
    assert any("memory" in reason for reason in decision.reasons)


def test_memory_reduction_promotes_when_speed_does_not() -> None:
    decision = evaluate_trial(
        _summary(
            [
                _primary("throughput", 10.0, stage=0.5),
                _primary("peak_memory_bytes", 700.0, baseline_center=1000.0, workload="memory"),
            ]
        )
    )

    assert decision.outcome == "promote"
    assert decision.passed_criteria == ("memory",)
    assert "speed" in decision.failed_criteria


def test_amdahl_projection_known_answers() -> None:
    assert projected_end_to_end_speedup(0.5, 2.0) == pytest.approx(4.0 / 3.0)
    assert projected_end_to_end_speedup(1.0, 2.0) == pytest.approx(2.0)
    assert projected_end_to_end_speedup(0.02, 2.0) == pytest.approx(1.0 / 0.99)


def test_stage_speedup_without_end_to_end_benefit_is_rejected() -> None:
    # 2.0x on a stage that is 2% of wall time projects to about 1.01x end to end.
    decision = evaluate_trial(
        _summary([_primary("throughput", 20.0, stage=0.02), _native_memory_flat()])
    )

    assert decision.outcome == "reject"
    assert any("does not project to end-to-end" in reason for reason in decision.reasons)


def test_negligible_stage_speedup_still_promotes_on_memory() -> None:
    decision = evaluate_trial(
        _summary(
            [
                _primary("throughput", 20.0, stage=0.02),
                _primary("peak_memory_bytes", 700.0, baseline_center=1000.0, workload="memory"),
            ]
        )
    )

    assert decision.outcome == "promote"
    assert decision.passed_criteria == ("memory",)


def test_reliability_gain_promotes_with_enough_attempts() -> None:
    decision = evaluate_trial(
        _summary(
            [_primary("throughput", 10.0, stage=0.5), _native_memory_flat()],
            reliability=ReliabilityCounts(14, 20, 16, 20),
        )
    )

    assert decision.outcome == "promote"
    assert decision.passed_criteria == ("reliability",)


def test_reliability_gain_with_too_few_attempts_is_insufficient() -> None:
    decision = evaluate_trial(
        _summary(
            [_primary("throughput", 10.0, stage=0.5), _native_memory_flat()],
            reliability=ReliabilityCounts(14, 20, 16, 19),
        )
    )

    assert decision.outcome == "insufficient_evidence"
    assert any("reliability candidate has 19 attempts" in reason for reason in decision.reasons)


def test_stage_fraction_missing_for_amdahl_is_insufficient() -> None:
    decision = evaluate_trial(
        _summary([_primary("throughput", 16.0, stage=None), _native_memory_flat()])
    )

    assert decision.outcome == "insufficient_evidence"
    assert any("stage_fraction is required" in reason for reason in decision.reasons)


# ---------------------------------------------------------------------------
# Dispersion and repeats
# ---------------------------------------------------------------------------


def test_relative_spread_known_answer() -> None:
    assert relative_spread((9.0, 10.0, 11.0)) == pytest.approx(0.2)


def test_fewer_than_five_repeats_is_insufficient() -> None:
    four = Measurement(
        workload_id="stage_workload",
        metric="throughput",
        kind="primary",
        baseline=_tight(10.0)[:4],
        candidate=_tight(16.0)[:4],
        stage_fraction=0.5,
    )

    decision = evaluate_trial(_summary([four, _native_memory_flat()]))

    assert decision.outcome == "insufficient_evidence"
    assert any("needs 5" in reason for reason in decision.reasons)


# ---------------------------------------------------------------------------
# Correctness gates
# ---------------------------------------------------------------------------


def test_failed_correctness_gate_rejects_despite_large_speedup() -> None:
    decision = evaluate_trial(
        _summary(
            [_primary("throughput", 50.0, stage=1.0), _native_memory_flat()],
            gates={"TAPE_REPLAY": "fail"},
        )
    )

    assert decision.outcome == "reject"
    assert decision.reasons == ("correctness gate failed: TAPE_REPLAY",)
    assert decision.passed_criteria == ()
    assert decision.switch_eligible is False


def test_required_gate_not_run_is_insufficient_despite_speedup() -> None:
    decision = evaluate_trial(
        _summary(
            [_primary("throughput", 30.0, stage=1.0), _native_memory_flat()],
            gates={"BATCH_SINGLE": "not_run"},
        )
    )

    assert decision.outcome == "insufficient_evidence"
    assert decision.reasons == ("correctness gate not run: BATCH_SINGLE",)


def test_missing_required_gate_is_treated_as_not_run() -> None:
    summary = _summary([_primary("throughput", 30.0, stage=1.0), _native_memory_flat()])
    gates = dict(summary.correctness_gates)
    del gates["DETERMINISM"]
    partial = TrialSummary(
        trial_id=summary.trial_id,
        candidate_class=summary.candidate_class,
        baseline_id=summary.baseline_id,
        candidate_id=summary.candidate_id,
        correctness_gates=gates,
        semantics_changed=False,
        measurements=summary.measurements,
        reliability=summary.reliability,
    )

    assert evaluate_trial(partial).outcome == "insufficient_evidence"


def test_scientific_comparison_is_required_when_semantics_change() -> None:
    measurements = [_primary("throughput", 16.0), _native_memory_flat()]

    not_run = evaluate_trial(_summary(measurements, semantics=True))
    assert not_run.outcome == "insufficient_evidence"
    assert "correctness gate not run: SCIENTIFIC_COMPARISON" in not_run.reasons

    passed = evaluate_trial(
        _summary(measurements, semantics=True, gates={"SCIENTIFIC_COMPARISON": "pass"})
    )
    assert passed.outcome == "promote"

    failed = evaluate_trial(
        _summary(measurements, semantics=True, gates={"SCIENTIFIC_COMPARISON": "fail"})
    )
    assert failed.outcome == "reject"


# ---------------------------------------------------------------------------
# Regression limit
# ---------------------------------------------------------------------------


def test_guard_regression_beyond_five_percent_rejects_despite_speed() -> None:
    guard = Measurement(
        workload_id="comparable_required",
        metric="throughput",
        kind="guard",
        baseline=_tight(10.0),
        candidate=_tight(9.4),
    )

    decision = evaluate_trial(
        _summary([_primary("throughput", 20.0, stage=1.0), _native_memory_flat(), guard])
    )

    assert decision.outcome == "reject"
    assert any("comparable_required/throughput" in reason for reason in decision.reasons)


def test_guard_slowdown_within_five_percent_is_not_a_regression() -> None:
    guard = Measurement(
        workload_id="comparable_required",
        metric="throughput",
        kind="guard",
        baseline=_tight(10.0),
        candidate=_tight(9.6),
    )

    decision = evaluate_trial(
        _summary([_primary("throughput", 20.0, stage=1.0), _native_memory_flat(), guard])
    )

    assert decision.outcome == "promote"


def test_memory_increase_beyond_five_percent_is_a_regression() -> None:
    guard = Measurement(
        workload_id="comparable_required",
        metric="peak_memory_bytes",
        kind="guard",
        baseline=_tight(1000.0),
        candidate=_tight(1100.0),
    )

    decision = evaluate_trial(_summary([_primary("throughput", 20.0, stage=1.0), guard]))

    assert decision.outcome == "reject"
    assert any("breaches the 5% limit" in reason for reason in decision.reasons)


# ---------------------------------------------------------------------------
# Integrated pipeline and the other classes
# ---------------------------------------------------------------------------


def test_integrated_cost_reduction_promotes_below_speed_threshold() -> None:
    decision = evaluate_trial(
        _summary(
            [
                _primary("throughput", 12.5, stage=None, workload="end_to_end"),
                _primary("resource_cost", 70.0, baseline_center=100.0, workload="end_to_end"),
            ],
            class_id="integrated_pipeline",
        )
    )

    assert decision.outcome == "promote"
    assert decision.passed_criteria == ("resource_cost",)
    assert "speed" in decision.failed_criteria


def test_integrated_speed_is_not_subject_to_amdahl() -> None:
    decision = evaluate_trial(
        _summary(
            [
                _primary("throughput", 13.5, stage=None, workload="end_to_end"),
                _primary("resource_cost", 95.0, baseline_center=100.0, workload="end_to_end"),
            ],
            class_id="integrated_pipeline",
        )
    )

    assert decision.outcome == "promote"
    assert decision.passed_criteria == ("speed",)


def test_integrated_speed_below_threshold_with_small_cost_change_rejects() -> None:
    decision = evaluate_trial(
        _summary(
            [
                _primary("throughput", 12.5, stage=None, workload="end_to_end"),
                _primary("resource_cost", 95.0, baseline_center=100.0, workload="end_to_end"),
            ],
            class_id="integrated_pipeline",
        )
    )

    assert decision.outcome == "reject"
    assert decision.passed_criteria == ()


@pytest.mark.parametrize("class_id", sorted(DEFAULT_MATRIX.classes))
def test_every_class_promotes_on_its_applicable_criteria(class_id: str) -> None:
    cls = DEFAULT_MATRIX.classes[class_id]
    measurements: list[Measurement] = []
    if cls.speedup is not None:
        stage = None if cls.amdahl_min_end_to_end is None else 0.5
        measurements.append(_primary("throughput", 20.0, stage=stage, workload="speed"))
    if cls.memory_reduction is not None:
        measurements.append(
            _primary("peak_memory_bytes", 500.0, baseline_center=1000.0, workload="memory")
        )
    if cls.resource_cost_reduction is not None:
        measurements.append(_primary("resource_cost", 50.0, baseline_center=100.0, workload="cost"))
    reliability = ReliabilityCounts(10, 20, 18, 20)

    decision = evaluate_trial(_summary(measurements, class_id=class_id, reliability=reliability))

    assert decision.outcome == "promote", decision.reasons
    assert "reliability" in decision.passed_criteria


def test_unknown_class_and_invalid_inputs_fail_closed() -> None:
    with pytest.raises(TrialSummaryError, match="unknown candidate class"):
        evaluate_trial(_summary([_primary("throughput", 16.0)], class_id="not_a_class"))


# ---------------------------------------------------------------------------
# Parsing and validation
# ---------------------------------------------------------------------------


def _measurement_dict(measurement: Measurement) -> dict[str, Any]:
    return {
        "workload_id": measurement.workload_id,
        "metric": measurement.metric,
        "kind": measurement.kind,
        "baseline": list(measurement.baseline),
        "candidate": list(measurement.candidate),
        "stage_fraction": measurement.stage_fraction,
    }


def _payload(summary: TrialSummary) -> dict[str, Any]:
    reliability = summary.reliability
    return {
        "schema_version": 1,
        "trial_id": summary.trial_id,
        "candidate_class": summary.candidate_class,
        "baseline_id": summary.baseline_id,
        "candidate_id": summary.candidate_id,
        "correctness_gates": dict(summary.correctness_gates),
        "semantics_changed": summary.semantics_changed,
        "measurements": [_measurement_dict(m) for m in summary.measurements],
        "reliability": None
        if reliability is None
        else {
            "baseline_successes": reliability.baseline_successes,
            "baseline_attempts": reliability.baseline_attempts,
            "candidate_successes": reliability.candidate_successes,
            "candidate_attempts": reliability.candidate_attempts,
        },
    }


def test_json_round_trip_loads_and_decides_the_same_trial(tmp_path: Path) -> None:
    summary = _summary([_primary("throughput", 16.0), _native_memory_flat()])
    path = tmp_path / "trial.json"
    path.write_text(json.dumps(_payload(summary)), encoding="utf-8")

    loaded = load_trial_summary(path)

    assert loaded == summary
    assert evaluate_trial(loaded) == evaluate_trial(summary)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(schema_version=2),
        lambda p: p.update(candidate_id="python_reference"),
        lambda p: p.update(candidate_class="unknown"),
        lambda p: p["correctness_gates"].update(NOT_A_GATE="pass"),
        lambda p: p["correctness_gates"].update(TAPE_REPLAY="maybe"),
        lambda p: p["measurements"][0].update(metric="latency"),
        lambda p: p["measurements"][0].update(kind="secondary"),
        lambda p: p["measurements"][0].update(baseline=[]),
        lambda p: p["measurements"][0].update(candidate=[1.0, float("nan")]),
        lambda p: p["measurements"][0].update(candidate=[1.0, 0.0]),
        lambda p: p["measurements"][0].update(baseline=[True, 2.0]),
        lambda p: p["measurements"][0].update(stage_fraction=1.5),
        lambda p: p["measurements"].append(p["measurements"][0]),
        lambda p: p.update(
            reliability={
                "baseline_successes": 21,
                "baseline_attempts": 20,
                "candidate_successes": 1,
                "candidate_attempts": 20,
            }
        ),
        lambda p: p.update(semantics_changed="no"),
    ],
)
def test_malformed_summaries_raise_instead_of_becoming_evidence(
    mutate: Callable[[dict[str, Any]], object],
) -> None:
    payload = _payload(_summary([_primary("throughput", 16.0), _native_memory_flat()]))
    mutate(payload)

    with pytest.raises(TrialSummaryError):
        decision_summary = trial_summary_from_mapping(payload)
        evaluate_trial(decision_summary)


def test_identical_baseline_and_candidate_ids_are_rejected_as_malformed() -> None:
    summary = _summary([_primary("throughput", 16.0)])
    same = TrialSummary(
        trial_id=summary.trial_id,
        candidate_class=summary.candidate_class,
        baseline_id="same",
        candidate_id="same",
        correctness_gates=summary.correctness_gates,
        semantics_changed=False,
        measurements=summary.measurements,
        reliability=summary.reliability,
    )

    with pytest.raises(TrialSummaryError, match="must differ"):
        evaluate_trial(same)


# ---------------------------------------------------------------------------
# Rejected trials never write to the selected implementation
# ---------------------------------------------------------------------------


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_rejected_trial_leaves_selected_implementation_tree_unchanged(tmp_path: Path) -> None:
    implementation = tmp_path / "selected_impl"
    implementation.mkdir()
    (implementation / "kernel.py").write_text("VALUE = 1\n", encoding="utf-8")
    trial_path = tmp_path / "trial.json"
    rejected = _summary(
        [_primary("throughput", 12.0, stage=1.0), _native_memory_flat()],
        gates={"ORACLE_EXACT": "fail"},
    )
    trial_path.write_text(json.dumps(_payload(rejected)), encoding="utf-8")
    before = _tree_snapshot(tmp_path)

    decision = evaluate_trial(load_trial_summary(trial_path))

    assert _tree_snapshot(tmp_path) == before
    assert decision.outcome == "reject"
    assert decision.default_implementation == "python_reference"
    assert decision.switch_eligible is False


def test_every_non_promote_outcome_keeps_the_baseline_as_default() -> None:
    cases = [
        _summary([_primary("throughput", 16.0)], gates={"TAPE_REPLAY": "fail"}),
        _summary([_primary("throughput", 16.0)], gates={"TAPE_REPLAY": "not_run"}),
        _summary([_primary("throughput", 11.0, stage=1.0), _native_memory_flat()]),
    ]
    for summary in cases:
        decision = evaluate_trial(summary)
        assert decision.outcome != "promote"
        assert decision.default_implementation == "python_reference"
        assert decision.switch_eligible is False


# ---------------------------------------------------------------------------
# Matrix mirror and recorded reasons
# ---------------------------------------------------------------------------


def _matrix_json_block(markdown: str) -> dict[str, object]:
    start = markdown.index("```json")
    body_start = markdown.index("\n", start) + 1
    body_end = markdown.index("\n```", body_start)
    decoded = json.loads(markdown[body_start:body_end])
    assert isinstance(decoded, dict)
    return decoded


def test_markdown_matrix_block_equals_the_typed_matrix() -> None:
    markdown = MATRIX_MD.read_text(encoding="utf-8")

    assert _matrix_json_block(markdown) == matrix_to_jsonable(DEFAULT_MATRIX)


def test_every_threshold_records_its_source_and_a_reason() -> None:
    thresholds = [
        DEFAULT_MATRIX.min_repeats,
        DEFAULT_MATRIX.max_relative_spread,
        DEFAULT_MATRIX.min_reliability_attempts,
        DEFAULT_MATRIX.max_regression,
    ]
    for cls in DEFAULT_MATRIX.classes.values():
        thresholds.extend(
            value
            for value in (
                cls.speedup,
                cls.stretch_speedup,
                cls.memory_reduction,
                cls.resource_cost_reduction,
                cls.reliability_gain,
                cls.amdahl_min_end_to_end,
            )
            if value is not None
        )
    for threshold in thresholds:
        assert threshold.source in {"planner", "lead_default"}
        assert len(threshold.reason.split()) >= 8


def test_every_class_requires_only_defined_gates() -> None:
    for cls in DEFAULT_MATRIX.classes.values():
        assert set(cls.required_gates) <= set(DEFAULT_MATRIX.gates)
        assert cls.speedup is not None
        is_integrated = cls.class_id == "integrated_pipeline"
        assert (cls.amdahl_min_end_to_end is None) == is_integrated
    assert DEFAULT_MATRIX.scientific_gate in DEFAULT_MATRIX.gates


def test_initial_matrix_values_match_the_recorded_sign_off() -> None:
    assert DEFAULT_MATRIX.min_repeats.value == 5
    assert DEFAULT_MATRIX.max_relative_spread.value == pytest.approx(0.15)
    assert DEFAULT_MATRIX.min_reliability_attempts.value == 20
    assert DEFAULT_MATRIX.max_regression.value == pytest.approx(0.05)
    native = DEFAULT_MATRIX.classes["native_environment"]
    assert native.speedup is not None and native.speedup.value == pytest.approx(1.5)
    assert native.stretch_speedup is not None and native.stretch_speedup.value == pytest.approx(3.0)
    integrated = DEFAULT_MATRIX.classes["integrated_pipeline"]
    assert integrated.speedup is not None and integrated.speedup.value == pytest.approx(1.3)
    assert integrated.resource_cost_reduction is not None
    assert integrated.resource_cost_reduction.value == pytest.approx(0.25)


def test_cli_prints_the_decision_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "trial.json"
    path.write_text(
        json.dumps(_payload(_summary([_primary("throughput", 16.0), _native_memory_flat()]))),
        encoding="utf-8",
    )

    assert pp.main([str(path)]) == 0

    decoded = json.loads(capsys.readouterr().out)
    assert decoded["outcome"] == "promote"
    assert decoded["default_implementation"] == "python_reference"
    assert decoded["switch_eligible"] is True


def test_cli_exits_two_on_malformed_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{}", encoding="utf-8")

    assert pp.main([str(path)]) == 2
    assert "invalid trial summary" in capsys.readouterr().err
