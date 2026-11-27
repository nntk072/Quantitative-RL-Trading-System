"""Fail-closed contracts for checkpoint replay inputs and explicit seeds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from artifacts.identity import file_sha256
from evaluation.reanalysis import checkpoint_reanalysis


def _complete_replay_result() -> dict[str, Any]:
    return {
        "policy_decisions_complete": True,
        "account_state_trace_complete": True,
        "n_steps": 1,
        "equity": pd.Series([100.0], name="equity"),
        "trades": pd.DataFrame(),
        "policy_decisions": pd.DataFrame([{"action": 0}]),
        "account_state_trace": pd.DataFrame([{"balance": 100.0}]),
        "breaches": [],
        "breach_events": [],
        "cycle_events": [],
        "payout_events": [],
    }


def test_explicit_action_seed_takes_precedence_even_for_deterministic_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "_source_final_evaluation_metadata",
        lambda _run: {"action_rng_seed": 17},
    )

    assert (
        checkpoint_reanalysis.resolve_reanalysis_action_seed(tmp_path, 42, stochastic=False) == 42
    )


def test_unsupported_replay_ledger_value_fails_before_writing_any_artifacts(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "replay"
    output_dir.mkdir()
    result = _complete_replay_result()
    result["equity"] = object()

    with pytest.raises(TypeError, match="replay ledger 'equity'"):
        checkpoint_reanalysis._write_train_only_replay_ledger(output_dir, result)

    assert list(output_dir.iterdir()) == []


def test_complete_replay_serializes_series_and_records_with_content_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clean = {"status": "matched", "failure_count": 0}
    monkeypatch.setattr(
        checkpoint_reanalysis, "reconcile_account_state_trace", lambda *_args, **_kwargs: clean
    )
    monkeypatch.setattr(
        checkpoint_reanalysis, "reconcile_policy_decisions", lambda *_args, **_kwargs: clean
    )
    result = _complete_replay_result()
    result["equity"] = pd.Series([100.0], index=pd.DatetimeIndex(["2025-05-01T15:00:00Z"]))
    result["cycle_events"] = [{"type": "cycle_close", "event_id": "cycle-1"}]

    ledger = checkpoint_reanalysis._write_train_only_replay_ledger(tmp_path, result)

    equity_artifact = ledger["artifacts"]["equity"]
    equity_path = tmp_path / equity_artifact["path"]
    saved_equity = pd.read_csv(equity_path)
    assert pd.to_datetime(saved_equity["time"], utc=True).iloc[0] == pd.Timestamp(
        "2025-05-01T15:00:00Z"
    )
    assert saved_equity["value"].tolist() == [100.0]
    assert equity_artifact["sha256"] == file_sha256(equity_path)
    cycles_path = tmp_path / ledger["artifacts"]["cycle_events"]["path"]
    assert pd.read_csv(cycles_path).to_dict("records") == [
        {"type": "cycle_close", "event_id": "cycle-1"}
    ]
