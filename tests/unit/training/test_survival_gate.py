from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest
from omegaconf import OmegaConf

from configuration import load_config
from decisioning.observations import OBSERVATION_SCHEMA_V2, build_observation_schema
from decisioning.trade_setup import trade_setup_observation_schema
from evaluation.reporting.run_manifest import build_sequence_feature_schema, file_sha256
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from training.artifacts.manifests import build_effective_policy_input_schema
from training.artifacts.walk_forward import (
    build_walk_forward_identity,
    fold_identity_sha256,
)
from training.configuration.survival_gate import (
    _complete_breach_free_path,
    _has_full_split_cap_conflict,
    _survival_candidate_schema_error,
    _survival_policy_sequence_schema_error,
    _survival_timeframe_contract_error,
    build_survival_gate,
    survival_config_identity,
    validate_portfolio_data,
    validate_portfolio_gate,
)


def _survival_sequence_columns() -> list[str]:
    return [
        "reachable_r",
        "reachable_r_valid",
        *[column for _, column in trade_setup_candidate_feature_columns()],
    ]


@pytest.mark.parametrize(
    "record, expected",
    [
        (
            {"survived_full_year": True, "completed_data_split": True, "n_breach_sessions": 0},
            True,
        ),
        (
            {"survived_full_year": "false", "completed_data_split": True, "n_breach_sessions": 0},
            False,
        ),
        (
            {"survived_full_year": True, "completed_data_split": "false", "n_breach_sessions": 0},
            False,
        ),
        (
            {"survived_full_year": True, "completed_data_split": True, "n_breach_sessions": "0"},
            False,
        ),
        (
            {"survived_full_year": True, "completed_data_split": True, "n_breach_sessions": False},
            False,
        ),
        ({"survived_full_year": True, "completed_data_split": True}, False),
    ],
)
def test_survival_gate_requires_typed_breach_free_outcome(record, expected) -> None:
    assert _complete_breach_free_path(record, survival_key="survived_full_year") is expected


@pytest.mark.parametrize(
    "path, value",
    [
        ("training.max_days", 30),
        ("training.episode_mode", "risk_terminated"),
        ("env.max_episode_steps", 1000),
    ],
)
def test_survival_gate_rejects_capped_training_config(path: str, value: object) -> None:
    cfg = _cfg()
    OmegaConf.update(cfg, path, value)
    assert _has_full_split_cap_conflict(cfg)


@pytest.mark.parametrize(
    "path, value",
    [
        ("training.max_days", 30),
        ("training.episode_mode", "risk_terminated"),
        ("env.max_episode_steps", 1000),
    ],
)
def test_gate_builder_rejects_capped_training_config(path: str, value: object, tmp_path) -> None:
    cfg = _cfg()
    OmegaConf.update(cfg, path, value)
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
    )
    seeds = [42, 43, 44, 45, 46, 47]
    with pytest.raises(SystemExit, match="complete uncapped training split"):
        build_survival_gate(
            cfg=cfg,
            args=args,
            run_dir=tmp_path,
            seed_results=[],
            seeds=seeds,
        )
    gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
    assert gate["status"] == "fail"


def _cfg(*, reward_mode: str = "survival", gate: str | None = None):
    return OmegaConf.create(
        {
            "env": {
                "reward_mode": reward_mode,
                "risk_mode": "dynamic",
                "observation_schema_version": "account-state-v2",
                "feature_validity_channels": True,
                "reachable_r_validity_mask": True,
                "strict_research_eligibility": True,
            },
            "account": {"initial_balance": 100000.0},
            "data": {
                "timeframes": [
                    "M1",
                    "M3",
                    "M5",
                    "M10",
                    "M15",
                    "M30",
                    "H1",
                    "H4",
                    "D1",
                ]
            },
            "features": {
                "htf_timeframes": [
                    "M3",
                    "M5",
                    "M10",
                    "M15",
                    "M30",
                    "H1",
                    "H4",
                    "D1",
                ],
                "entry_ideas": {
                    "enabled": True,
                    "timeframes": [
                        "M1",
                        "M3",
                        "M5",
                        "M10",
                        "M15",
                        "M30",
                        "H1",
                        "H4",
                        "D1",
                    ],
                },
            },
            "risk": {
                "target_timeframes": [
                    "M3",
                    "M5",
                    "M10",
                    "M15",
                    "M30",
                    "H1",
                    "H4",
                    "D1",
                ]
            },
            "ftmo": {
                "limit_value_mode": "percent_equity",
                "max_drawdown_mode": "static",
                "risk_per_trade_limit": 1000.0,
                "risk_sizing_limit_usd": 900.0,
                "risk_per_trade_limit_pct": 0.01,
                "daily_loss_limit_pct": 0.05,
                "max_loss_limit_initial_pct": 0.10,
            },
            "training": {
                "survival_gate_manifest": gate,
                "episode_mode": "full_split",
                "max_days": None,
            },
            "ppo": {"total_timesteps": 1000, "gamma": 1.0, "gae_lambda": 1.0},
        }
    )


def test_config_identity_ignores_only_phase_specific_values() -> None:
    qualified = _cfg()
    portfolio = _cfg(reward_mode="dsr", gate="/tmp/survival.json")
    portfolio.ppo.total_timesteps = 2000
    assert survival_config_identity(qualified) == survival_config_identity(portfolio)
    portfolio.env.risk_mode = "fixed"
    assert survival_config_identity(qualified) != survival_config_identity(portfolio)


def test_survival_qualification_overlay_resolves_to_the_required_training_contract() -> None:
    cfg = load_config(config_path="config/research/survival_qualification.yaml")
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
        seed=42,
        seeds=[42, 43, 44, 45, 46, 47],
    )

    assert validate_portfolio_gate(cfg=cfg, args=args) is None


def test_portfolio_training_requires_a_survival_gate() -> None:
    with pytest.raises(SystemExit, match="blocked until"):
        validate_portfolio_gate(
            cfg=_cfg(reward_mode="dsr"),
            args=Namespace(algo="ppo", arch="tcn", strategy="baseline", seed=1, seeds=None),
        )


@pytest.mark.parametrize(
    "path, value",
    [
        ("ftmo.max_drawdown_mode", "intraday_trailing"),
        ("ftmo.daily_loss_limit_pct", 0.04),
        ("ftmo.max_loss_limit_initial_pct", 0.08),
        ("ftmo.risk_sizing_limit_usd", 1000.0),
        ("ftmo.risk_per_trade_limit_pct", 0.02),
    ],
)
def test_survival_training_rejects_noncanonical_account_contract(
    path: str, value: object, tmp_path: Path
) -> None:
    cfg = _cfg()
    OmegaConf.update(cfg, path, value)
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
        seed=42,
        seeds=[42, 43, 44, 45, 46, 47],
    )
    with pytest.raises(SystemExit, match="survival qualification account contract mismatch"):
        validate_portfolio_gate(cfg=cfg, args=args)
    with pytest.raises(SystemExit, match="SURVIVAL_PHASE_GATE_FAILED"):
        build_survival_gate(
            cfg=cfg,
            args=args,
            run_dir=tmp_path,
            seed_results=[],
            seeds=args.seeds,
        )
    gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
    assert any("survival qualification account contract mismatch" in x for x in gate["failures"])


@pytest.mark.parametrize(
    "path, value",
    [
        ("data.timeframes", ["M1", "M5", "M15", "H1"]),
        ("features.htf_timeframes", ["M5", "M15", "H1"]),
        ("features.entry_ideas.timeframes", ["M5", "M15", "H1"]),
        ("risk.target_timeframes", ["M5", "M15", "H1"]),
    ],
)
def test_survival_training_requires_the_full_timeframe_ladder(
    path: str, value: object, tmp_path: Path
) -> None:
    cfg = _cfg()
    OmegaConf.update(cfg, path, value)
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
        seed=42,
        seeds=[42, 43, 44, 45, 46, 47],
    )
    with pytest.raises(SystemExit, match="full configured timeframe ladder"):
        validate_portfolio_gate(cfg=cfg, args=args)
    with pytest.raises(SystemExit, match="SURVIVAL_PHASE_GATE_FAILED"):
        build_survival_gate(
            cfg=cfg,
            args=args,
            run_dir=tmp_path,
            seed_results=[],
            seeds=args.seeds,
        )
    gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
    assert any("full configured timeframe ladder" in x for x in gate["failures"])


@pytest.mark.parametrize(
    ("candidate_timeframes", "idea_timeframes"),
    [
        (["M1"], ["M1"]),
        (
            ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"],
            ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"],
        ),
    ],
)
def test_survival_timeframe_contract_allows_only_matched_a_or_bc_candidate_scope(
    candidate_timeframes: list[str], idea_timeframes: list[str]
) -> None:
    cfg = _cfg()
    cfg.env.trade_setup_candidate_timeframes = candidate_timeframes
    cfg.features.entry_ideas.timeframes = idea_timeframes

    assert _survival_timeframe_contract_error(cfg) is None


def test_survival_timeframe_contract_rejects_partial_or_unmatched_candidate_scope() -> None:
    cfg = _cfg()
    cfg.env.trade_setup_candidate_timeframes = ["M1", "M5"]
    cfg.features.entry_ideas.timeframes = ["M1", "M5"]
    error = _survival_timeframe_contract_error(cfg)
    assert error is not None
    assert "exactly M1 or the full timeframe menu" in error

    cfg.env.trade_setup_candidate_timeframes = ["M1"]
    cfg.features.entry_ideas.timeframes = ["M1", "M5"]
    error = _survival_timeframe_contract_error(cfg)
    assert error is not None
    assert "must match env.trade_setup_candidate_timeframes" in error

    for invalid_timeframes in (
        ["D1", "H4", "H1", "M30", "M15", "M10", "M5", "M3", "M1"],
        ["M1", "M1"],
        ["M1", "M2"],
    ):
        cfg.env.trade_setup_candidate_timeframes = invalid_timeframes
        cfg.features.entry_ideas.timeframes = invalid_timeframes
        error = _survival_timeframe_contract_error(cfg)
        assert error is not None
        assert "candidate_timeframes" in error

    cfg.env.trade_setup_candidate_timeframes = [
        "M1",
        "M3",
        "M5",
        "M10",
        "M15",
        "M30",
        "H1",
        "H4",
        "D1",
    ]
    cfg.features.entry_ideas.timeframes = ["D1", "H4", "H1", "M30", "M15", "M10", "M5", "M3", "M1"]
    error = _survival_timeframe_contract_error(cfg)
    assert error is not None
    assert "must match env.trade_setup_candidate_timeframes" in error


@pytest.mark.parametrize(
    ("candidate_timeframes", "history_enabled", "config_arch", "runtime_arch"),
    [
        (["M1"], True, "tcn", "tcn"),
        (
            ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"],
            False,
            "mtf_reasoning",
            "mtf_reasoning",
        ),
        (
            ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"],
            True,
            "mtf_reasoning",
            "mtf_reasoning",
        ),
        (
            ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"],
            False,
            "tcn",
            "mtf_reasoning",
        ),
    ],
)
def test_survival_candidate_mask_schema_matches_a_bc_scope_and_history(
    candidate_timeframes: list[str],
    history_enabled: bool,
    config_arch: str,
    runtime_arch: str,
) -> None:
    cfg = _cfg()
    cfg["agent"] = {"arch": config_arch}
    cfg.env.trade_setup_actions = True
    cfg.env.trade_setup_candidate_timeframes = candidate_timeframes
    cfg.env.completed_htf_history_enabled = history_enabled
    mtf_enabled = runtime_arch == "mtf_reasoning"
    effective_history_enabled = mtf_enabled and history_enabled
    sequence_columns = ["close", "M3_close", "reachable_r", "reachable_r_valid"]
    observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V2).to_dict()
    observation_schema["trade_setup_observation"] = trade_setup_observation_schema(
        candidate_timeframes, completed_htf_history_enabled=effective_history_enabled
    )
    observation_schema["effective_policy_input_schema"] = build_effective_policy_input_schema(
        sequence_columns,
        mtf=mtf_enabled,
        trade_setup_actions=True,
        completed_htf_history_enabled=effective_history_enabled,
        validity_channels=True,
    )

    assert (
        _survival_candidate_schema_error(cfg, observation_schema, sequence_columns, runtime_arch)
        is None
    )

    wrong_ids_schema = json.loads(json.dumps(observation_schema))
    wrong_ids_schema["trade_setup_observation"]["eligible_candidate_ids"].pop()
    error = _survival_candidate_schema_error(cfg, wrong_ids_schema, sequence_columns, runtime_arch)
    assert error is not None
    assert "candidate mask schema" in error

    wrong_stream_schema = json.loads(json.dumps(observation_schema))
    wrong_stream_schema["effective_policy_input_schema"]["streams"].pop()
    error = _survival_candidate_schema_error(
        cfg, wrong_stream_schema, sequence_columns, runtime_arch
    )
    assert error is not None
    assert "effective policy input schema" in error


def test_survival_policy_sequence_schema_separates_candidate_masks() -> None:
    cfg = _cfg()
    cfg.env.trade_setup_actions = True
    cfg.env.trade_setup_candidate_timeframes = ["M1"]
    columns = ["reachable_r", "reachable_r_valid"]

    assert _survival_policy_sequence_schema_error(cfg, columns) is None
    leaked_setup_column = [*columns, "entry_idea_po3_M1_long"]
    error = _survival_policy_sequence_schema_error(cfg, leaked_setup_column)
    assert error is not None
    assert "belong in candidate masks" in error

    cfg.env.trade_setup_actions = False
    cfg.env.trade_setup_candidate_timeframes = list(_cfg().features.entry_ideas.timeframes)
    columns.extend(column for _, column in trade_setup_candidate_feature_columns())
    assert _survival_policy_sequence_schema_error(cfg, columns) is None
    columns.remove("entry_idea_po3_M1_long")
    error = _survival_policy_sequence_schema_error(cfg, columns)
    assert error is not None
    assert "omits configured timeframe-specific setup eligibility" in error


def test_survival_training_requires_setup_eligibility_features_enabled(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg.features.entry_ideas.enabled = False
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
        seed=42,
        seeds=[42, 43, 44, 45, 46, 47],
    )

    with pytest.raises(SystemExit, match="entry_ideas.enabled=true"):
        validate_portfolio_gate(cfg=cfg, args=args)
    with pytest.raises(SystemExit, match="SURVIVAL_PHASE_GATE_FAILED"):
        build_survival_gate(
            cfg=cfg,
            args=args,
            run_dir=tmp_path,
            seed_results=[],
            seeds=args.seeds,
        )
    gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
    assert any("entry_ideas.enabled=true" in item for item in gate["failures"])


def test_survival_training_requires_explicit_ny_session_eligibility(tmp_path) -> None:
    cfg = _cfg()
    cfg.env.strict_research_eligibility = False
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
        seed=42,
        seeds=[42, 43, 44, 45, 46, 47],
    )
    with pytest.raises(SystemExit, match="strict_research_eligibility=true"):
        validate_portfolio_gate(cfg=cfg, args=args)
    with pytest.raises(SystemExit, match="SURVIVAL_PHASE_GATE_FAILED"):
        build_survival_gate(
            cfg=cfg,
            args=args,
            run_dir=tmp_path,
            seed_results=[],
            seeds=args.seeds,
        )
    gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
    assert any("strict_research_eligibility=true" in failure for failure in gate["failures"])

    portfolio_cfg = _cfg(reward_mode="dsr", gate="/tmp/not-read-before-eligibility.json")
    portfolio_cfg.env.strict_research_eligibility = False
    with pytest.raises(SystemExit, match="portfolio training requires"):
        validate_portfolio_gate(cfg=portfolio_cfg, args=args)


@pytest.mark.parametrize("reward_mode", ["survival", "dsr"])
def test_survival_phases_require_account_state_risk_budget_coordinates(
    reward_mode: str, tmp_path: Path
) -> None:
    cfg = _cfg(
        reward_mode=reward_mode,
        gate="/tmp/survival.json" if reward_mode == "dsr" else None,
    )
    cfg.env.observation_schema_version = "account-state-v1"
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
        seed=42,
        seeds=[42, 43, 44, 45, 46, 47],
    )

    with pytest.raises(SystemExit, match="remaining daily and maximum-loss budgets"):
        validate_portfolio_gate(cfg=cfg, args=args)

    if reward_mode == "survival":
        with pytest.raises(SystemExit, match="SURVIVAL_PHASE_GATE_FAILED"):
            build_survival_gate(
                cfg=cfg,
                args=args,
                run_dir=tmp_path,
                seed_results=[],
                seeds=args.seeds,
            )
        gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
        assert any(
            "remaining daily and maximum-loss budgets" in failure for failure in gate["failures"]
        )


@pytest.mark.parametrize(
    ("setting", "message"),
    [
        ("feature_validity_channels", "feature_validity_channels=true"),
        ("reachable_r_validity_mask", "reachable_r_validity_mask=true"),
    ],
)
def test_survival_phases_require_feature_validity_channels(setting: str, message: str) -> None:
    cfg = _cfg()
    cfg.env[setting] = False
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
        seed=42,
        seeds=[42, 43, 44, 45, 46, 47],
    )

    with pytest.raises(SystemExit, match=message):
        validate_portfolio_gate(cfg=cfg, args=args)


@pytest.mark.parametrize("setting", ["stop_on_no_trades", "stop_on_equity_gate"])
def test_survival_gate_rejects_activity_based_early_abort_settings(
    setting: str, tmp_path: Path
) -> None:
    cfg = _cfg()
    cfg.training.early_abort = {
        "enabled": True,
        "stop_on_nonfinite": True,
        "stop_on_no_trades": setting == "stop_on_no_trades",
        "stop_on_equity_gate": setting == "stop_on_equity_gate",
    }
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        mvp=False,
        allow_locked_oos_for_selection=False,
        seed=42,
        seeds=[42, 43, 44, 45, 46, 47],
    )
    with pytest.raises(SystemExit, match="cannot enable activity or equity-gate"):
        validate_portfolio_gate(cfg=cfg, args=args)
    with pytest.raises(SystemExit, match="SURVIVAL_PHASE_GATE_FAILED"):
        build_survival_gate(
            cfg=cfg,
            args=args,
            run_dir=tmp_path,
            seed_results=[],
            seeds=args.seeds,
        )
    gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
    assert any("cannot enable activity or equity-gate" in item for item in gate["failures"])


def test_survival_gate_writes_failure_evidence_for_insufficient_seeds(tmp_path) -> None:
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
    )
    with pytest.raises(SystemExit, match="SURVIVAL_PHASE_GATE_FAILED"):
        build_survival_gate(
            cfg=_cfg(),
            args=args,
            run_dir=tmp_path,
            seed_results=[],
            seeds=[1, 2, 3, 4, 5],
        )
    gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
    assert gate["status"] == "fail"
    assert gate["minimum_seed_count"] == 6
    assert gate["failures"]


def test_forced_survival_failure_cannot_be_overridden_by_existing_evidence(tmp_path) -> None:
    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
    )
    with pytest.raises(SystemExit, match="SURVIVAL_PHASE_GATE_FAILED"):
        build_survival_gate(
            cfg=_cfg(),
            args=args,
            run_dir=tmp_path,
            seed_results=[],
            seeds=[1, 2, 3, 4, 5, 6],
            forced_failures=["survival training finalization failed: known failure"],
        )
    gate = json.loads((tmp_path / "survival_phase_gate.json").read_text())
    assert gate["status"] == "fail"
    assert "survival training finalization failed: known failure" in gate["failures"]


def test_passing_survival_gate_revalidates_seed_evidence_and_portfolio_data(
    monkeypatch, tmp_path
) -> None:
    from training.configuration import survival_gate

    seeds = [42, 43, 44, 45, 46, 47]
    source = {"available": True, "head": "abc123", "dirty_files": []}
    dataset_records = {"train_bars": {"rows": 10, "sha256": "a" * 64}}
    survival_cfg = _cfg()
    seed_results = [{"seed": seed} for seed in seeds]
    for seed in seeds:
        seed_dir = tmp_path / "qualification" / "seeds" / f"seed{seed}"
        seed_dir.mkdir(parents=True)
        checkpoint = seed_dir / "model.zip"
        checkpoint.write_bytes(f"checkpoint-{seed}".encode())
        config_path = seed_dir / "config.yaml"
        OmegaConf.save(survival_cfg, config_path)
        sequence_columns = _survival_sequence_columns()
        observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V2).to_dict()
        observation_schema["effective_policy_input_schema"] = build_effective_policy_input_schema(
            sequence_columns,
            mtf=False,
            trade_setup_actions=False,
            completed_htf_history_enabled=False,
            validity_channels=True,
        )
        manifest = {
            "seed": seed,
            "artifact_paths": {"checkpoint": "model.zip"},
            "checkpoint": {"path": str(checkpoint), "sha256": file_sha256(checkpoint)},
            "config": {"path": str(config_path), "sha256": file_sha256(config_path)},
            "training_protocol": {
                "training_phase": "survival_qualification",
                "mvp_mode": False,
                "locked_oos_selection_allowed": False,
                "algorithm": "ppo",
                "seed": seed,
                "reward": {"mode": "survival", "selector": "dsr"},
                "walk_forward": {"enabled": True, "folds": 5},
                "constrained_rl": {"enabled": False},
            },
            "training_architecture": {"algorithm": "ppo", "arch": "tcn"},
            "stop_candidate_schema": {"strategy_name": "baseline"},
            "datasets": dataset_records,
            "feature_cache": {"sha256": "feature-hash"},
            "source": source,
            "action_schema": {"schema": "action-v1"},
            "observation_schema": observation_schema,
            "sequence_feature_schema": build_sequence_feature_schema(
                sequence_columns, include_validity_channels=True
            ),
        }
        (seed_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (seed_dir / "train_equity_gate.json").write_text(
            json.dumps({"ok": False, "hard_risk_ok": True, "breached": False}),
            encoding="utf-8",
        )
        (seed_dir / "train_path_outcome.json").write_text(
            json.dumps(
                {
                    "survived_full_split": True,
                    "completed_data_split": True,
                    "n_breach_sessions": 0,
                }
            ),
            encoding="utf-8",
        )
        manifest_path = seed_dir / "run_manifest.json"
        wf_identity = build_walk_forward_identity(
            run_manifest_path=manifest_path,
            seed=seed,
            wf_splits=5,
            purge_bars=60,
            embargo_bars=20,
            wf_steps=1000,
        )
        folds = []
        for fold_id in range(5):
            split_sha256 = f"{fold_id + 1:064x}"
            folds.append(
                {
                    "fold": fold_id,
                    "split_sha256": split_sha256,
                    "fold_identity_sha256": fold_identity_sha256(
                        wf_identity, fold_id, split_sha256
                    ),
                    "completed_data_split": True,
                    "survived_full_year": True,
                    "n_breach_sessions": 0,
                }
            )
        (seed_dir / "walk_forward.json").write_text(
            json.dumps(
                {
                    "schema_version": "walk-forward-progress-v1",
                    "identity": wf_identity,
                    "status": "complete",
                    "folds": folds,
                }
            ),
            encoding="utf-8",
        )

    args = Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        walk_forward=True,
        wf_splits=5,
        seed=42,
        seeds=None,
        resume_checkpoint=str(tmp_path / "qualification/seeds/seed42/model.zip"),
        allow_locked_oos_for_selection=False,
    )
    args.allow_locked_oos_for_selection = True
    with pytest.raises(SystemExit, match="exposed report-period data"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    args.allow_locked_oos_for_selection = False
    args.mvp = True
    with pytest.raises(SystemExit, match="capped MVP"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    args.mvp = False
    mismatched_manifest_path = tmp_path / "qualification/seeds/seed47/run_manifest.json"
    valid_manifest = mismatched_manifest_path.read_text(encoding="utf-8")
    old_observation_manifest = json.loads(valid_manifest)
    old_observation_manifest["observation_schema"] = build_observation_schema(
        "account-state-v1"
    ).to_dict()
    mismatched_manifest_path.write_text(json.dumps(old_observation_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="survival risk-budget coordinates"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    unexpected_mask_manifest = json.loads(valid_manifest)
    unexpected_mask_manifest["observation_schema"]["trade_setup_observation"] = (
        trade_setup_observation_schema()
    )
    mismatched_manifest_path.write_text(json.dumps(unexpected_mask_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="candidate mask schema"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    values_only_manifest = json.loads(valid_manifest)
    values_only_manifest["sequence_feature_schema"] = build_sequence_feature_schema(
        _survival_sequence_columns()
    )
    mismatched_manifest_path.write_text(json.dumps(values_only_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="does not include valid missingness channels"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    missing_reachability_manifest = json.loads(valid_manifest)
    missing_reachability_manifest["sequence_feature_schema"] = build_sequence_feature_schema(
        ["feature_1"], include_validity_channels=True
    )
    mismatched_manifest_path.write_text(json.dumps(missing_reachability_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="omits reachable_r_valid"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    missing_setup_manifest = json.loads(valid_manifest)
    missing_setup_columns = [
        column for column in _survival_sequence_columns() if column != "entry_idea_po3_M1_long"
    ]
    missing_setup_manifest["observation_schema"]["effective_policy_input_schema"] = (
        build_effective_policy_input_schema(
            missing_setup_columns,
            mtf=False,
            trade_setup_actions=False,
            completed_htf_history_enabled=False,
            validity_channels=True,
        )
    )
    missing_setup_manifest["sequence_feature_schema"] = build_sequence_feature_schema(
        missing_setup_columns,
        include_validity_channels=True,
    )
    mismatched_manifest_path.write_text(json.dumps(missing_setup_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="timeframe-specific setup eligibility features"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    incomplete_observation_manifest = json.loads(valid_manifest)
    incomplete_observation_manifest["observation_schema"]["observation_coordinates"].pop()
    mismatched_manifest_path.write_text(
        json.dumps(incomplete_observation_manifest), encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="survival risk-budget coordinates"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    mismatched_manifest = json.loads(valid_manifest)
    mismatched_manifest["training_protocol"]["reward"]["mode"] = "pnl"
    mismatched_manifest_path.write_text(json.dumps(mismatched_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="training protocol reward"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    changed_config_path = tmp_path / "qualification/seeds/seed47/config.yaml"
    valid_config = changed_config_path.read_bytes()
    changed_cfg = _cfg()
    changed_cfg.env.risk_mode = "fixed"
    OmegaConf.save(changed_cfg, changed_config_path)
    with pytest.raises(SystemExit, match="configuration snapshot checksum"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest = json.loads(valid_manifest)
    mismatched_manifest["config"]["sha256"] = file_sha256(changed_config_path)
    mismatched_manifest_path.write_text(json.dumps(mismatched_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="differs from the survival gate request"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    changed_config_path.write_bytes(valid_config)
    non_survival_cfg = _cfg(reward_mode="dsr")
    OmegaConf.save(non_survival_cfg, changed_config_path)
    non_survival_manifest = json.loads(valid_manifest)
    non_survival_manifest["config"]["sha256"] = file_sha256(changed_config_path)
    mismatched_manifest_path.write_text(json.dumps(non_survival_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="snapshot did not train with survival reward"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    changed_config_path.write_bytes(valid_config)
    disabled_setup_cfg = _cfg()
    disabled_setup_cfg.features.entry_ideas.enabled = False
    OmegaConf.save(disabled_setup_cfg, changed_config_path)
    disabled_setup_manifest = json.loads(valid_manifest)
    disabled_setup_manifest["config"]["sha256"] = file_sha256(changed_config_path)
    mismatched_manifest_path.write_text(json.dumps(disabled_setup_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="entry_ideas.enabled=true"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    changed_config_path.write_bytes(valid_config)
    capped_cfg = _cfg()
    capped_cfg.training.max_days = 30
    OmegaConf.save(capped_cfg, changed_config_path)
    capped_manifest = json.loads(valid_manifest)
    capped_manifest["config"]["sha256"] = file_sha256(changed_config_path)
    mismatched_manifest_path.write_text(json.dumps(capped_manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="capped the training split"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    mismatched_manifest_path.write_text(valid_manifest, encoding="utf-8")
    changed_config_path.write_bytes(valid_config)
    with pytest.raises(SystemExit, match="duplicate seeds"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results + [seed_results[0]],
            seeds=seeds,
        )
    gate_path = build_survival_gate(
        cfg=survival_cfg,
        args=args,
        run_dir=tmp_path / "qualification",
        seed_results=seed_results,
        seeds=seeds,
    )
    monkeypatch.setattr(survival_gate, "source_state", lambda _root: source)
    portfolio_cfg = _cfg(reward_mode="dsr", gate=str(gate_path))
    gate = validate_portfolio_gate(cfg=portfolio_cfg, args=args)
    assert gate is not None and gate["status"] == "pass"
    args.seeds = [42, 43]
    with pytest.raises(SystemExit, match="exactly one seed"):
        validate_portfolio_gate(cfg=portfolio_cfg, args=args)
    args.seeds = None

    cache = tmp_path / "features.parquet"
    Path(f"{cache}.hash").write_text("feature-hash", encoding="utf-8")
    validate_portfolio_data(gate=gate, dataset_records=dataset_records, feat_cache=cache)

    passing_gate_manifest = gate_path.read_bytes()
    duplicated_gate = json.loads(passing_gate_manifest)
    duplicated_gate["evidence"].append(duplicated_gate["evidence"][0])
    gate_path.write_text(json.dumps(duplicated_gate), encoding="utf-8")
    with pytest.raises(SystemExit, match="evidence contains duplicates"):
        validate_portfolio_gate(cfg=portfolio_cfg, args=args)
    gate_path.write_bytes(passing_gate_manifest)

    changed_train_gate = tmp_path / "qualification/seeds/seed47/train_equity_gate.json"
    passing_train_gate = changed_train_gate.read_bytes()
    changed_train_gate.write_text(
        json.dumps({"ok": False, "hard_risk_ok": False, "breached": True}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="train_gate checksum"):
        validate_portfolio_gate(cfg=portfolio_cfg, args=args)
    with pytest.raises(SystemExit, match="hard-risk failure"):
        build_survival_gate(
            cfg=survival_cfg,
            args=args,
            run_dir=tmp_path / "qualification",
            seed_results=seed_results,
            seeds=seeds,
        )
    changed_train_gate.write_bytes(passing_train_gate)
    gate_path.write_bytes(passing_gate_manifest)
    checkpoint = Path(args.resume_checkpoint)
    checkpoint.write_bytes(b"changed")
    with pytest.raises(SystemExit, match="checksum"):
        validate_portfolio_gate(cfg=portfolio_cfg, args=args)
