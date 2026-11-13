"""Research readiness, replay, and evidence packaging contract tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from artifacts.identity import file_sha256
from experiments.research import (
    exposure,
    portfolio,
    primary_comparison,
    readiness,
    release,
    repeatability,
    robustness,
    static_contract,
)
from experiments.research.catalog import load_research_catalog

SOURCE = "a" * 40
SEEDS = (42, 43, 44, 45, 46, 47)


def _json(path: Path, value: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _qualified_evidence(tmp_path: Path) -> tuple[Path, dict[int, Path]]:
    rows: list[dict[str, object]] = []
    runs: dict[int, Path] = {}
    for seed in SEEDS:
        root = tmp_path / f"seed{seed}"
        source = _json(root / "run_manifest.json", {"completed_steps": 1500})
        model = root / "checkpoint.zip"
        model.write_bytes(f"model-{seed}".encode())
        rows.append(
            {
                "seed": seed,
                "run_manifest": str(source),
                "run_manifest_sha256": file_sha256(source),
                "checkpoint": str(model),
                "checkpoint_sha256": file_sha256(model),
            }
        )
        runs[seed] = root
    gate = _json(
        tmp_path / "qualification.json", {"schema_version": 1, "status": "pass", "evidence": rows}
    )
    return gate, runs


def test_qualified_continuation_has_independent_control_and_treatment(tmp_path: Path) -> None:
    gate, _ = _qualified_evidence(tmp_path)
    catalog = load_research_catalog()
    experiment = catalog.experiment("portfolio_value")
    bundle = portfolio.build_portfolio_bundle(
        experiment,
        source_commit=SOURCE,
        gate_path=gate,
        canonical_config="config/research/survival_trade_setup_mtf_conditioned.yaml",
        output_root=str(tmp_path / "output"),
    )
    assert len(bundle.commands) == 12
    assert {x.variant_id for x in bundle.commands} == {"qualified_policy", "always_no_trade"}
    assert all(x.component == "portfolio" for x in bundle.commands)
    assert "ppo.total_timesteps=2001500" in bundle.commands[0].argv
    control = portfolio.build_portfolio_bundle(
        experiment,
        source_commit=SOURCE,
        gate_path=gate,
        canonical_config="config/research/survival_trade_setup_mtf_conditioned.yaml",
        output_root=str(tmp_path / "only_control"),
        selected_variants=("always_no_trade",),
    )
    assert len(control.commands) == 6
    assert all(c.variant_id == "always_no_trade" for c in control.commands)
    with pytest.raises(ValueError, match="no variants"):
        portfolio.build_portfolio_bundle(
            experiment,
            source_commit=SOURCE,
            gate_path=gate,
            canonical_config="x",
            output_root=str(tmp_path),
            selected_variants=("unknown",),
        )
    with pytest.raises(ValueError, match="not checkpoint continuation"):
        portfolio.build_portfolio_bundle(
            catalog.experiment("feature_inputs"),
            source_commit=SOURCE,
            gate_path=gate,
            canonical_config="x",
            output_root=str(tmp_path),
        )


def test_portfolio_safety_requires_all_seeds_without_breaches(tmp_path: Path) -> None:
    _, runs = _qualified_evidence(tmp_path)
    for run in runs.values():
        _json(run / "train_equity_gate.json", {"hard_risk_ok": True, "breached": False})
        _json(
            run / "train_path_outcome.json",
            {
                "survived_full_split": True,
                "completed_data_split": True,
                "n_breach_sessions": 0,
            },
        )
    safe = portfolio.summarize_portfolio_safety(runs)
    assert safe["status"] == "pass"
    assert len(safe["records"]) == 6
    _json(runs[42] / "train_equity_gate.json", {"hard_risk_ok": False, "breached": True})
    assert portfolio.summarize_portfolio_safety(runs)["failures"] == ["seed42"]
    with pytest.raises(ValueError, match="seeds"):
        portfolio.summarize_portfolio_safety({42: runs[42]})
    with pytest.raises(ValueError, match="exactly one"):
        portfolio.find_completed_run(tmp_path / "absent")


def test_repeatability_bundle_checks_checkpoint_hashes_and_summarizes_ledgers(
    tmp_path: Path,
) -> None:
    gate, runs = _qualified_evidence(tmp_path)
    experiment = load_research_catalog().experiment("checkpoint_repeatability")
    bundle = repeatability.build_repeatability_bundle(
        experiment,
        source_commit=SOURCE,
        gate_path=gate,
        output_root=str(tmp_path / "replay"),
    )
    assert len(bundle.commands) == 18
    assert all(c.variant_id == "deterministic_replay" for c in bundle.commands)
    assert all(c.component == "validation" for c in bundle.commands)
    commands = []
    for seed in SEEDS:
        artifact = _json(tmp_path / f"evidence{seed}" / "repeatability.json", {"status": "passed"})
        commands.append(
            {
                "command_id": f"seed{seed}.compare",
                "status": "passed",
                "artifact_sha256": {str(artifact): file_sha256(artifact)},
            }
        )
    manifest = _json(tmp_path / "replays.json", {"commands": commands})
    assert repeatability.summarize_repeatability(manifest)["status"] == "pass"
    commands[0]["status"] = "failed"
    _json(manifest, {"commands": commands})
    assert repeatability.summarize_repeatability(manifest)["failures"] == ["seed42.compare"]
    (runs[42] / "checkpoint.zip").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checkpoint changed"):
        repeatability.build_repeatability_bundle(
            experiment,
            source_commit=SOURCE,
            gate_path=gate,
            output_root=str(tmp_path),
        )


def test_registered_robustness_variants_use_one_replay_builder(tmp_path: Path) -> None:
    _, runs = _qualified_evidence(tmp_path)
    catalog = load_research_catalog()
    account = catalog.experiment("account_robustness")
    bundle = robustness.build_robustness_bundle(
        account,
        source_commit=SOURCE,
        finalist_runs=runs,
        output_root=str(tmp_path / "replay"),
    )
    assert len(bundle.commands) == len(SEEDS) * len(account.variants)
    assert all(c.component == "robustness" for c in bundle.commands)
    assert {c.variant_id for c in bundle.commands} == {
        variant.variant_id for variant in account.variants
    }
    with pytest.raises(ValueError, match="no variants"):
        robustness.build_robustness_bundle(
            account,
            source_commit=SOURCE,
            finalist_runs=runs,
            output_root=str(tmp_path),
            selected_variants=("unknown",),
        )
    with pytest.raises(ValueError, match="seed set"):
        robustness.build_robustness_bundle(
            account,
            source_commit=SOURCE,
            finalist_runs={42: runs[42]},
            output_root=str(tmp_path),
        )
    variant = replace(account.variants[0], overrides=("unknown_key=value",))
    invalid = replace(account, variants=(variant,))
    with pytest.raises(ValueError, match="unsupported robustness override"):
        robustness.build_robustness_bundle(
            invalid,
            source_commit=SOURCE,
            finalist_runs=runs,
            output_root=str(tmp_path),
        )


def test_robustness_summary_refuses_unfinished_or_breached_replays(tmp_path: Path) -> None:
    screen = _json(
        tmp_path / "train_only_screen.json",
        {
            "training_split": {
                "completed_data_split": True,
                "survived_full_period": True,
                "fail_time": None,
            }
        },
    )
    manifest = _json(
        tmp_path / "robustness.json",
        {
            "experiment_id": "account_robustness",
            "commands": [
                {
                    "command_id": "static.seed42",
                    "status": "passed",
                    "artifact_sha256": {str(screen): file_sha256(screen)},
                }
            ],
        },
    )
    assert robustness.summarize_robustness([manifest])["status"] == "pass"
    _json(screen, {"training_split": {"completed_data_split": False}})
    assert robustness.summarize_robustness([manifest])["status"] == "fail"
    _json(manifest, {"experiment_id": "something_else", "commands": []})
    with pytest.raises(ValueError, match="unexpected robustness"):
        robustness.summarize_robustness([manifest])


def test_exposed_period_is_not_reopened_after_authorization(tmp_path: Path, monkeypatch) -> None:
    record = _json(tmp_path / "robustness.json", {"status": "pass"})
    marker = tmp_path / "opened.json"
    monkeypatch.setattr(
        "experiments.research.exposure.subprocess.check_output", lambda *a, **k: SOURCE
    )
    result = exposure.open_exposed_report(marker, record)
    assert result["selection_allowed"] is False
    assert result["source_commit"] == SOURCE
    with pytest.raises(FileExistsError, match="already opened"):
        exposure.open_exposed_report(marker, record)
    _json(record, {"status": "fail"})
    with pytest.raises(ValueError, match="passing robustness"):
        exposure.open_exposed_report(tmp_path / "new.json", record)


def test_release_copies_source_bound_evidence_and_prohibits_overwrites(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(release, "_git_state", lambda: (SOURCE, True))
    results = _json(
        tmp_path / "results.json",
        {
            "schema_version": 1,
            "domains": ["data"],
            "experiments": ["data_integrity"],
        },
    )
    protocol = tmp_path / "protocol.yaml"
    protocol.write_text("schema_version: 1\n", encoding="utf-8")
    catalog = tmp_path / "experiments.yaml"
    catalog.write_text("schema_version: 1\n", encoding="utf-8")
    packet = release.assemble_release(
        consolidated_results=results,
        protocol=protocol,
        catalog=catalog,
        output_dir=tmp_path / "release",
    )
    assert packet["source_commit"] == SOURCE
    assert len(packet["artifacts"]) == 3
    assert all((tmp_path / "release" / x["path"]).is_file() for x in packet["artifacts"])
    with pytest.raises(FileExistsError):
        release.assemble_release(
            consolidated_results=results,
            protocol=protocol,
            catalog=catalog,
            output_dir=tmp_path / "release",
        )
    monkeypatch.setattr(release, "_git_state", lambda: (SOURCE, False))
    with pytest.raises(ValueError, match="clean"):
        release.assemble_release(
            consolidated_results=results,
            protocol=protocol,
            catalog=catalog,
            output_dir=tmp_path / "other",
        )


def test_scientific_readiness_requires_all_source_bound_reviews(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(readiness, "_source_state", lambda: (SOURCE, True))
    evidence = tmp_path / "evidence.json"
    _json(evidence, {"audit": "complete"})
    review = readiness.record_review(
        review_id="research_review",
        status="pass",
        reviewed_by="reviewer",
        note="Verified causal source boundary",
        evidence=[evidence],
        output=tmp_path / "review.json",
    )
    assert review["source_commit"] == SOURCE
    contract = {
        "required_experiments": ["data_integrity"],
        "common_reviews": ["research_review"],
        "price_reviews": [],
    }
    execution = {
        "schema_version": 1,
        "source_commit": SOURCE,
        "experiment_id": "data_integrity",
        "status": "passed",
        "commands": [{"command_id": "denominator_register", "status": "passed"}],
    }
    result = readiness.build_readiness(
        contract=contract,
        execution_manifests={"data_integrity": execution},
        reviews={"research_review": review},
    )
    assert result["status"] == "pass"
    assert result["scientific_training_authorized"] is True
    assert result["price_training_authorized"] is True
    missing = readiness.build_readiness(
        contract=contract,
        execution_manifests={},
        reviews={},
    )
    assert missing["status"] == "fail"
    assert missing["errors"]
    evidence.write_text("tampered", encoding="utf-8")
    assert readiness._review_errors(
        review,
        review_id="research_review",
        source_commit=SOURCE,
    ) == [f"review evidence changed: {evidence}"]
    with pytest.raises(ValueError, match="non-empty"):
        readiness.record_review(
            review_id="",
            status="pass",
            reviewed_by="reviewer",
            note="ok",
            evidence=[evidence],
            output=tmp_path / "bad.json",
        )


def test_readiness_contract_validates_unique_sections(tmp_path: Path) -> None:
    contract = readiness.load_readiness_contract()
    assert contract["schema_version"] == 1
    bad = {**contract, "common_reviews": ["same", "same"]}
    path = tmp_path / "readiness.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        readiness.load_readiness_contract(path)
    bad = {**contract, "common_reviews": ["same"], "price_reviews": ["same"]}
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="disjoint"):
        readiness.load_readiness_contract(path)


def _comparison_arm(
    seed: int,
    *,
    control: bool,
    source: Path,
) -> dict[str, object]:
    from evaluation.metrics.matched_comparison import MATCH_FIELDS

    provenance: dict[str, object] = {
        field: seed if field == "seed" else "matched-evidence" for field in MATCH_FIELDS
    }
    provenance["policy_sha256"] = ("a" if control else "b") * 64
    return {
        "provenance": provenance,
        "policy_id": "always_no_trade_v1" if control else "qualified_policy",
        "evaluation_complete": True,
        "hard_risk_gate_passed": True,
        "initial_operating_equity": 100000.0,
        "ending_retained_equity": 100000.0 if control else 101000.0,
        "cumulative_payouts": 0.0,
        "trade_count": 0 if control else 1,
        "net_return_initial_equity_pct": 0.0 if control else 1.0,
        "source_artifacts": [{"path": str(source), "sha256": file_sha256(source)}],
    }


def test_matched_comparison_reconciles_economic_return_and_causal_provenance(
    tmp_path: Path,
) -> None:
    artifact = _json(tmp_path / "reference.json", {"status": "complete"})
    pairs = [
        {
            "seed": seed,
            "control": _comparison_arm(seed, control=True, source=artifact),
            "treatment": _comparison_arm(seed, control=False, source=artifact),
        }
        for seed in SEEDS
    ]
    source = {
        "schema_version": 1,
        "evaluation_exposure": "development",
        "expected_seeds": list(SEEDS),
        "pairs": pairs,
    }
    payload = primary_comparison.build_primary_payload(source)
    result = primary_comparison.analyze_primary_payload(payload)
    assert result["pair_count"] == 6
    assert result["positive_primary_result"] is True
    assert result["status"] == "positive"
    assert primary_comparison._finite(1, "test") == 1.0
    with pytest.raises(ValueError, match="finite"):
        primary_comparison._finite(float("nan"), "test")
    with pytest.raises(ValueError, match="numeric"):
        primary_comparison._finite(True, "test")
    with pytest.raises(ValueError, match="development"):
        primary_comparison.build_primary_payload({**source, "evaluation_exposure": "test"})
    invalid = {**source, "pairs": pairs[:-1]}
    with pytest.raises(ValueError, match="six pairs"):
        primary_comparison.build_primary_payload(invalid)
    control = pairs[0]["control"]
    assert isinstance(control, dict)
    control["net_return_initial_equity_pct"] = 5.0
    with pytest.raises(ValueError, match="does not reconcile"):
        primary_comparison.build_primary_payload(source)


def test_static_survival_checks_express_exact_configuration_contract() -> None:
    from decisioning.trade_setup import TRADE_SETUP_TIMEFRAMES

    cfg = {
        "account": {"initial_balance": 100000.0},
        "evaluation": {"development_only": True},
        "env": {
            "reward_mode": "survival",
            "observation_schema_version": "account-state-v2",
            "feature_validity_channels": True,
            "reachable_r_validity_mask": True,
            "strict_research_eligibility": True,
            "max_episode_steps": None,
            "n_envs": 8,
            "strategy_actions": True,
            "trade_setup_actions": True,
            "trade_setup_candidate_timeframes": list(TRADE_SETUP_TIMEFRAMES),
        },
        "ftmo": {
            "max_drawdown_mode": "static",
            "daily_loss_limit_pct": 0.05,
            "max_loss_limit_initial_pct": 0.10,
            "risk_sizing_limit_usd": 900.0,
        },
        "ppo": {"gamma": 1.0, "gae_lambda": 1.0, "policy_distribution": "control"},
        "features": {"entry_ideas": {"timeframes": list(TRADE_SETUP_TIMEFRAMES)}},
        "training": {"episode_mode": "full_split", "max_days": None},
    }
    assert static_contract._survival_errors(cfg) == []
    assert static_contract._without_policy_intervention(cfg)["ppo"] == {
        "gamma": 1.0,
        "gae_lambda": 1.0,
    }
    environment = cfg["env"]
    account_rules = cfg["ftmo"]
    assert isinstance(environment, dict)
    assert isinstance(account_rules, dict)
    environment["strict_research_eligibility"] = False
    account_rules["risk_sizing_limit_usd"] = 950.0
    failures = static_contract._survival_errors(cfg)
    assert "strict research eligibility" in failures
    assert "$900 sizing ceiling" in failures
