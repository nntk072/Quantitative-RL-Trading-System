"""Focused contracts for checkpoint replay validation and order chart helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from evaluation.plotting import orders
from evaluation.reanalysis import checkpoint_reanalysis


def test_reanalysis_rejects_non_object_training_protocol_before_checkpoint_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "run_manifest.json").write_text(
        json.dumps(
            {
                "feature_cache": {"identity": "fixture"},
                "datasets": {},
                "training_protocol": [],
            }
        ),
        encoding="utf-8",
    )
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
        checkpoint_reanalysis, "resolve_checkpoint", lambda *_args: source / "model.zip"
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "validate_checkpoint_manifest_hash",
        lambda *_args: {"status": "unverified_legacy"},
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "load_checkpoint",
        lambda **_kwargs: pytest.fail("invalid training protocol must fail before model load"),
    )

    with pytest.raises(ValueError, match="training_protocol must be an object"):
        checkpoint_reanalysis.main()

    assert not output.exists()


def test_order_chart_per_trade_equity_prefers_logged_close_and_fills_missing_values() -> None:
    close_times = pd.to_datetime(["2025-02-03T15:01:00Z", "2025-02-03T15:02:00Z"], utc=True)
    pairs = [
        (pd.Series(dtype=object), pd.Series({"time": close_times[0], "equity": 101.0})),
        (pd.Series(dtype=object), pd.Series({"time": close_times[1], "equity": None})),
    ]
    continuous = pd.Series([100.0, 102.0], index=close_times)

    times, values = orders._per_trade_equity(pairs, continuous)

    assert times.equals(pd.DatetimeIndex(close_times))
    assert values.tolist() == [101.0, 102.0]


@pytest.mark.parametrize(
    ("index", "expected_minutes"),
    [
        (pd.DatetimeIndex(["2025-02-03T15:00:00Z"]), 1),
        (pd.DatetimeIndex(["2025-02-03T15:00:00Z", "2025-02-03T15:00:00Z"]), 1),
    ],
)
def test_order_chart_candle_width_uses_minute_fallback_without_positive_spacing(
    index: pd.DatetimeIndex, expected_minutes: int
) -> None:
    assert orders._candle_body_days(index) == pytest.approx(expected_minutes / 1440)


def test_order_chart_date_format_handles_empty_and_multi_day_windows() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]))
    multi_day = pd.DataFrame(
        index=pd.DatetimeIndex(["2025-02-03T23:59:00Z", "2025-02-04T00:01:00Z"])
    )

    assert orders._axis_date_format(empty) == "%H:%M"
    assert orders._axis_date_format(multi_day) == "%m/%d %H:%M"


def test_order_chart_legacy_position_events_are_sorted_and_fill_pnl_is_computed() -> None:
    open_row = pd.Series(
        {
            "type": "open",
            "time": "2025-02-03T15:00:00Z",
            "price": 100.0,
            "direction": 1,
            "bar": 1,
        }
    )
    close_row = pd.Series(
        {
            "type": "close",
            "time": "2025-02-03T15:02:00Z",
            "price": 101.0,
            "size": 0.5,
            "bar": 3,
        }
    )
    partial = {
        **open_row.to_dict(),
        "type": "tp_partial_close",
        "time": "2025-02-03T15:01:00Z",
        "price": 102.0,
        "size": 0.5,
        "bar": 2,
    }
    events = orders._position_events(pd.DataFrame(), open_row, close_row)

    # Legacy rows without a position id fall back to the supplied pair and sort
    # the lifecycle by its bar key.
    assert events["type"].tolist() == ["open", "close"]
    calculated = orders._position_pnl_from_fills(
        pd.DataFrame([partial, close_row.to_dict()]),
        direction=1,
        entry=100.0,
        initial_lots=1.0,
        contract=2.0,
    )
    assert calculated == 3.0


def test_order_chart_pnl_uses_logged_exit_pnl_and_returns_zero_without_fill_fields() -> None:
    logged = pd.DataFrame(
        [
            {"type": "tp_partial_close", "pnl": 1.5},
            {"type": "close", "pnl": None},
        ]
    )
    unpriced = pd.DataFrame([{"type": "stop_close"}])

    assert orders._position_pnl_from_fills(logged, 1, 100.0, 1.0, 1.0) == 1.5
    assert orders._position_pnl_from_fills(unpriced, 1, 100.0, 1.0, 1.0) == 0.0
