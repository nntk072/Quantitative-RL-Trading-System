"""Contract tests for reusable research execution and scientific utility modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from experiments.research import compute_budget, execution, history, statistics, workflow
from experiments.research.catalog import load_research_catalog
from experiments.research.qualification import (
    build_qualification_bundle,
    qualified_checkpoint_by_seed,
)

SOURCE = "a" * 40


def _bundle(*commands: execution.CommandSpec) -> execution.CommandBundle:
    return execution.CommandBundle(
        source_commit=SOURCE,
        experiment_id="research_contract",
        domain="validation",
        commands=commands,
    )


def _command(name: str, *, return_code: int = 0, **kwargs: Any) -> execution.CommandSpec:
    return execution.CommandSpec(
        command_id=name,
        argv=(sys.executable, "-c", f"raise SystemExit({return_code})"),
        variant_id=name,
        component="source",
        **kwargs,
    )


def test_command_graph_executes_and_resumes_without_repeating_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(execution, "_git_state", lambda: (SOURCE, True))
    bundle = _bundle(_command("source"), _command("dependent", depends_on=("source",)))
    run_root = tmp_path / "execution"
    result = execution.execute_command_bundle(
        bundle,
        run_root=run_root,
        max_workers=2,
        allow_experiments=False,
    )
    assert result["status"] == "passed"
    assert [item["component"] for item in result["commands"]] == ["source", "source"]
    assert all(item["variant_id"] == item["command_id"] for item in result["commands"])
    second = execution.execute_command_bundle(
        bundle,
        run_root=run_root,
        max_workers=1,
        allow_experiments=False,
        resume=True,
    )
    assert second["status"] == "passed"
    assert len(list((run_root / "commands" / "source").glob("attempt_*"))) == 1


def test_failed_and_blocked_commands_retain_component_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(execution, "_git_state", lambda: (SOURCE, True))
    bundle = _bundle(
        _command("failure", return_code=3),
        _command("blocked", depends_on=("failure",)),
    )
    root = tmp_path / "failed"
    result = execution.execute_command_bundle(
        bundle,
        run_root=root,
        max_workers=1,
        allow_experiments=False,
    )
    assert result["status"] == "failed"
    assert [x["status"] for x in result["commands"]] == ["failed", "blocked"]
    assert result["commands"][1]["component"] == "source"
    with pytest.raises(ValueError, match="retry_failed"):
        execution.execute_command_bundle(
            bundle,
            run_root=root,
            max_workers=1,
            allow_experiments=False,
            resume=True,
        )
    retried = execution.execute_command_bundle(
        bundle,
        run_root=root,
        max_workers=1,
        allow_experiments=False,
        resume=True,
        retry_failed=True,
    )
    assert retried["status"] == "failed"


def test_execution_rejects_stale_source_bad_worktree_and_invalid_resource_controls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(_command("source", experiment=True))
    monkeypatch.setattr(execution, "_git_state", lambda: (SOURCE, False))
    with pytest.raises(ValueError, match="clean source"):
        execution.execute_command_bundle(
            bundle,
            run_root=tmp_path / "dirty",
            max_workers=1,
            allow_experiments=True,
        )
    monkeypatch.setattr(execution, "_git_state", lambda: ("b" * 40, True))
    with pytest.raises(ValueError, match="stale"):
        execution.execute_command_bundle(
            bundle,
            run_root=tmp_path / "stale",
            max_workers=1,
            allow_experiments=True,
        )
    monkeypatch.setattr(execution, "_git_state", lambda: (SOURCE, True))
    with pytest.raises(ValueError, match="allow_experiments"):
        execution.execute_command_bundle(
            bundle,
            run_root=tmp_path / "blocked",
            max_workers=1,
            allow_experiments=False,
        )
    with pytest.raises(ValueError, match="max_workers"):
        execution.execute_command_bundle(
            bundle,
            run_root=tmp_path / "workers",
            max_workers=0,
            allow_experiments=True,
        )
    with pytest.raises(ValueError, match="resume"):
        execution.execute_command_bundle(
            bundle,
            run_root=tmp_path / "missing",
            max_workers=1,
            allow_experiments=True,
            resume=True,
        )


def test_execution_can_defer_work_to_a_later_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(execution, "_git_state", lambda: (SOURCE, True))
    result = execution.execute_command_bundle(
        _bundle(_command("later", estimated_seconds=10.0)),
        run_root=tmp_path / "deferred",
        max_workers=1,
        allow_experiments=False,
        max_runtime_seconds=0.0,
    )
    assert result["status"] == "incomplete"
    assert result["commands"][0]["status"] == "pending"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"schema_version": 2}, "unsupported"),
        ({"source_commit": "short"}, "source commit"),
        ({"domain": ""}, "domain"),
        ({"experiment_id": ""}, "experiment_id"),
        ({"commands": []}, "requires commands"),
    ],
)
def test_bundle_validation_rejects_invalid_identity(
    change: dict[str, object],
    message: str,
) -> None:
    payload = execution.bundle_payload(_bundle(_command("source")))
    payload.update(change)
    with pytest.raises(ValueError, match=message):
        execution.bundle_from_payload(payload)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"id": ""}, "IDs"),
        ({"argv": []}, "argv"),
        ({"argv": ["sbatch"]}, "forbidden"),
        ({"depends_on": ["missing"]}, "dependencies"),
        ({"accepted_return_codes": [True]}, "integer list"),
        ({"variant_id": " "}, "variant_id"),
        ({"component": 1}, "component"),
        ({"estimated_seconds": "later"}, "numeric"),
        ({"resource_lock": 1}, "resource_lock"),
    ],
)
def test_bundle_validation_rejects_invalid_command(
    change: dict[str, object],
    message: str,
) -> None:
    payload = execution.bundle_payload(_bundle(_command("source")))
    payload["commands"][0].update(change)
    with pytest.raises(ValueError, match=message):
        execution.bundle_from_payload(payload)


def test_artifact_inventory_covers_files_directories_and_missing_paths(tmp_path: Path) -> None:
    artifact = tmp_path / "result.txt"
    artifact.write_text("complete", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    inventory = execution._artifact_hashes(
        (str(artifact), str(tmp_path), str(empty), str(tmp_path / "missing"))
    )
    assert inventory[str(artifact)]
    assert f"EMPTY::{empty}" in inventory
    assert f"MISSING::{tmp_path / 'missing'}" in inventory


def test_survival_bundle_builds_each_seed_and_fold_as_reusable_commands() -> None:
    exp = load_research_catalog().experiment("survival_policy")
    readiness = {"status": "pass", "scientific_training_authorized": True}
    bundle = build_qualification_bundle(
        exp,
        source_commit=SOURCE,
        readiness=readiness,
        output_root="outputs/research",
        selected_variants=("setup_conditioned",),
    )
    assert len(bundle.commands) == 37
    assert {item.variant_id for item in bundle.commands} == {"setup_conditioned"}
    assert {item.component for item in bundle.commands} == {"policy"}
    assert sum(bool(item.depends_on) for item in bundle.commands) == 31
    with pytest.raises(ValueError, match="authorized"):
        build_qualification_bundle(
            exp,
            source_commit=SOURCE,
            readiness={"status": "fail"},
            output_root="outputs/research",
            selected_variants=("setup_conditioned",),
        )
    with pytest.raises(ValueError, match="no variants"):
        build_qualification_bundle(
            exp,
            source_commit=SOURCE,
            readiness=readiness,
            output_root="outputs/research",
            selected_variants=("not_registered",),
        )


def test_qualified_checkpoint_requires_genuine_passing_evidence(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.zip"
    checkpoint.write_bytes(b"checkpoint")
    gate = tmp_path / "gate.json"
    gate.write_text(
        json.dumps({"status": "pass", "evidence": [{"seed": 42, "checkpoint": str(checkpoint)}]}),
        encoding="utf-8",
    )
    assert qualified_checkpoint_by_seed(gate) == {42: checkpoint}
    gate.write_text(json.dumps({"status": "fail", "evidence": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="not passing"):
        qualified_checkpoint_by_seed(gate)


def test_compute_budget_reflects_full_path_coverage_and_allocation_cost() -> None:
    def build(
        *,
        n_envs: list[int] | None = None,
        throughput: dict[int, float] | None = None,
        fold_decisions: list[int] | None = None,
    ) -> dict[str, Any]:
        return compute_budget.build_compute_budget(
            decisions_per_full_path=100,
            wf_decisions_per_full_path=([50] * 5 if fold_decisions is None else fold_decisions),
            n_envs_values=[2, 4] if n_envs is None else n_envs,
            rollout_steps_per_env=32,
            batch_size=64,
            epochs=2,
            supplied_total_timesteps=200,
            fps_by_n_envs={2: 100.0, 4: 80.0} if throughput is None else throughput,
        )

    budget = build()
    assert budget["schema_version"] == 1
    assert budget["recommended_n_envs"] == 2
    assert len(budget["rows"]) == 2
    assert len(budget["rows"][0]["walk_forward"]) == 5
    assert budget["rows"][0]["supplied_budget_is_semantically_sufficient"] is False
    assert budget["rows"][0]["estimated_main_plus_wf_wall_seconds"] > 0
    assert compute_budget._full_path_equivalents(200, n_envs=2, decisions_per_full_path=100) == 1
    assert compute_budget._round_up(101, 32) == 128
    with pytest.raises(ValueError, match="unique"):
        build(n_envs=[2, 2])
    with pytest.raises(ValueError, match="FPS"):
        build(throughput={2: -1.0})
    with pytest.raises(ValueError, match="one walk-forward"):
        build(fold_decisions=[50])
    with pytest.raises(ValueError, match="positive"):
        compute_budget._round_up(0, 32)


def test_paired_statistics_reject_non_finite_values_and_preserve_seed_pairs() -> None:
    diff = statistics.paired_differences([3.0, 4.0, 5.0], [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(diff, np.array([2.0, 2.0, 2.0]))
    assert statistics.exact_sign_flip_greater(diff) == pytest.approx(0.125)
    lo, hi = statistics.paired_bootstrap_interval(diff, samples=100, seed=3)
    assert lo == pytest.approx(2.0)
    assert hi == pytest.approx(2.0)
    result = statistics.analyze_paired_seeds([3.0] * 6, [1.0] * 6, bootstrap_samples=200)
    assert result.positive is True
    assert result.pair_count == 6
    with pytest.raises(ValueError, match="equal"):
        statistics.paired_differences([1], [1, 2])
    with pytest.raises(ValueError, match="finite"):
        statistics.paired_differences([np.nan], [1])
    with pytest.raises(ValueError, match="limit"):
        statistics.exact_sign_flip_greater(np.ones(16))
    with pytest.raises(ValueError, match="positive"):
        statistics.paired_bootstrap_interval(np.ones(2), samples=0)
    assert statistics.exact_sign_flip_greater(-np.ones(3)) == 1.0


def test_evidence_history_is_domain_indexed_and_rejects_path_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(history, "ROOT", tmp_path)
    (tmp_path / "research").mkdir()
    register = tmp_path / "history.yaml"
    register.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "entries": {
                    "audit": {
                        "domain": "data",
                        "path": "research",
                        "disposition": "superseded",
                        "summary": "Recorded market-data audit.",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    entries = history.load_history(register)
    assert len(entries) == 1
    rendered = history.render_markdown(entries)
    assert "Data" in rendered and "Recorded market-data audit." in rendered
    invalid = yaml.safe_load(register.read_text(encoding="utf-8"))
    invalid["entries"]["audit"]["path"] = "../outside"
    register.write_text(yaml.safe_dump(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes repository"):
        history.load_history(register)
    invalid["entries"]["audit"]["path"] = "absent"
    register.write_text(yaml.safe_dump(invalid), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        history.load_history(register)


def test_workflow_selects_supported_command_builders_and_freezes_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = load_research_catalog()
    monkeypatch.setattr(workflow, "current_source_commit", lambda: SOURCE)
    bundle = workflow.freeze_experiment(
        catalog,
        "feature_inputs",
        output_root=str(tmp_path),
        selected_variants=("observation_validity",),
    )
    assert len(bundle.commands) == 1
    assert bundle.commands[0].component == "observations"
    path = tmp_path / "bundle.json"
    workflow.write_bundle(bundle, path)
    assert workflow.load_bundle(path) == bundle
    with pytest.raises(ValueError, match="no variants"):
        workflow.freeze_experiment(
            catalog,
            "feature_inputs",
            output_root=str(tmp_path),
            selected_variants=("unknown",),
        )
    with pytest.raises(ValueError, match="requires a scientific readiness"):
        workflow.freeze_experiment(catalog, "survival_policy", output_root=str(tmp_path))
    with pytest.raises(ValueError, match="requires a survival qualification"):
        workflow.freeze_experiment(catalog, "checkpoint_repeatability", output_root=str(tmp_path))
    with pytest.raises(ValueError, match="requires finalist runs"):
        workflow.freeze_experiment(catalog, "account_robustness", output_root=str(tmp_path))
