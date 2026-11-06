"""Evaluation must preserve input runs and reproduce training fit scope."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from omegaconf import OmegaConf

from decisioning.actions import build_action_schema_from_config
from decisioning.trade_setup import build_trade_setup_action_schema
from evaluation.reanalysis import checkpoint_reanalysis as eval_run
from evaluation.reanalysis import provenance as reanalysis_provenance
from evaluation.reanalysis.datasets import _load_train_only_feature_snapshot
from evaluation.reanalysis.provenance import (
    _evaluation_dataset_records,
    _feature_build_scope,
    _load_exact_source_feature_cache,
    _load_run_config,
    _reanalysis_backend_disposition,
    _validate_reanalysis_datasets,
    _validate_reanalysis_feature_cache,
    _validate_reanalysis_request,
)
from evaluation.reanalysis.validation import (
    resolve_recorded_sequence_schema,
    validate_train_only_feature_snapshot_request,
)
from evaluation.reporting.run_manifest import build_sequence_feature_schema, file_sha256
from features import feature_cache_path


def test_checkpoint_reanalysis_schema_includes_policy_selected_entry_execution() -> None:
    env_config = OmegaConf.create(
        {
            "trade_setup_actions": True,
            "agent_entry_execution": True,
            "allow_agent_sl_mode": True,
            "allow_agent_tp_mode": True,
            "allow_multi_tp": False,
        }
    )

    assert build_action_schema_from_config(env_config) == (
        build_trade_setup_action_schema(
            has_sl_mode=True,
            has_tp_mode=True,
            has_multi_tp=False,
            has_entry_execution=True,
        )
    )


def test_checkpoint_reanalysis_defaults_to_source_action_mode() -> None:
    default_args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out"]
    )
    sampled_args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out", "--stochastic", "--seed", "42"]
    )
    deterministic_args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out", "--deterministic"]
    )
    assert default_args.stochastic is None
    assert sampled_args.stochastic is True
    assert deterministic_args.stochastic is False
    assert sampled_args.seed == 42


def test_checkpoint_reanalysis_parses_recorded_sequence_schema_opt_in() -> None:
    args = eval_run.build_reanalysis_parser().parse_args(
        [
            "--run",
            "source",
            "--output",
            "out",
            "--use-recorded-sequence-schema",
            "--train-only-screen",
            "--train-only-feature-snapshot",
            "train.parquet",
        ]
    )
    assert args.use_recorded_sequence_schema is True


def test_checkpoint_reanalysis_parses_current_stop_menu_diagnostic() -> None:
    args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out", "--use-current-stop-menu"]
    )

    assert args.use_current_stop_menu is True


def test_recorded_sequence_schema_requires_snapshot_and_rebuilds_exact_order() -> None:
    columns = ["last_swing_high", "volume_spike", "reachable_r"]
    schema = build_sequence_feature_schema(columns)
    rebuilt, resolved = resolve_recorded_sequence_schema(
        schema,
        available_columns={"last_swing_high", "volume_spike"},
        generated_columns={"reachable_r"},
        train_only_screen=True,
        has_train_only_feature_snapshot=True,
        mtf_enabled=False,
        feature_validity_channels=False,
    )
    assert rebuilt == schema
    assert resolved == tuple(columns)

    with pytest.raises(ValueError, match="requires --train-only-feature-snapshot"):
        resolve_recorded_sequence_schema(
            schema,
            available_columns={"last_swing_high", "volume_spike"},
            generated_columns={"reachable_r"},
            train_only_screen=True,
            has_train_only_feature_snapshot=False,
            mtf_enabled=False,
            feature_validity_channels=False,
        )
    with pytest.raises(ValueError, match="absent from the training feature frame"):
        resolve_recorded_sequence_schema(
            schema,
            available_columns={"volume_spike"},
            generated_columns={"reachable_r"},
            train_only_screen=True,
            has_train_only_feature_snapshot=True,
            mtf_enabled=False,
            feature_validity_channels=False,
        )
    with pytest.raises(ValueError, match="does not support MTF"):
        resolve_recorded_sequence_schema(
            schema,
            available_columns={"last_swing_high", "volume_spike"},
            generated_columns={"reachable_r"},
            train_only_screen=True,
            has_train_only_feature_snapshot=True,
            mtf_enabled=True,
            feature_validity_channels=False,
        )


def test_recorded_sequence_schema_rejects_corrupt_hash_and_channel_mismatch() -> None:
    schema = build_sequence_feature_schema(["volume_spike"])
    corrupt = {**schema, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="hash or dimensions"):
        resolve_recorded_sequence_schema(
            corrupt,
            available_columns={"volume_spike"},
            generated_columns=set(),
            train_only_screen=True,
            has_train_only_feature_snapshot=True,
            mtf_enabled=False,
            feature_validity_channels=False,
        )
    with pytest.raises(ValueError, match="validity channels differ"):
        resolve_recorded_sequence_schema(
            schema,
            available_columns={"volume_spike"},
            generated_columns=set(),
            train_only_screen=True,
            has_train_only_feature_snapshot=True,
            mtf_enabled=False,
            feature_validity_channels=True,
        )


def test_checkpoint_reanalysis_inherits_sampled_mode_and_seed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    evaluation_dir = source / "evaluations"
    evaluation_dir.mkdir(parents=True)
    (evaluation_dir / "test_report_only.json").write_text(
        json.dumps({"policy_action_mode": "stochastic", "action_rng_seed": 50}),
        encoding="utf-8",
    )

    assert eval_run.resolve_reanalysis_action_mode(source, None) is True
    assert eval_run.resolve_reanalysis_action_seed(source, None, stochastic=True) == 50
    assert eval_run.resolve_reanalysis_action_mode(source, False) is False


def test_checkpoint_reanalysis_parses_tick_fill_slippage_override() -> None:
    args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out", "--tick-fill-slippage-points", "10"]
    )
    assert args.tick_fill_slippage_points == 10.0


def test_checkpoint_reanalysis_can_disable_only_peak_eod_training_policy() -> None:
    args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out", "--disable-peak-eod-dd-policy"]
    )
    source = {
        "peak_trailing_dd_limit_usd": 10_000.0,
        "max_loss_usd": 1100.0,
        "respect_planned_risk": True,
    }

    resolved = eval_run.resolve_replay_eod_risk(
        source, disable_peak_eod_dd_policy=args.disable_peak_eod_dd_policy
    )

    assert resolved == {
        "peak_trailing_dd_limit_usd": 0.0,
        "max_loss_usd": 1100.0,
        "respect_planned_risk": True,
    }
    assert source["peak_trailing_dd_limit_usd"] == 10_000.0


def test_checkpoint_reanalysis_preserves_source_eod_policy_by_default() -> None:
    args = eval_run.build_reanalysis_parser().parse_args(["--run", "source", "--output", "out"])

    resolved = eval_run.resolve_replay_eod_risk(
        {"peak_trailing_dd_limit_usd": 10_000.0},
        disable_peak_eod_dd_policy=args.disable_peak_eod_dd_policy,
    )

    assert resolved == {"peak_trailing_dd_limit_usd": 10_000.0}


def test_train_only_screen_is_explicit_opt_in() -> None:
    default_args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out"]
    )
    screen_args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out", "--train-only-screen"]
    )
    ledger_args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out", "--train-only-screen", "--export-replay-ledger"]
    )

    assert default_args.train_only_screen is False
    assert screen_args.train_only_screen is True
    assert ledger_args.export_replay_ledger is True


def test_replay_ledger_export_requires_train_only_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["checkpoint-reanalysis", "--run", "source", "--output", "out", "--export-replay-ledger"],
    )

    with pytest.raises(SystemExit, match="requires --train-only-screen"):
        eval_run.main()


def test_train_only_screen_requires_seed_for_stochastic_actions() -> None:
    with pytest.raises(ValueError, match="requires a recorded or explicit seed"):
        eval_run.validate_train_only_action_mode(
            train_only_screen=True, stochastic=True, action_rng_seed=None
        )

    eval_run.validate_train_only_action_mode(
        train_only_screen=True, stochastic=True, action_rng_seed=50
    )
    eval_run.validate_train_only_action_mode(
        train_only_screen=True, stochastic=False, action_rng_seed=None
    )


def test_train_only_screen_report_records_evaluation_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provenance = {
        "source": {"available": True, "head": "test-revision", "dirty_files": []},
        "runtime": {"python": "test-runtime"},
        "python_executable": "/test/python",
    }
    monkeypatch.setattr(eval_run, "build_evaluation_provenance", lambda _repo: provenance)

    report_path = eval_run.write_train_only_screen_report(
        tmp_path / "screen",
        {"artifact_role": "candidate_screen_train_only", "test_split_evaluated": False},
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["evaluation_provenance"] == provenance
    assert report["test_split_evaluated"] is False


def test_train_only_screen_exports_complete_replay_ledgers_with_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_run, "build_evaluation_provenance", lambda _repo: {})
    monkeypatch.setattr(
        eval_run,
        "reconcile_account_state_trace",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0, "checks": {}},
    )
    monkeypatch.setattr(
        eval_run,
        "reconcile_policy_decisions",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0, "checks": {}},
    )
    result = {
        "equity": pd.Series([100.0, 101.0], name="equity"),
        "trades": pd.DataFrame({"trade_id": [1]}),
        "policy_decisions": pd.DataFrame({"action": [0, 1]}),
        "account_state_trace": pd.DataFrame({"balance": [100.0, 101.0]}),
        "breaches": [{"time": "t1", "kind": "daily"}],
        "breach_events": [],
        "cycle_events": pd.DataFrame({"cycle": [1]}),
        "payout_events": pd.DataFrame({"payout": [0.5]}),
        "trade_setup_decisions": pd.DataFrame(
            {"decision_id": ["decision-1"], "candidate_id": ["po3:M1:long"]}
        ),
        "policy_decisions_complete": True,
        "account_state_trace_complete": True,
        "n_steps": 2,
    }

    report_path = eval_run.write_train_only_screen_report(
        tmp_path / "screen",
        {"artifact_role": "candidate_screen_train_only", "test_split_evaluated": False},
        replay_result=result,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    ledger = report["replay_ledger"]

    assert ledger["complete"] is True
    assert ledger["test_split_evaluated"] is False
    assert ledger["n_steps"] == 2
    assert ledger["artifacts"]["trade_setup_decisions"]["row_count"] == 1
    for name, artifact in ledger["artifacts"].items():
        path = report_path.parent / artifact["path"]
        assert path.is_file()
        assert artifact["sha256"] == file_sha256(path)
        if artifact["row_count"]:
            frame = pd.read_csv(path)
            assert len(frame) == artifact["row_count"]
        else:
            assert path.read_text(encoding="utf-8") == ""

    monkeypatch.setattr(
        eval_run,
        "reconcile_account_state_trace",
        lambda *_args, **_kwargs: {"status": "mismatch", "failure_count": 1, "checks": {}},
    )
    with pytest.raises(ValueError, match="account-state/daily-risk reconciliation"):
        eval_run.write_train_only_screen_report(
            tmp_path / "risk-mismatch",
            {"artifact_role": "candidate_screen_train_only", "test_split_evaluated": False},
            replay_result=result,
        )
    diagnostic = tmp_path / "risk-mismatch" / "replay_ledger_diagnostic.json"
    assert diagnostic.is_file()
    assert (tmp_path / "risk-mismatch" / "diagnostic_replay_account_state_trace.csv").is_file()

    monkeypatch.setattr(
        eval_run,
        "reconcile_account_state_trace",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0, "checks": {}},
    )
    monkeypatch.setattr(
        eval_run,
        "reconcile_policy_decisions",
        lambda *_args, **_kwargs: {"status": "incomplete", "failure_count": 0, "checks": {}},
    )
    with pytest.raises(ValueError, match="policy-decision/action reconciliation"):
        eval_run.write_train_only_screen_report(
            tmp_path / "policy-mismatch",
            {"artifact_role": "candidate_screen_train_only", "test_split_evaluated": False},
            replay_result=result,
        )


@pytest.mark.parametrize("missing_field", ["cycle_events", "payout_events"])
def test_train_only_screen_requires_cash_event_ledgers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_field: str
) -> None:
    monkeypatch.setattr(eval_run, "build_evaluation_provenance", lambda _repo: {})
    monkeypatch.setattr(
        eval_run,
        "reconcile_account_state_trace",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0},
    )
    monkeypatch.setattr(
        eval_run,
        "reconcile_policy_decisions",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0},
    )
    result = {
        "equity": pd.Series([100.0]),
        "trades": pd.DataFrame(),
        "policy_decisions": pd.DataFrame({"action": [0]}),
        "account_state_trace": pd.DataFrame({"balance": [100.0]}),
        "breaches": [],
        "breach_events": [],
        "cycle_events": pd.DataFrame(),
        "payout_events": pd.DataFrame(),
        "policy_decisions_complete": True,
        "account_state_trace_complete": True,
        "n_steps": 1,
    }
    result.pop(missing_field)

    with pytest.raises(ValueError, match=missing_field):
        eval_run.write_train_only_screen_report(
            tmp_path / missing_field,
            {"artifact_role": "candidate_screen_train_only", "test_split_evaluated": False},
            replay_result=result,
        )


def test_train_only_screen_requires_setup_ledger_for_setup_actions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_run, "build_evaluation_provenance", lambda _repo: {})
    result = {
        "equity": pd.Series([100.0]),
        "trades": pd.DataFrame(),
        "policy_decisions": pd.DataFrame({"trade_setup_candidate_id": [0]}),
        "account_state_trace": pd.DataFrame({"balance": [100.0]}),
        "breaches": [],
        "breach_events": [],
        "cycle_events": pd.DataFrame(),
        "payout_events": pd.DataFrame(),
        "policy_decisions_complete": True,
        "account_state_trace_complete": True,
        "n_steps": 1,
    }

    with pytest.raises(ValueError, match="setup-aware policy decisions"):
        eval_run.write_train_only_screen_report(
            tmp_path / "missing-setup-ledger",
            {"artifact_role": "candidate_screen_train_only", "test_split_evaluated": False},
            replay_result=result,
        )


@pytest.mark.parametrize("failure_count", [False, 0.0, "0"])
def test_train_only_screen_rejects_malformed_reconciliation_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_count: object
) -> None:
    monkeypatch.setattr(eval_run, "build_evaluation_provenance", lambda _repo: {})
    monkeypatch.setattr(
        eval_run,
        "reconcile_account_state_trace",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": failure_count},
    )
    monkeypatch.setattr(
        eval_run,
        "reconcile_policy_decisions",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0},
    )
    result = {
        "equity": pd.Series([100.0]),
        "trades": pd.DataFrame(),
        "policy_decisions": pd.DataFrame({"action": [0]}),
        "account_state_trace": pd.DataFrame({"balance": [100.0]}),
        "breaches": [],
        "breach_events": [],
        "cycle_events": pd.DataFrame(),
        "payout_events": pd.DataFrame(),
        "policy_decisions_complete": True,
        "account_state_trace_complete": True,
        "n_steps": 1,
    }

    with pytest.raises(ValueError, match="account-state/daily-risk reconciliation"):
        eval_run.write_train_only_screen_report(
            tmp_path / "malformed-reconciliation",
            {"artifact_role": "candidate_screen_train_only", "test_split_evaluated": False},
            replay_result=result,
        )


def test_train_only_screen_replay_ledger_fails_closed_on_incomplete_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_run, "build_evaluation_provenance", lambda _repo: {})
    result = {
        "equity": pd.Series([100.0]),
        "trades": pd.DataFrame(),
        "policy_decisions": pd.DataFrame(),
        "account_state_trace": pd.DataFrame(),
        "breaches": [],
        "breach_events": [],
        "policy_decisions_complete": False,
        "account_state_trace_complete": True,
    }

    with pytest.raises(ValueError, match="policy_decisions_complete"):
        eval_run.write_train_only_screen_report(
            tmp_path / "incomplete",
            {"artifact_role": "candidate_screen_train_only", "test_split_evaluated": False},
            replay_result=result,
        )


def test_train_only_evaluation_receives_only_training_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    train_bars = pd.DataFrame({"close": [100.0, 101.0]})
    train_features = pd.DataFrame({"signal": [0.0, 1.0]})
    captured: dict[str, object] = {}

    def fake_evaluate(_model: object, *, stochastic: bool, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        captured["stochastic"] = stochastic
        return {"equity": [100_000.0, 100_100.0], "trades": []}

    monkeypatch.setattr(eval_run, "evaluate_checkpoint_split", fake_evaluate)
    result, metrics = eval_run.evaluate_train_split(
        object(),
        stochastic=False,
        bars=train_bars,
        features=train_features,
        tickbook=None,
        legacy_sequence_columns=False,
        eval_common={},
        initial_balance=100_000.0,
        periods_per_year=100,
    )

    assert captured["bars"] is train_bars
    assert captured["features"] is train_features
    assert captured["stochastic"] is False
    assert result["initial_balance"] == 100_000.0
    assert metrics.n_trades == 0


def test_train_only_dataset_parity_checks_training_inputs_only() -> None:
    source = {
        "train_bars": {"sha256": "train-bars"},
        "train_features": {"sha256": "train-features"},
        "test_bars": {"sha256": "source-test-bars"},
        "test_features": {"sha256": "source-test-features"},
        "primary_ticks": {"sha256": "full-ticks"},
    }
    evaluated = {
        "train_bars": {"sha256": "train-bars"},
        "train_features": {"sha256": "train-features"},
        "primary_ticks": {"sha256": "training-ticks"},
    }

    assert (
        _validate_reanalysis_datasets(
            source,
            evaluated,
            allow_legacy=False,
            train_only=True,
        )
        == "train_only_verified_full_tick_identity_not_reloaded"
    )


def test_train_only_dataset_parity_rejects_training_input_mismatch() -> None:
    source = {
        "train_bars": {"sha256": "source-train-bars"},
        "train_features": {"sha256": "train-features"},
    }
    evaluated = {
        "train_bars": {"sha256": "different-train-bars"},
        "train_features": {"sha256": "train-features"},
    }

    with pytest.raises(ValueError, match="differs from training for train_bars"):
        _validate_reanalysis_datasets(
            source,
            evaluated,
            allow_legacy=False,
            train_only=True,
        )


def test_execution_seed_uses_explicit_override_then_source_seed() -> None:
    manifest = {
        "seed": 50,
        "training_protocol": {"seed": 51},
        "metrics_protocol": {"execution_seed": 52},
    }

    assert eval_run.resolve_execution_seed(7, manifest) == 7
    assert eval_run.resolve_execution_seed(None, manifest) == 50


def test_execution_seed_rejects_negative_and_reports_missing_seed() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        eval_run.resolve_execution_seed(-1, {})
    assert eval_run.resolve_execution_seed(None, {}) is None


def test_legacy_input_provenance_reanalysis_requires_explicit_opt_in() -> None:
    args = eval_run.build_reanalysis_parser().parse_args(["--run", "source", "--output", "out"])
    assert args.allow_legacy_data_provenance is False
    assert args.source_feature_cache is None
    opted_in = eval_run.build_reanalysis_parser().parse_args(
        [
            "--run",
            "source",
            "--output",
            "out",
            "--allow-legacy-data-provenance",
            "--source-feature-cache",
            "cache/baseline.parquet",
        ]
    )
    assert opted_in.allow_legacy_data_provenance is True
    assert opted_in.source_feature_cache == "cache/baseline.parquet"


def test_legacy_sequence_schema_reanalysis_requires_explicit_opt_in() -> None:
    default_args = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out"]
    )
    opted_in = eval_run.build_reanalysis_parser().parse_args(
        ["--run", "source", "--output", "out", "--allow-legacy-sequence-schema"]
    )

    assert default_args.allow_legacy_sequence_schema is False
    assert opted_in.allow_legacy_sequence_schema is True


def test_checkpoint_replay_forwards_legacy_sequence_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_evaluate_model(
        _model: object, *, deterministic: bool, **kwargs: object
    ) -> dict[str, str]:
        captured["deterministic"] = deterministic
        captured.update(kwargs)
        return {"status": "captured"}

    monkeypatch.setattr(eval_run, "evaluate_model", fake_evaluate_model)
    result = eval_run.evaluate_checkpoint_split(
        object(),
        stochastic=False,
        bars=pd.DataFrame(),
        features=pd.DataFrame(),
        legacy_sequence_columns=True,
    )

    assert result == {"status": "captured"}
    assert captured["deterministic"] is True
    assert captured["legacy_sequence_columns"] is True


def test_checkpoint_sequence_width_must_match_ordered_feature_schema() -> None:
    model = SimpleNamespace(
        observation_space=SimpleNamespace(
            spaces={"seq": SimpleNamespace(shape=(128, 7)), "account": object()}
        )
    )

    assert eval_run.validate_sequence_input_width(model, 7) == 7
    with pytest.raises(ValueError, match="sequence input width disagrees"):
        eval_run.validate_sequence_input_width(model, 8)


def test_reanalysis_feature_cache_requires_identity_or_legacy_opt_in(tmp_path: Path) -> None:
    cache = tmp_path / "features_v1.parquet"
    cache.write_bytes(b"features")
    (tmp_path / "features_v1.parquet.hash").write_text("abc123\n")

    with pytest.raises(ValueError, match="no feature-cache identity"):
        _validate_reanalysis_feature_cache(None, cache, allow_legacy=False)

    disposition, digest, file_digest = _validate_reanalysis_feature_cache(
        None, cache, allow_legacy=True
    )
    assert disposition == "legacy_unverified"
    assert digest == "abc123"
    assert file_digest == file_sha256(cache)


def test_reanalysis_dataset_parity_requires_exact_train_test_inputs() -> None:
    train = {
        "sha256": "train-digest",
        "rows": 2,
    }
    test = {
        "sha256": "test-digest",
        "rows": 1,
    }
    datasets = {
        "train_bars": train,
        "train_features": train,
        "test_bars": test,
        "test_features": test,
    }

    assert _validate_reanalysis_datasets(datasets, datasets, allow_legacy=False) == "verified"
    with pytest.raises(ValueError, match="dataset differs from training for test_features"):
        _validate_reanalysis_datasets(
            datasets,
            {**datasets, "test_features": {"sha256": "changed"}},
            allow_legacy=False,
        )
    assert _validate_reanalysis_datasets(None, datasets, allow_legacy=True) == "legacy_unverified"
    with pytest.raises(ValueError, match="incomplete train/test dataset identities"):
        _validate_reanalysis_datasets({"train_bars": train}, datasets, allow_legacy=True)


def test_evaluation_dataset_records_include_splits_secondary_and_ticks() -> None:
    index = pd.date_range("2025-01-01", periods=2, freq="min", tz="UTC")
    frame = pd.DataFrame({"close": [100.0, 101.0]}, index=index)

    class TickBook:
        _ts = pd.Series([1, 2]).to_numpy(dtype="int64")
        _bid = pd.Series([100.0, 101.0]).to_numpy(dtype="float64")
        _ask = pd.Series([100.1, 101.1]).to_numpy(dtype="float64")

    result = _evaluation_dataset_records(
        train_bars=frame,
        train_features=frame,
        test_bars=frame,
        test_features=frame,
        train_secondary=frame,
        test_secondary=frame,
        primary_ticks=TickBook(),
    )
    assert set(result) == {
        "train_bars",
        "train_features",
        "test_bars",
        "test_features",
        "train_secondary",
        "test_secondary",
        "primary_ticks",
    }
    assert result["primary_ticks"]["rows"] == 2


@pytest.mark.parametrize(
    ("source", "evaluation", "expected"),
    [
        ({"data_source": "frame"}, "frame", ("frame", "same_backend")),
        ({"data_source": "frames"}, "frame", ("frames", "same_backend")),
        (
            {"data_source": "bundle"},
            "frame",
            ("bundle", "cross_backend_requires_checkpoint_parity"),
        ),
        ({"data_source": "bundle"}, "bundle", ("bundle", "same_backend")),
        (None, "frame", ("unknown", "legacy_unverified")),
    ],
)
def test_reanalysis_records_backend_parity_disposition(
    source: object, evaluation: str, expected: tuple[str, str]
) -> None:
    assert _reanalysis_backend_disposition(source, evaluation) == expected


def test_reanalysis_feature_cache_requires_exact_training_identity_and_hash(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "features_v1.parquet"
    cache.write_bytes(b"features")
    (tmp_path / "features_v1.parquet.hash").write_text("abc123\n")
    cache_file_digest = file_sha256(cache)
    source = {
        "identity": cache.name,
        "sha256": "abc123",
        "file_sha256": cache_file_digest,
    }

    assert _validate_reanalysis_feature_cache(source, cache, allow_legacy=False) == (
        "verified",
        "abc123",
        cache_file_digest,
    )
    with pytest.raises(ValueError, match="identity differs from training"):
        _validate_reanalysis_feature_cache(
            {"identity": "other.parquet", "sha256": "abc123"},
            cache,
            allow_legacy=False,
        )
    with pytest.raises(ValueError, match="content identity differs from training"):
        _validate_reanalysis_feature_cache(
            {"identity": cache.name, "sha256": "different"},
            cache,
            allow_legacy=False,
        )
    with pytest.raises(ValueError, match="file SHA-256 differs from training"):
        _validate_reanalysis_feature_cache(
            {**source, "file_sha256": "0" * 64},
            cache,
            allow_legacy=False,
        )
    with pytest.raises(ValueError, match="feature_cache.identity is missing"):
        _validate_reanalysis_feature_cache({}, cache, allow_legacy=True)
    partial_source = {"identity": cache.name, "sha256": "abc123"}
    with pytest.raises(ValueError, match="feature_cache.file_sha256 is missing"):
        _validate_reanalysis_feature_cache(partial_source, cache, allow_legacy=False)
    assert _validate_reanalysis_feature_cache(partial_source, cache, allow_legacy=True) == (
        "legacy_unverified",
        "abc123",
        cache_file_digest,
    )


def test_exact_source_feature_cache_replay_requires_manifest_file_identity(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "baseline.parquet"
    index = pd.date_range("2025-01-01", periods=2, freq="min", tz="UTC")
    expected = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    expected.to_parquet(cache)
    (tmp_path / "baseline.parquet.hash").write_text("content-hash\n")
    source = {
        "identity": cache.name,
        "sha256": "content-hash",
        "file_sha256": file_sha256(cache),
    }

    loaded, resolved, cache_hash, file_hash = _load_exact_source_feature_cache(source, cache)
    pd.testing.assert_frame_equal(loaded, expected, check_freq=False)
    assert resolved == cache.resolve()
    assert cache_hash == "content-hash"
    assert file_hash == source["file_sha256"]

    with pytest.raises(ValueError, match="file SHA-256 differs from training"):
        _load_exact_source_feature_cache({**source, "file_sha256": "0" * 64}, cache)

    with pytest.raises(ValueError, match="requires feature_cache.file_sha256"):
        _load_exact_source_feature_cache({"identity": cache.name, "sha256": "content-hash"}, cache)


def test_train_only_feature_snapshot_requires_train_only_and_excludes_full_cache() -> None:
    with pytest.raises(ValueError, match="requires --train-only-screen"):
        validate_train_only_feature_snapshot_request(
            train_only_screen=False,
            source_feature_cache=None,
            train_only_feature_snapshot="train.parquet",
        )
    with pytest.raises(ValueError, match="cannot be combined"):
        validate_train_only_feature_snapshot_request(
            train_only_screen=True,
            source_feature_cache="all.parquet",
            train_only_feature_snapshot="train.parquet",
        )
    validate_train_only_feature_snapshot_request(
        train_only_screen=True,
        source_feature_cache=None,
        train_only_feature_snapshot="train.parquet",
    )


def test_train_only_feature_snapshot_requires_exact_ordered_timeline(tmp_path: Path) -> None:
    cache = tmp_path / "train_features.parquet"
    index = pd.date_range("2025-01-01", periods=3, freq="min", tz="UTC")
    expected = pd.DataFrame({"feature": [1.0, 0.0, 3.0]}, index=index)
    expected.to_parquet(cache)

    loaded, resolved, cache_hash = _load_train_only_feature_snapshot(cache, index)
    pd.testing.assert_frame_equal(loaded, expected, check_freq=False)
    assert resolved == cache.resolve()
    assert cache_hash == file_sha256(cache)

    with pytest.raises(ValueError, match="do not exactly match training bars"):
        _load_train_only_feature_snapshot(cache, index.delete(1))

    duplicated = pd.DataFrame({"feature": [1.0, 2.0]}, index=[index[0], index[0]])
    duplicated.to_parquet(cache)
    with pytest.raises(ValueError, match="must be unique and ordered"):
        _load_train_only_feature_snapshot(cache, pd.DatetimeIndex(duplicated.index))


def test_stop_schema_requires_checkpoint_manifest_and_config_agreement() -> None:
    schema = {"menu": "recent_confirmed_unswept_mtf_swings_v1"}
    assert (
        eval_run.validate_stop_candidate_schema(
            checkpoint_schema=schema,
            manifest_schema=schema,
            expected_schema=schema,
            allow_legacy=False,
        )
        == "versioned"
    )
    with pytest.raises(ValueError, match="disagree"):
        eval_run.validate_stop_candidate_schema(
            checkpoint_schema=schema,
            manifest_schema={"menu": "legacy_last_accepted_swing_v1"},
            expected_schema=schema,
            allow_legacy=False,
        )
    with pytest.raises(ValueError, match="differs from the run config"):
        eval_run.validate_stop_candidate_schema(
            checkpoint_schema=schema,
            manifest_schema=schema,
            expected_schema={"menu": "legacy_last_accepted_swing_v1"},
            allow_legacy=False,
        )
    assert (
        eval_run.validate_stop_candidate_schema(
            checkpoint_schema=schema,
            manifest_schema=schema,
            expected_schema={"menu": "current_eight_timeframe_menu"},
            allow_legacy=False,
            allow_changed_menu=True,
        )
        == "changed_policy_diagnostic"
    )


def test_legacy_stop_schema_requires_opt_in_and_cannot_claim_expanded_menu() -> None:
    legacy = {"menu": "legacy_last_accepted_swing_v1"}
    with pytest.raises(ValueError, match="no stop-candidate schema"):
        eval_run.validate_stop_candidate_schema(
            checkpoint_schema=None,
            manifest_schema=None,
            expected_schema=legacy,
            allow_legacy=False,
        )
    assert (
        eval_run.validate_stop_candidate_schema(
            checkpoint_schema=None,
            manifest_schema=None,
            expected_schema=legacy,
            allow_legacy=True,
        )
        == "legacy_opt_in"
    )
    with pytest.raises(ValueError, match="cannot assert that menu was trained"):
        eval_run.validate_stop_candidate_schema(
            checkpoint_schema=None,
            manifest_schema=None,
            expected_schema={"menu": "recent_confirmed_unswept_mtf_swings_v1"},
            allow_legacy=True,
        )


def test_checkpoint_reanalysis_checks_manifest_artifact_hash(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.zip"
    checkpoint.write_bytes(b"saved checkpoint")
    expected = file_sha256(checkpoint)

    assert (
        eval_run.validate_checkpoint_manifest_hash(checkpoint, {"checkpoint": {"sha256": expected}})
        == "verified"
    )
    with pytest.raises(ValueError, match="does not match"):
        eval_run.validate_checkpoint_manifest_hash(checkpoint, {"checkpoint": {"sha256": "0" * 64}})
    assert eval_run.validate_checkpoint_manifest_hash(checkpoint, {}) == (
        "unavailable_legacy_manifest"
    )


@pytest.mark.parametrize(("stochastic", "expected_deterministic"), [(False, True), (True, False)])
def test_checkpoint_split_replay_passes_selected_action_mode(
    monkeypatch: pytest.MonkeyPatch, stochastic: bool, expected_deterministic: bool
) -> None:
    captured: dict[str, bool] = {}

    def fake_evaluate_model(
        _model: object, *, deterministic: bool, **_kwargs: object
    ) -> dict[str, object]:
        captured["deterministic"] = deterministic
        return {}

    monkeypatch.setattr(eval_run, "evaluate_model", fake_evaluate_model)
    result = eval_run.evaluate_checkpoint_split(object(), stochastic=stochastic)

    assert result == {}
    assert captured["deterministic"] is expected_deterministic


def test_reanalysis_requires_explicit_historical_access(tmp_path: Path) -> None:
    source = tmp_path / "historical"
    source.mkdir()
    with pytest.raises(ValueError, match="historical"):
        _validate_reanalysis_request(source, tmp_path / "review", allow_historical=False)


def test_reanalysis_refuses_input_and_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "historical"
    source.mkdir()
    with pytest.raises(ValueError, match="separate"):
        _validate_reanalysis_request(source, source, allow_historical=True)
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "metrics.json").write_text("immutable")
    with pytest.raises(FileExistsError, match="exists"):
        _validate_reanalysis_request(source, destination, allow_historical=True)
    assert (destination / "metrics.json").read_text() == "immutable"


def test_reanalysis_allows_new_output_and_keeps_source(tmp_path: Path) -> None:
    source = tmp_path / "historical"
    source.mkdir()
    (source / "config.yaml").write_text("original")
    _validate_reanalysis_request(source, tmp_path / "review", allow_historical=True)
    assert (source / "config.yaml").read_text() == "original"


def test_evaluation_fails_closed_without_run_config_snapshot(tmp_path: Path) -> None:
    run_dir = tmp_path / "historical"
    run_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="Run config snapshot missing"):
        _load_run_config(run_dir)


@pytest.mark.parametrize("contents", ["", "- 1\n- 2\n"])
def test_evaluation_rejects_nonmapping_run_snapshot(tmp_path: Path, contents: str) -> None:
    run_dir = tmp_path / "historical"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text(contents)
    with pytest.raises(ValueError, match="configuration mapping"):
        _load_run_config(run_dir)


def test_evaluation_uses_exact_run_snapshot(tmp_path: Path) -> None:
    run_dir = tmp_path / "historical"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text(
        "env:\n  strategy_actions: true\n"
        "data:\n  split:\n    train_end: '2025-12-31'\n"
        "    test_start: '2026-01-01'\n"
    )
    cfg = _load_run_config(run_dir)
    assert cfg.env.strategy_actions is True


@pytest.mark.parametrize(
    "contents",
    [
        "env:\n  strategy_actions: true\n",
        "data:\n  split:\n    train_end: '2025-12-31'\n",
        "data:\n  split:\n    test_start: '2026-01-01'\n",
        "data:\n  split:\n    train_end: null\n    test_start: ''\n",
    ],
)
def test_evaluation_rejects_missing_saved_split_boundaries(tmp_path: Path, contents: str) -> None:
    run_dir = tmp_path / "historical"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text(contents)
    with pytest.raises(ValueError, match="split"):
        _load_run_config(run_dir)


def test_eval_feature_scope_matches_training_mask_and_cache(tmp_path: Path) -> None:
    index = pd.date_range("2025-01-01", periods=6, freq="D", tz="UTC")
    bars = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]}, index=index)
    cfg = OmegaConf.create({"features": {"zscore_window": 3}})
    mask, cache = _feature_build_scope(bars, cfg, tmp_path, "US100", "2025-01-03")
    assert mask.tolist() == [True, True, True, False, False, False]
    assert cache == feature_cache_path(tmp_path, "US100", cfg, bars, train_mask=mask)
    assert cache != feature_cache_path(tmp_path, "US100", cfg, bars)


def test_eval_feature_scope_honors_and_hash_validates_prebuilt_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = pd.date_range("2025-01-01", periods=6, freq="D", tz="UTC")
    bars = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]}, index=index)
    cache = tmp_path / "prebuilt.parquet"
    cache.write_bytes(b"cache")
    (tmp_path / "prebuilt.parquet.hash").write_text("expected\n")
    cfg = OmegaConf.create(
        {
            "data": {"prebuilt_feature_cache": str(cache)},
            "features": {"zscore_window": 3, "po3_reference_mode": "m1_legacy"},
        }
    )
    monkeypatch.setattr(
        reanalysis_provenance,
        "feature_cache_content_hash",
        lambda *_args, **_kwargs: "expected",
    )

    mask, resolved = _feature_build_scope(bars, cfg, tmp_path, "US100", "2025-01-03")
    assert mask.tolist() == [True, True, True, False, False, False]
    assert resolved == cache

    (tmp_path / "prebuilt.parquet.hash").write_text("stale\n")
    with pytest.raises(ValueError, match="does not match the saved config/data hash"):
        _feature_build_scope(bars, cfg, tmp_path, "US100", "2025-01-03")
