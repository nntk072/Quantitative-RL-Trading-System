"""Behavioral contracts for report generation and replay-ledger exports."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from omegaconf import OmegaConf

from evaluation.reanalysis import checkpoint_reanalysis
from evaluation.reporting import order_chart_regeneration
from evaluation.reporting.account_state_trace_reconciliation import reconcile_account_state_trace
from evaluation.reporting.trade_note import build_trade_plot_note


def _complete_replay_result() -> dict[str, Any]:
    return {
        "policy_decisions_complete": True,
        "account_state_trace_complete": True,
        "n_steps": 1,
        "equity": pd.Series(
            [100_001.0], index=pd.DatetimeIndex(["2025-01-02T16:31:00Z"], name="time")
        ),
        "trades": pd.DataFrame([{"type": "close", "pnl": 1.0}]),
        "policy_decisions": pd.DataFrame([{"action": 1}]),
        "account_state_trace": pd.DataFrame([{"balance": 100_001.0}]),
        "breaches": [],
        "breach_events": pd.DataFrame(),
        "cycle_events": [{"type": "cycle_close"}],
        "payout_events": [],
    }


def test_train_only_replay_export_requires_complete_trace_and_required_ledgers(
    tmp_path: Path,
) -> None:
    output = tmp_path / "incomplete"
    output.mkdir()
    with pytest.raises(ValueError, match="policy_decisions_complete is not true"):
        checkpoint_reanalysis._write_train_only_replay_ledger(
            output,
            {"policy_decisions_complete": False, "account_state_trace_complete": True},
        )

    result = _complete_replay_result()
    del result["payout_events"]
    with pytest.raises(ValueError, match="missing fields.*payout_events"):
        checkpoint_reanalysis._write_train_only_replay_ledger(output, result)

    setup_aware = _complete_replay_result()
    setup_aware["policy_decisions"] = pd.DataFrame([{"trade_setup_candidate_id": "candidate-1"}])
    with pytest.raises(ValueError, match="lack trade_setup_decisions"):
        checkpoint_reanalysis._write_train_only_replay_ledger(output, setup_aware)


def test_train_only_replay_export_rejects_ledger_rows_outside_the_rollout_length(
    tmp_path: Path,
) -> None:
    output = tmp_path / "misaligned"
    output.mkdir()
    result = _complete_replay_result()
    result["policy_decisions"] = pd.DataFrame()

    with pytest.raises(ValueError, match="policy_decisions has 0 rows for 1 rollout steps"):
        checkpoint_reanalysis._write_train_only_replay_ledger(output, result)

    assert not list(output.glob("*.csv"))


def test_train_only_replay_export_writes_hashed_csvs_after_both_reconciliations_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "complete"
    output.mkdir()
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "reconcile_account_state_trace",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0},
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "reconcile_policy_decisions",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0},
    )

    ledger = checkpoint_reanalysis._write_train_only_replay_ledger(
        output, _complete_replay_result()
    )

    assert ledger["complete"] is True
    assert ledger["test_split_evaluated"] is False
    assert ledger["artifacts"]["equity"]["row_count"] == 1
    assert len(ledger["artifacts"]["equity"]["sha256"]) == 64
    assert (output / "replay_equity.csv").read_text(encoding="utf-8").startswith("time,value\n")
    assert (output / "replay_cycle_events.csv").is_file()


def test_train_only_replay_export_preserves_diagnostics_when_reconciliation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "diagnostic"
    output.mkdir()
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "reconcile_account_state_trace",
        lambda *_args, **_kwargs: {"status": "incomplete", "failure_count": 0},
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "reconcile_policy_decisions",
        lambda *_args, **_kwargs: {"status": "matched", "failure_count": 0},
    )

    with pytest.raises(ValueError, match="Diagnostic traces were preserved"):
        checkpoint_reanalysis._write_train_only_replay_ledger(output, _complete_replay_result())

    diagnostic = output / "replay_ledger_diagnostic.json"
    assert diagnostic.is_file()
    assert not (output / "replay_equity.csv").exists()


@pytest.mark.parametrize(
    ("extra_args", "message"),
    [
        (("--export-replay-ledger",), "requires --train-only-screen"),
        (
            ("--use-recorded-sequence-schema", "--allow-legacy-sequence-schema"),
            "cannot be combined",
        ),
    ],
)
def test_checkpoint_reanalysis_rejects_conflicting_cli_modes_before_io(
    monkeypatch: pytest.MonkeyPatch, extra_args: tuple[str, ...], message: str
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["checkpoint-reanalysis", "--run", "missing-run", "--output", "new-output", *extra_args],
    )

    with pytest.raises(SystemExit, match=message):
        checkpoint_reanalysis.main()


def test_checkpoint_reanalysis_requires_an_existing_source_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "checkpoint-reanalysis",
            "--run",
            str(tmp_path / "missing-run"),
            "--output",
            str(tmp_path / "new-output"),
        ],
    )

    with pytest.raises(SystemExit, match="Run directory not found"):
        checkpoint_reanalysis.main()


def test_checkpoint_reanalysis_inherits_only_a_valid_stochastic_action_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "_source_final_evaluation_metadata",
        lambda _run_dir: {"action_rng_seed": 23},
    )

    assert (
        checkpoint_reanalysis.resolve_reanalysis_action_seed(tmp_path, None, stochastic=True) == 23
    )
    assert (
        checkpoint_reanalysis.resolve_reanalysis_action_seed(tmp_path, None, stochastic=False)
        is None
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "_source_final_evaluation_metadata",
        lambda _run_dir: {"action_rng_seed": True},
    )
    assert (
        checkpoint_reanalysis.resolve_reanalysis_action_seed(tmp_path, None, stochastic=True)
        is None
    )


def test_account_trace_reports_missing_versioned_fields_as_incomplete() -> None:
    trace = pd.DataFrame(
        [{"schema_version": "account_state_trace.v3", "state_phase": "post_action_valuation"}]
    )

    report = reconcile_account_state_trace(trace, pd.DataFrame())

    assert report["status"] == "incomplete"
    assert "missing_point_value_column" in report["incomplete_reasons"]
    assert "missing_required_columns" in report["incomplete_reasons"]
    assert {"balance", "equity", "trade_event_count"}.issubset(report["missing_columns"])


def test_account_trace_rejects_mixed_schema_versions_before_reconciliation() -> None:
    trace = pd.DataFrame(
        [
            {"schema_version": "account_state_trace.v2", "state_phase": "pre_action_valuation"},
            {"schema_version": "account_state_trace.v3", "state_phase": "post_action_valuation"},
        ]
    )

    report = reconcile_account_state_trace(trace, pd.DataFrame())

    assert report["status"] == "incomplete"
    assert "unsupported_or_mixed_trace_schema" in report["incomplete_reasons"]
    assert report["trace_schema"] == ["account_state_trace.v2", "account_state_trace.v3"]


def test_plot_note_renders_short_side_events_and_clips_long_context() -> None:
    open_row = {
        "time": "2025-01-02T16:31:00Z",
        "fill_quote_source": "tick",
        "sl_price": 101.0,
        "sl_ref": "H1_last_swing_high",
        "tp_legs": [
            {"leg": 1, "executed_price": 98.0, "reference": "M5_fvg_bear_low"},
            "malformed leg",
        ],
        "primary_idea": "fvg_retest",
        "primary_setup_timeframe": "M5",
        "primary_direction": -1,
        "supporting_idea_timeframes": ["po3@H1:short" * 12],
    }
    events = pd.DataFrame(
        [
            {
                "type": "sl_update",
                "effective_time": "2025-01-02T16:32:00Z",
                "price": 100.0,
            },
            {
                "type": "stop_close",
                "actual_tick_time": "2025-01-02T16:33:00Z",
                "price": 99.5,
                "pnl": 2.0,
            },
            {
                "type": "tp_update",
                "tp_slot": 1,
                "effective_time": "2025-01-02T16:32:30Z",
                "price": 97.0,
            },
            {
                "type": "tp_partial_close",
                "tp_slot": 1,
                "actual_tick_time": "2025-01-02T16:34:00Z",
                "price": 97.0,
                "pnl": 3.0,
            },
        ]
    )

    note = build_trade_plot_note(
        open_row,
        {"time": "2025-01-02T16:35:00Z"},
        entry_price=99.0,
        exit_price=97.0,
        direction=-1,
        pnl=5.0,
        lots=0.5,
        close_reason_detail="structure_sl",
        position_events=events,
        signal_time="2025-01-02T16:30:00Z",
    )

    assert note[0].startswith("ENTRY Short 16:30:00→16:31:00 @ 99.00 · 0.50 lots · tick")
    assert note[1].startswith("REASON FVG retest M5 short; context:")
    assert len(note[1]) == 150 and note[1].endswith("…")
    assert "move →100.00" in note[2]
    assert "fill 16:33:00 @ 99.50 $+2.00" in note[2]
    assert "TP1 move →97.00" in note[3]
    assert "TP1 fill 16:34:00 @ 97.00 $+3.00" in note[3]
    assert note[4].endswith("SL hit · $+5.00")


@pytest.mark.parametrize(
    ("open_row", "expected"),
    [
        (
            {"entry_ideas": ["fvg_retest"], "entry_idea_zones": [{"family": "fvg"}]},
            "FVG reaction",
        ),
        (
            {"entry_ideas": ["fvg_retest"], "entry_idea_zones": [{"family": "ifvg"}]},
            "IFVG reaction",
        ),
        ({"entry_ideas": ["fvg_retest"]}, "Gap reaction type unrecorded"),
        ({}, "setup not recorded"),
        ({"entry_setup_types": ["sweep", "swing"], "manipulation": "against"}, "PO3 opposing"),
    ],
)
def test_plot_note_keeps_gap_family_and_opposing_context_explicit(
    open_row: dict[str, Any], expected: str
) -> None:
    note = build_trade_plot_note(
        open_row,
        {"time": "2025-01-02T16:35:00Z"},
        entry_price=100.0,
        exit_price=101.0,
        direction=1,
        pnl=-1.0,
        lots=1.0,
        close_reason_detail="",
    )

    assert expected in note[1]


@pytest.mark.parametrize(
    ("close_reason", "expected"),
    [("profit_target", "TP hit"), ("breakeven", "BE"), ("ema_21", "EMA exit"), ("", "closed")],
)
def test_plot_note_normalizes_close_reasons(close_reason: str, expected: str) -> None:
    note = build_trade_plot_note(
        {},
        {"time": "2025-01-02T16:35:00Z"},
        entry_price=100.0,
        exit_price=101.0,
        direction=1,
        pnl=1.0,
        lots=1.0,
        close_reason_detail=close_reason,
    )
    assert note[4].endswith(f"· {expected} · $+1.00")


def test_plot_note_marks_ema_runner_when_no_fixed_target_was_recorded() -> None:
    note = build_trade_plot_note(
        {"exit_mode": "ema_21"},
        {"time": "2025-01-02T16:35:00Z"},
        entry_price=100.0,
        exit_price=101.0,
        direction=1,
        pnl=1.0,
        lots=1.0,
        close_reason_detail="ema_exit",
    )
    assert note[3] == "TP EMA21 runner after partial"


def test_replot_converts_mixed_offset_trade_times_before_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evaluation.plotting import trade_plots

    run_dir = tmp_path / "run"
    source_split = run_dir / "training"
    source_split.mkdir(parents=True)
    (source_split / "trades.csv").write_text(
        "type,time,entry_ideas,entry_idea_timeframes\nopen,2025-11-02T01:30:00-04:00,,\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "rendered"
    orders_dir = output_root / "training" / "orders"
    orders_dir.mkdir(parents=True)
    stale_chart = orders_dir / "stale.png"
    stale_chart.touch()
    cfg = OmegaConf.create({})
    bars = pd.DataFrame({"close": [1.0]}, index=pd.DatetimeIndex(["2025-11-02T05:30:00Z"]))
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        order_chart_regeneration,
        "_replot_split_summary",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        order_chart_regeneration,
        "_load_split_bars",
        lambda *_args, **_kwargs: (bars, None, bars, None),
    )
    monkeypatch.setattr(order_chart_regeneration, "_extract_trade_chart_config", lambda _cfg: {})

    def capture_png(_bars: pd.DataFrame, trades: pd.DataFrame, **kwargs: Any) -> None:
        captured["trades"] = trades.copy()
        Path(kwargs["orders_dir"]).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        cast(Any, order_chart_regeneration)._plt,
        "plot_per_trade_orders",
        capture_png,
    )
    monkeypatch.setattr(
        cast(Any, order_chart_regeneration)._pi,
        "plot_per_trade_orders",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(trade_plots, "write_trade_diagnostics", lambda *_args, **_kwargs: None)

    order_chart_regeneration._replot_split(
        run_dir,
        cfg,
        "training",
        72,
        False,
        save_html=False,
        output_root=output_root,
        swing_timeframes=(),
    )

    assert captured["trades"].iloc[0]["time"] == pd.Timestamp("2025-11-02T05:30:00Z")
    assert not stale_chart.exists()
    assert orders_dir.is_dir()
