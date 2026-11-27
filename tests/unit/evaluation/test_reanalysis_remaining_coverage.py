"""Reanalysis adapter and replay-ledger boundary contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from evaluation.reanalysis import checkpoint_reanalysis


def test_checkpoint_loader_forwards_algorithm_and_legacy_layout_to_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint = tmp_path / "policy.zip"
    received: list[tuple[Path, str | None, str]] = []
    sentinel = object()

    def load_adapter(path: Path, *, legacy_layout_key: str | None, algo: str = "ppo") -> object:
        received.append((path, legacy_layout_key, algo))
        return sentinel

    monkeypatch.setitem(checkpoint_reanalysis.__dict__, "load_sb3_checkpoint", load_adapter)

    loaded = checkpoint_reanalysis.load_checkpoint(
        checkpoint, legacy_layout_key="legacy4_no_exit_v1", algo="sac"
    )

    assert loaded is sentinel
    assert received == [(checkpoint, "legacy4_no_exit_v1", "sac")]


@pytest.mark.parametrize("payload", ["{malformed", "[]"])
def test_action_metadata_reader_ignores_malformed_or_non_object_json(
    tmp_path: Path, payload: str
) -> None:
    metadata = tmp_path / "evaluations" / "test_report_only.json"
    metadata.parent.mkdir()
    metadata.write_text(payload, encoding="utf-8")

    assert checkpoint_reanalysis.resolve_reanalysis_action_mode(tmp_path, None) is False
    assert (
        checkpoint_reanalysis.resolve_reanalysis_action_seed(tmp_path, None, stochastic=True)
        is None
    )


def test_replay_export_does_not_accept_boolean_zero_as_a_clean_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "replay"
    output.mkdir()
    result: dict[str, Any] = {
        "policy_decisions_complete": True,
        "account_state_trace_complete": True,
        "n_steps": 0,
        "equity": pd.Series(dtype=float),
        "trades": pd.DataFrame(),
        "policy_decisions": pd.DataFrame(),
        "account_state_trace": pd.DataFrame(),
        "breaches": [],
        "breach_events": [],
        "cycle_events": [],
        "payout_events": [],
    }
    monkeypatch.setitem(
        checkpoint_reanalysis.__dict__,
        "reconcile_account_state_trace",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": False},
    )
    monkeypatch.setitem(
        checkpoint_reanalysis.__dict__,
        "reconcile_policy_decisions",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0},
    )

    with pytest.raises(ValueError, match="Diagnostic traces were preserved"):
        checkpoint_reanalysis._write_train_only_replay_ledger(output, result)

    diagnostic = output / "replay_ledger_diagnostic.json"
    assert diagnostic.is_file()
    assert not (output / "replay_equity.csv").exists()
