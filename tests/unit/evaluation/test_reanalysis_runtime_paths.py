"""Train-only reanalysis routes preserve replay mode and report scope."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from evaluation.reanalysis import checkpoint_reanalysis


def test_replay_mode_and_seed_use_only_valid_recorded_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "source"
    metadata_dir = run_dir / "evaluations"
    metadata_dir.mkdir(parents=True)
    metadata_path = metadata_dir / "test_report_only.json"

    assert checkpoint_reanalysis.resolve_reanalysis_action_mode(run_dir, None) is False
    assert (
        checkpoint_reanalysis.resolve_reanalysis_action_seed(run_dir, None, stochastic=True) is None
    )
    metadata_path.write_text(
        json.dumps({"policy_action_mode": "stochastic", "action_rng_seed": 19}),
        encoding="utf-8",
    )
    assert checkpoint_reanalysis.resolve_reanalysis_action_mode(run_dir, None) is True
    assert (
        checkpoint_reanalysis.resolve_reanalysis_action_seed(run_dir, None, stochastic=True) == 19
    )
    assert checkpoint_reanalysis.resolve_reanalysis_action_mode(run_dir, False) is False
    assert checkpoint_reanalysis.resolve_reanalysis_action_seed(run_dir, 7, stochastic=True) == 7

    metadata_path.write_text("[]", encoding="utf-8")
    assert checkpoint_reanalysis.resolve_reanalysis_action_mode(run_dir, None) is False
    metadata_path.write_text("{invalid", encoding="utf-8")
    assert (
        checkpoint_reanalysis.resolve_reanalysis_action_seed(run_dir, None, stochastic=True) is None
    )


def test_train_only_stochastic_replay_requires_an_action_seed() -> None:
    checkpoint_reanalysis.validate_train_only_action_mode(
        train_only_screen=False, stochastic=True, action_rng_seed=None
    )
    checkpoint_reanalysis.validate_train_only_action_mode(
        train_only_screen=True, stochastic=False, action_rng_seed=None
    )
    checkpoint_reanalysis.validate_train_only_action_mode(
        train_only_screen=True, stochastic=True, action_rng_seed=3
    )
    with pytest.raises(ValueError, match="requires a recorded or explicit seed"):
        checkpoint_reanalysis.validate_train_only_action_mode(
            train_only_screen=True, stochastic=True, action_rng_seed=None
        )


@pytest.mark.parametrize("provider_api", [True, False])
def test_checkpoint_split_uses_provider_or_model_evaluator_with_matching_mode(
    monkeypatch: pytest.MonkeyPatch, provider_api: bool
) -> None:
    provider = (
        SimpleNamespace(metadata={}, predict=lambda *_args: None) if provider_api else object()
    )
    calls: list[tuple[str, bool, dict[str, Any]]] = []

    def evaluate(name: str):
        def capture(_provider: Any, *, deterministic: bool, **kwargs: Any) -> dict[str, Any]:
            calls.append((name, deterministic, kwargs))
            return {"equity": pd.Series([100.0])}

        return capture

    monkeypatch.setattr(checkpoint_reanalysis, "evaluate_provider", evaluate("provider"))
    monkeypatch.setattr(checkpoint_reanalysis, "evaluate_model", evaluate("model"))
    bars = pd.DataFrame({"close": [100.0]})
    features = pd.DataFrame({"atr": [1.0]})
    result = checkpoint_reanalysis.evaluate_checkpoint_split(
        provider, stochastic=True, bars=bars, features=features
    )

    assert result["equity"].iloc[0] == 100.0
    assert len(calls) == 1
    evaluator, deterministic, kwargs = calls[0]
    assert evaluator == ("provider" if provider_api else "model")
    assert deterministic is False
    assert kwargs["bars"] is bars
    assert kwargs["features"] is features


def test_replay_eod_risk_copies_settings_before_disabling_training_policy() -> None:
    source = {"peak_trailing_dd_limit_usd": 900.0, "daily_loss_limit_usd": 500.0}

    unchanged = checkpoint_reanalysis.resolve_replay_eod_risk(
        source, disable_peak_eod_dd_policy=False
    )
    disabled = checkpoint_reanalysis.resolve_replay_eod_risk(
        source, disable_peak_eod_dd_policy=True
    )

    assert unchanged == source
    assert disabled == {"peak_trailing_dd_limit_usd": 0.0, "daily_loss_limit_usd": 500.0}
    assert source["peak_trailing_dd_limit_usd"] == 900.0


def test_train_split_adds_initial_balance_and_account_path_inputs_to_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = pd.DataFrame({"close": [100.0]})
    features = pd.DataFrame({"atr": [1.0]})
    result: dict[str, Any] = {
        "equity": pd.Series([100_000.0, 100_001.0]),
        "trades": pd.DataFrame([{"pnl": 1.0}]),
        "n_sessions": 2,
        "n_breach_sessions": 1,
    }
    calls: dict[str, Any] = {}

    def evaluate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls["evaluation"] = (args, kwargs)
        return result

    def account_inputs(value: dict[str, Any]) -> dict[str, Any]:
        assert value is result
        return {"account_state_trace": "verified-input"}

    def calculate(equity: Any, **kwargs: Any) -> dict[str, Any]:
        calls["metrics"] = (equity, kwargs)
        return {"return": 0.01}

    monkeypatch.setattr(checkpoint_reanalysis, "evaluate_checkpoint_split", evaluate)
    monkeypatch.setattr(checkpoint_reanalysis, "account_path_metric_inputs", account_inputs)
    monkeypatch.setattr(checkpoint_reanalysis, "calculate_metrics", calculate)

    evaluated, metrics = checkpoint_reanalysis.evaluate_train_split(
        object(),
        stochastic=False,
        bars=bars,
        features=features,
        tickbook="ticks",
        legacy_sequence_columns=True,
        eval_common={"audit_tag": "train-only"},
        initial_balance=100_000.0,
        periods_per_year=252,
        sequence_columns_override=("close", "atr"),
    )

    assert evaluated is result
    assert evaluated["initial_balance"] == 100_000.0
    assert metrics == {"return": 0.01}
    assert calls["evaluation"][1]["sequence_columns_override"] == ("close", "atr")
    assert calls["metrics"][1]["n_sessions"] == 2
    assert calls["metrics"][1]["n_breach_sessions"] == 1
    assert calls["metrics"][1]["account_state_trace"] == "verified-input"
    assert calls["metrics"][1]["initial_balance"] == 100_000.0
    assert calls["evaluation"][1]["audit_tag"] == "train-only"


def test_train_only_screen_writer_persists_provenance_and_preserves_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "screen"
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "build_evaluation_provenance",
        lambda _root: {"source": "test-fixture", "complete": True},
    )
    report = {"status": "no_trade", "evaluated_split": "training"}

    report_path = checkpoint_reanalysis.write_train_only_screen_report(output_dir, report)

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["status"] == "no_trade"
    assert saved["evaluation_provenance"] == {"source": "test-fixture", "complete": True}
    assert saved["evaluated_split"] == "training"
    assert "replay_ledger" not in saved
    with pytest.raises(FileExistsError):
        checkpoint_reanalysis.write_train_only_screen_report(output_dir, {"status": "again"})


def test_reanalysis_rejects_unsupported_manifest_algorithm_before_loading_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "run_manifest.json").write_text(
        json.dumps(
            {
                "feature_cache": {"identity": "fixture"},
                "datasets": {},
                "training_protocol": {"algorithm": "td3"},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "reanalysis"
    checkpoint = source / "model.zip"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "checkpoint-reanalysis",
            "--run",
            str(source),
            "--output",
            str(output),
            "--allow-historical",
        ],
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "_load_run_config",
        lambda _run: SimpleNamespace(
            risk={"target_timeframes": ["M5"]},
            output=SimpleNamespace(save_html=False, max_order_charts=0),
        ),
    )
    monkeypatch.setattr(checkpoint_reanalysis, "resolve_checkpoint", lambda *_args: checkpoint)
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "validate_checkpoint_manifest_hash",
        lambda *_args: {"status": "unverified_legacy"},
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "load_checkpoint",
        lambda **_kwargs: pytest.fail("unsupported algorithm must be rejected before model load"),
    )

    with pytest.raises(ValueError, match="unsupported source checkpoint algorithm: 'td3'"):
        checkpoint_reanalysis.main()

    assert not output.exists()


@pytest.mark.parametrize(
    ("manifest_text", "message"),
    [
        ("[]", "source run manifest must be a JSON object"),
        (
            '{"feature_cache": {}, "datasets": []}',
            "source run manifest datasets must be an object",
        ),
        ('{"datasets": {}}', "lacks feature-cache or dataset identities"),
    ],
)
def test_reanalysis_rejects_invalid_source_manifest_before_loading_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_text: str,
    message: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "run_manifest.json").write_text(manifest_text, encoding="utf-8")
    output = tmp_path / "reanalysis"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "checkpoint-reanalysis",
            "--run",
            str(source),
            "--output",
            str(output),
            "--allow-historical",
        ],
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "_load_run_config",
        lambda _run: SimpleNamespace(
            risk={"target_timeframes": ["M5"]},
            output=SimpleNamespace(save_html=False, max_order_charts=0),
        ),
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "resolve_checkpoint",
        lambda *_args: source / "model.zip",
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "load_checkpoint",
        lambda **_kwargs: pytest.fail("invalid manifest must be rejected before model load"),
    )

    with pytest.raises(ValueError, match=message):
        checkpoint_reanalysis.main()

    assert not output.exists()
