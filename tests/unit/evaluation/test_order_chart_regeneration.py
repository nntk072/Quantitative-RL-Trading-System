from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from omegaconf import OmegaConf

from evaluation.reporting import order_chart_regeneration
from evaluation.reporting.order_chart_regeneration import (
    _build_chart_features,
    _chart_feature_config,
    _entry_idea_timeframes,
    _standard_deviation_timeframes,
)


def test_chart_overlay_selection_enables_only_requested_context_families() -> None:
    config = OmegaConf.create(
        {
            "features": {
                "order_blocks": {"enabled": False, "timeframes": ["M5"]},
                "include_fvg_ifvg": False,
                "include_strategy_state": False,
                "ifvg_mtf": {"enabled": False, "timeframes": ["M5"]},
                "structure": {"enabled": True, "timeframes": ["M5"]},
            }
        }
    )

    chart_config = _chart_feature_config(
        config,
        order_block_timeframes=("M1", "H1"),
        fvg_timeframes=(),
        ifvg_timeframes=("M5", "D1"),
        swing_timeframes=("M1", "M5"),
    )

    assert chart_config.features.order_blocks.enabled is True
    assert list(chart_config.features.order_blocks.timeframes) == ["M1", "H1"]
    assert chart_config.features.include_fvg_ifvg is False
    assert chart_config.features.include_strategy_state is True
    assert chart_config.features.ifvg_mtf.enabled is True
    assert list(chart_config.features.ifvg_mtf.timeframes) == ["M5", "D1"]
    assert chart_config.features.structure.enabled is True
    assert list(chart_config.features.structure.timeframes) == ["M5"]
    assert config.features.order_blocks.enabled is False


def test_m1_only_swing_plot_keeps_primary_structure_without_mtf_build() -> None:
    config = OmegaConf.create({"features": {"structure": {"enabled": True}}})

    chart_config = _chart_feature_config(
        config,
        order_block_timeframes=(),
        fvg_timeframes=(),
        ifvg_timeframes=(),
        swing_timeframes=("M1",),
    )

    assert chart_config.features.structure.enabled is False


def test_chart_feature_build_uses_full_history_and_saved_training_mask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = OmegaConf.create(
        {"data": {"split": {"train_start": "2025-01-02", "train_end": "2025-01-03"}}}
    )
    index = pd.DatetimeIndex(
        [
            "2025-01-01 23:59:59.999999",
            "2025-01-02 00:00:00",
            "2025-01-03 23:59:59.999999",
            "2025-01-04 00:00:00",
        ],
        tz="America/New_York",
    )

    primary = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]}, index=index)
    secondary = pd.DataFrame({"close": [5.0, 6.0, 7.0, 8.0]}, index=index)
    feature_config = OmegaConf.create({"features": {}})
    expected = pd.DataFrame({"normalized": [0.0, 0.0, 1.0, 2.0]}, index=index)
    captured: dict[str, Any] = {}

    def build_features(
        primary_arg: pd.DataFrame,
        *,
        secondary: pd.DataFrame | None,
        cfg: Any,
        train_mask: pd.Series,
    ) -> pd.DataFrame:
        captured["primary"] = primary_arg
        captured["secondary"] = secondary
        captured["cfg"] = cfg
        captured["train_mask"] = train_mask
        return expected

    monkeypatch.setattr(order_chart_regeneration, "build_features", build_features)
    result = _build_chart_features(config, feature_config, primary, secondary)

    assert result is expected
    assert captured["primary"] is primary
    assert captured["secondary"] is secondary
    assert captured["cfg"] is feature_config
    assert captured["train_mask"].tolist() == [False, True, True, False]


def test_replot_rebuilds_all_timeframes_used_by_overlapping_trade_ideas() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "entry_ideas": (
                    "['po3', 'fvg_retest', 'ifvg_retest', 'ifvg_unretested', "
                    "'order_block', 'standard_deviation']"
                ),
                "entry_idea_timeframes": (
                    "{'po3': ['M15'], 'fvg_retest': ['M5'], 'ifvg_retest': ['M10'], "
                    "'ifvg_unretested': ['M30'], "
                    "'order_block': ['M3'], 'standard_deviation': ['H1']}"
                ),
            }
        ]
    )
    idea_timeframes = _entry_idea_timeframes(trades)
    config = OmegaConf.create(
        {
            "features": {
                "order_blocks": {"enabled": False, "timeframes": []},
                "entry_ideas": {"enabled": False, "timeframes": []},
                "include_fvg_ifvg": False,
                "include_strategy_state": False,
                "fvg_timeframes": [],
                "ifvg_mtf": {"enabled": False, "timeframes": []},
                "po3_state_mtf": {"enabled": False, "timeframes": []},
                "structure": {"enabled": False, "timeframes": []},
            }
        }
    )

    chart_config = _chart_feature_config(
        config,
        order_block_timeframes=(),
        fvg_timeframes=(),
        ifvg_timeframes=(),
        swing_timeframes=(),
        entry_idea_timeframes=idea_timeframes,
    )

    assert list(chart_config.features.order_blocks.timeframes) == ["M3"]
    assert list(chart_config.features.fvg_timeframes) == ["M5", "M15"]
    assert list(chart_config.features.ifvg_mtf.timeframes) == ["M10", "M15", "M30"]
    assert list(chart_config.features.po3_state_mtf.timeframes) == ["M15"]
    assert list(chart_config.features.entry_ideas.timeframes) == ["H1"]


def test_entry_idea_timeframes_ignores_malformed_rows_and_uses_recorded_zone_timeframes() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "entry_ideas": "[malformed",
                "entry_idea_timeframes": "{'po3': ['H1']}",
                "entry_idea_zones": "[]",
            },
            {
                "type": "open",
                "entry_ideas": "['po3', 'order_block']",
                "entry_idea_timeframes": "{'po3': 'h1'}",
                "entry_idea_zones": "[{'idea': 'ifvg_retest', 'timeframe': 'm15'}]",
            },
            {
                "type": "close",
                "entry_ideas": "['sweep']",
                "entry_idea_timeframes": "{'sweep': ['D1']}",
                "entry_idea_zones": "[]",
            },
        ]
    )

    assert _entry_idea_timeframes(trades) == {
        "po3": ("H1",),
        "order_block": ("M1",),
        "ifvg_retest": ("M15",),
    }


def test_standard_deviation_timeframes_follow_only_open_retracement_setups() -> None:
    trades = pd.DataFrame(
        [
            {
                "type": "open",
                "entry_ideas": "['standard_deviation', 'po3']",
                "entry_idea_timeframes": "{'standard_deviation': ['H1', 'M15'], 'po3': ['M5']}",
            },
            {
                "type": "open",
                "entry_ideas": "['fvg_retest']",
                "entry_idea_timeframes": "{'standard_deviation': ['H4']}",
            },
            {
                "type": "close",
                "entry_ideas": "['standard_deviation']",
                "entry_idea_timeframes": "{'standard_deviation': ['D1']}",
            },
        ]
    )

    assert _standard_deviation_timeframes(trades) == ("M15", "H1")


def test_load_split_bars_partitions_secondary_timeline_with_the_primary_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {
                "primary": "ES",
                "secondary": "NQ",
                "split": {"train_end": "2025-01-03", "test_start": "2025-01-05"},
            }
        }
    )
    primary_index = pd.DatetimeIndex(
        [
            "2025-01-02T15:00:00Z",
            "2025-01-03T15:00:00Z",
            "2025-01-04T15:00:00Z",
            "2025-01-05T15:00:00Z",
        ]
    )
    secondary_index = pd.DatetimeIndex(
        ["2025-01-02T16:00:00Z", "2025-01-04T16:00:00Z", "2025-01-05T16:00:00Z"]
    )
    primary = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0]}, index=primary_index)
    secondary = pd.DataFrame({"close": [200.0, 202.0, 203.0]}, index=secondary_index)
    calls: list[bool] = []

    def load_pipeline(_cfg: Any, *, force: bool) -> dict[str, Any]:
        calls.append(force)
        return {
            "ES": {"M1": primary},
            "NQ": {"M1": secondary},
        }

    monkeypatch.setattr(order_chart_regeneration, "run_pipeline", load_pipeline)

    train, train_secondary, full_primary, full_secondary = (
        order_chart_regeneration._load_split_bars(cfg, "training", True)
    )
    test, test_secondary, repeated_primary, repeated_secondary = (
        order_chart_regeneration._load_split_bars(cfg, "testing", False)
    )

    assert train.index.equals(primary_index[:2])
    assert test.index.equals(primary_index[3:])
    assert train_secondary is not None
    assert test_secondary is not None
    assert train_secondary.index.equals(secondary_index[:1])
    assert test_secondary.index.equals(secondary_index[2:])
    assert train_secondary["close"].tolist() == [200.0]
    assert test_secondary["close"].tolist() == [203.0]
    assert full_primary is primary and repeated_primary is primary
    assert full_secondary is secondary and repeated_secondary is secondary
    assert calls == [True, False]


def test_main_applies_cli_render_overrides_and_normalizes_timeframe_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "source-run"
    run_dir.mkdir()
    output_dir = tmp_path / "rendered"
    cfg = OmegaConf.create({"output": {"save_html": True, "max_order_charts": 40}})
    calls: list[tuple[Any, ...]] = []

    def capture_split(*args: Any) -> None:
        calls.append(args)

    monkeypatch.setattr(order_chart_regeneration, "_load_run_config", lambda _: cfg)
    monkeypatch.setattr(order_chart_regeneration, "_replot_split", capture_split)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "order-chart-regeneration",
            "--run",
            str(run_dir),
            "--output",
            str(output_dir),
            "--split",
            "training",
            "--dpi",
            "110",
            "--max-charts",
            "3",
            "--no-save-html",
            "--force",
            "--order-block-timeframes",
            "h1,m5",
            "--ema-timeframes",
            "all",
            "--swing-timeframes",
            "",
        ],
    )

    order_chart_regeneration.main()

    assert output_dir.is_dir()
    assert len(calls) == 1
    assert calls[0][0:7] == (run_dir, cfg, "training", 110, True, False, 3)
    assert calls[0][7] == output_dir
    assert calls[0][8] == ("H1", "M5")
    assert calls[0][11] == ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
    assert calls[0][12] == ()


def test_main_rejects_unsupported_timeframe_before_creating_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "source-run"
    run_dir.mkdir()
    output_dir = tmp_path / "rendered"
    cfg = OmegaConf.create({"output": {}})
    called = False

    def capture_split(*args: Any) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(order_chart_regeneration, "_load_run_config", lambda _: cfg)
    monkeypatch.setattr(order_chart_regeneration, "_replot_split", capture_split)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "order-chart-regeneration",
            "--run",
            str(run_dir),
            "--output",
            str(output_dir),
            "--fvg-timeframes",
            "H2",
        ],
    )

    with pytest.raises(SystemExit, match="Unsupported chart timeframe"):
        order_chart_regeneration.main()

    assert not output_dir.exists()
    assert called is False


def test_replot_copies_equity_to_separate_output_and_skips_data_load_without_trades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "source-run"
    source_split = run_dir / "training"
    source_split.mkdir(parents=True)
    equity_path = source_split / "equity.csv"
    equity_path.write_text("time,equity\n2025-01-02,100000\n", encoding="utf-8")
    output_root = tmp_path / "rendered"
    cfg = OmegaConf.create({})
    summaries: list[tuple[Path, Any, Any]] = []

    def record_summary(
        split_dir: Path, config: Any, dpi: int, *, trades: pd.DataFrame | None = None
    ) -> None:
        summaries.append((split_dir, config, trades))

    def fail_data_load(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("bar data should not be loaded when the split has no trades.csv")

    monkeypatch.setattr(order_chart_regeneration, "_replot_split_summary", record_summary)
    monkeypatch.setattr(order_chart_regeneration, "_load_split_bars", fail_data_load)

    order_chart_regeneration._replot_split(
        run_dir,
        cfg,
        "training",
        72,
        False,
        output_root=output_root,
        swing_timeframes=(),
    )

    output_split = output_root / "training"
    assert (output_split / "equity.csv").read_bytes() == equity_path.read_bytes()
    assert equity_path.read_text(encoding="utf-8").endswith("100000\n")
    assert summaries == [(output_split, cfg, None)]


def test_replot_normalizes_trade_times_and_replaces_stale_charts_without_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "source-run"
    source_split = run_dir / "training"
    source_split.mkdir(parents=True)
    (source_split / "trades.csv").write_text(
        "type,time,direction,price,pnl\n"
        "open,2025-01-02T13:01:00+00:00,1,100.0,\n"
        "close,2025-01-02T13:02:00+00:00,1,101.0,1.0\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "rendered"
    orders_dir = output_root / "training" / "orders"
    orders_dir.mkdir(parents=True)
    (orders_dir / "stale.html").write_text("old output", encoding="utf-8")
    cfg = OmegaConf.create({"data": {"primary": "ES"}})
    bars_index = pd.date_range("2025-01-02 15:00", periods=4, freq="min", tz="Europe/Helsinki")
    bars = pd.DataFrame({"close": [100.0, 100.5, 101.0, 101.5]}, index=bars_index)
    received: dict[str, Any] = {}

    def plot_orders(_bars: pd.DataFrame, trades: pd.DataFrame, *, orders_dir: Path, **_kwargs: Any):
        received["times"] = pd.DatetimeIndex(trades["time"])
        orders_dir.mkdir(parents=True, exist_ok=True)
        (orders_dir / "regenerated.png").write_text("chart", encoding="utf-8")

    def plot_html(_bars: pd.DataFrame, _trades: pd.DataFrame, *, orders_dir: Path, **_kwargs: Any):
        (orders_dir / "regenerated.html").write_text("chart", encoding="utf-8")

    monkeypatch.setattr(order_chart_regeneration, "_replot_split_summary", lambda *_a, **_k: None)
    monkeypatch.setattr(
        order_chart_regeneration,
        "_load_split_bars",
        lambda *_args: (bars, None, bars, None),
    )
    monkeypatch.setattr(order_chart_regeneration, "_extract_trade_chart_config", lambda _cfg: {})
    monkeypatch.setattr(
        order_chart_regeneration.__dict__["_plt"], "plot_per_trade_orders", plot_orders
    )
    monkeypatch.setattr(
        order_chart_regeneration.__dict__["_pi"], "plot_per_trade_orders", plot_html
    )
    monkeypatch.setattr(
        "evaluation.plotting.diagnostics.trade.write_trade_diagnostics",
        lambda _directory, trades, *_args, **_kwargs: received.update(diagnostics_rows=len(trades)),
    )

    order_chart_regeneration._replot_split(
        run_dir,
        cfg,
        "training",
        72,
        False,
        save_html=True,
        output_root=output_root,
        swing_timeframes=(),
    )

    assert received["times"].tz == bars_index.tz
    assert received["times"].tolist() == [bars_index[1], bars_index[2]]
    assert received["diagnostics_rows"] == 2
    assert not (orders_dir / "stale.html").exists()
    assert (orders_dir / "regenerated.png").is_file()
    assert (orders_dir / "regenerated.html").is_file()
