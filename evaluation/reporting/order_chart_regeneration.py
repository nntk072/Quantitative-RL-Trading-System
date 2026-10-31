"""Regenerate per-trade order charts (PNG + HTML) for an existing run.

Rebuilds the M1 bars for a saved run's split from its ``config.yaml``
snapshot and re-renders the per-trade order charts directly from the run's
existing ``trades.csv`` — no retraining, no re-running the backtest. Useful
after a charting bug fix (e.g. the trade-pairing fix that dropped
``tp_close`` events) so a historical run's charts can be corrected without
the cost of regenerating the underlying trade log.

Usage
-----
    cd Quantitative-RL-Trading-System
    uv run python -m evaluation.reporting.order_chart_regeneration \\
        --run outputs/20260719_002519_rl_train_seed42 --split testing
    uv run python -m evaluation.reporting.order_chart_regeneration \\
        --run outputs/20260719_002519_rl_train_seed42 --split both
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import argparse
import logging
import shutil
from collections import defaultdict
from collections.abc import Mapping

import pandas as pd
from omegaconf import OmegaConf

from configuration import load_config
from evaluation.plotting import plots as _plt
from evaluation.plotting import plots_interactive as _pi
from evaluation.reporting.run_artifact_writer import (
    _extract_ftmo_limits,
    _extract_trade_chart_config,
)
from features.pipeline.feature_matrix_builder import build_features
from market_data.loading import run_pipeline
from market_data.splits.definitions import get_split_config, split_bars, split_train_test

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _load_run_config(run_dir: Path) -> Any:
    """Prefer the run's own config snapshot so split boundaries/account
    settings match exactly what produced its trades.csv."""
    cfg_path = run_dir / "config.yaml"
    if cfg_path.exists():
        log.info("Loading config snapshot: %s", cfg_path)
        return OmegaConf.load(cfg_path)
    log.warning("No config.yaml in %s; falling back to default config", run_dir)
    return load_config([])


def _load_split_bars(cfg: Any, split: str, force: bool) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Rebuild primary (and secondary if configured) M1 bars for one split."""
    data = run_pipeline(cfg, force=force)
    primary_m1 = data[cfg.data.primary]["M1"]
    secondary_m1 = data.get(cfg.data.secondary, {}).get("M1")
    train_end, test_start = get_split_config(cfg)
    train_bars, test_bars, _, _ = split_train_test(primary_m1, primary_m1, train_end, test_start)
    train_sec = test_sec = None
    if secondary_m1 is not None and not secondary_m1.empty:
        train_sec, test_sec = split_bars(secondary_m1, train_end, test_start)
    if split == "training":
        return train_bars, train_sec
    return test_bars, test_sec


def _chart_feature_config(
    cfg: Any,
    *,
    order_block_timeframes: tuple[str, ...],
    fvg_timeframes: tuple[str, ...],
    ifvg_timeframes: tuple[str, ...],
    swing_timeframes: tuple[str, ...],
    standard_deviation_timeframes: tuple[str, ...] = (),
    entry_idea_timeframes: Mapping[str, tuple[str, ...]] | None = None,
) -> Any:
    """Enable only selected context families on a disposable chart config."""
    copied = OmegaConf.create(OmegaConf.to_container(cfg, resolve=True))
    features = copied.setdefault("features", OmegaConf.create())
    ideas = entry_idea_timeframes or {}

    def merge_timeframes(*values: Any) -> tuple[str, ...]:
        ladder = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
        found: set[str] = set()
        for value in values:
            if isinstance(value, str):
                found.add(value.upper())
            elif isinstance(value, (tuple, list, set)):
                found.update(str(timeframe).upper() for timeframe in value)
        return tuple(timeframe for timeframe in ladder if timeframe in found) + tuple(
            sorted(found.difference(ladder))
        )

    ob_tfs = merge_timeframes(order_block_timeframes, ideas.get("order_block", ()))
    fvg_tfs = merge_timeframes(fvg_timeframes, ideas.get("fvg_retest", ()), ideas.get("po3", ()))
    po3_tfs = merge_timeframes(ideas.get("po3", ()))
    ifvg_tfs = merge_timeframes(
        ifvg_timeframes,
        po3_tfs,
        ideas.get("ifvg_retest", ()),
        ideas.get("ifvg_unretested", ()),
    )
    sd_tfs = merge_timeframes(standard_deviation_timeframes, ideas.get("standard_deviation", ()))
    if ob_tfs:
        features.order_blocks.enabled = True
        features.order_blocks.timeframes = list(ob_tfs)
    if fvg_tfs:
        features.include_fvg_ifvg = True
        features.fvg_timeframes = list(fvg_tfs)
    if ifvg_tfs:
        features.include_strategy_state = True
        features.ifvg_mtf.enabled = True
        features.ifvg_mtf.timeframes = list(ifvg_tfs)
    if po3_tfs:
        features.include_strategy_state = True
        features.po3_state_mtf.enabled = True
        features.po3_state_mtf.timeframes = list(po3_tfs)
    if swing_timeframes:
        features.structure.enabled = any(tf != "M1" for tf in swing_timeframes)
        features.structure.timeframes = [tf for tf in swing_timeframes if tf != "M1"]
    if sd_tfs:
        if "entry_ideas" not in features:
            features.entry_ideas = OmegaConf.create({})
        features.entry_ideas.enabled = True
        features.entry_ideas.timeframes = list(sd_tfs)
    return copied


def _entry_idea_timeframes(trades: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Union only the timeframes recorded on open rows for each entry idea."""
    ladder = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
    selected: dict[str, set[str]] = defaultdict(set)
    if "type" not in trades or "entry_ideas" not in trades:
        return {}
    for _, row in trades.loc[trades["type"].astype(str).eq("open")].iterrows():
        try:
            raw_ideas = row.get("entry_ideas")
            raw_timeframes = row.get("entry_idea_timeframes")
            raw_zones = row.get("entry_idea_zones")
            ideas = ast.literal_eval(raw_ideas) if isinstance(raw_ideas, str) else raw_ideas
            mapping = (
                ast.literal_eval(raw_timeframes)
                if isinstance(raw_timeframes, str)
                else raw_timeframes
            )
            zones = ast.literal_eval(raw_zones) if isinstance(raw_zones, str) else raw_zones
        except (SyntaxError, ValueError):
            continue
        if isinstance(mapping, Mapping):
            for idea, values in mapping.items():
                values = (values,) if isinstance(values, str) else values
                if isinstance(values, (list, tuple, set)):
                    selected[str(idea)].update(str(value).upper() for value in values)
        if isinstance(ideas, (list, tuple, set)):
            for idea in ideas:
                if not selected[str(idea)]:
                    selected[str(idea)].add("M1")
        if isinstance(zones, list):
            for zone in zones:
                if isinstance(zone, Mapping):
                    idea = str(zone.get("idea", ""))
                    if idea:
                        selected[idea].add(str(zone.get("timeframe", "M1")).upper())
    return {
        idea: tuple(tf for tf in ladder if tf in timeframes)
        for idea, timeframes in selected.items()
        if timeframes
    }


def _standard_deviation_timeframes(trades: pd.DataFrame) -> tuple[str, ...]:
    """Find retracement timeframes recorded on trades that used that idea."""
    if not {"type", "entry_ideas", "entry_idea_timeframes"}.issubset(trades.columns):
        return ()
    ladder = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
    selected: set[str] = set()
    for _, row in trades.loc[trades["type"].astype(str).eq("open")].iterrows():
        raw_ideas = row.get("entry_ideas")
        raw_timeframes = row.get("entry_idea_timeframes")
        try:
            ideas = ast.literal_eval(raw_ideas) if isinstance(raw_ideas, str) else raw_ideas
            mapping = (
                ast.literal_eval(raw_timeframes)
                if isinstance(raw_timeframes, str)
                else raw_timeframes
            )
        except (SyntaxError, ValueError):
            continue
        if not isinstance(ideas, (list, tuple, set)) or "standard_deviation" not in ideas:
            continue
        if not isinstance(mapping, dict):
            continue
        values = mapping.get("standard_deviation", ())
        if isinstance(values, str):
            values = (values,)
        if isinstance(values, (list, tuple, set)):
            selected.update(str(value).upper() for value in values)
    return tuple(tf for tf in ladder if tf in selected)


def _load_equity(split_dir: Path) -> pd.Series | None:
    path = split_dir / "equity.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    col = df.columns[0]
    equity = df[col]
    equity.name = "equity"
    return equity


def _replot_split_summary(
    split_dir: Path, cfg: Any, dpi: int, trades: pd.DataFrame | None = None
) -> None:
    """Refresh equity / drawdown / daily-PnL charts from the saved equity.csv."""
    equity = _load_equity(split_dir)
    if equity is None or equity.empty:
        log.warning("No equity.csv in %s; skipping summary charts", split_dir)
        return
    daily_loss_limit, max_loss_limit, profit_target = _extract_ftmo_limits(cfg)
    initial_balance = 100_000.0
    try:
        initial_balance = float(cfg.account.initial_balance)
    except Exception:
        pass
    log.info("Re-plotting equity/drawdown/daily PnL → %s", split_dir)
    _plt.plot_equity_curve(
        equity,
        initial_balance=initial_balance,
        daily_loss_limit=daily_loss_limit,
        max_loss_limit=max_loss_limit,
        profit_target=profit_target,
        trades=trades,
        out_path=split_dir / "equity.png",
        dpi=dpi,
    )
    _plt.plot_drawdown(
        equity,
        out_path=split_dir / "drawdown.png",
        dpi=dpi,
        daily_loss_limit=daily_loss_limit,
    )
    _plt.plot_daily_pnl(
        equity,
        daily_loss_limit=daily_loss_limit,
        out_path=split_dir / "daily_pnl.png",
        dpi=dpi,
    )
    try:
        _pi.plot_equity_curve(
            equity,
            initial_balance=initial_balance,
            daily_loss_limit=daily_loss_limit,
            max_loss_limit=max_loss_limit,
            profit_target=profit_target,
            trades=trades,
            out_path=split_dir / "equity.html",
        )
        _pi.plot_drawdown(
            equity,
            out_path=split_dir / "drawdown.html",
            daily_loss_limit=daily_loss_limit,
        )
        _pi.plot_daily_pnl(
            equity,
            daily_loss_limit=daily_loss_limit,
            out_path=split_dir / "daily_pnl.html",
        )
    except ImportError:
        log.warning("plotly not available — skipping interactive summary charts")


def _replot_split(
    run_dir: Path,
    cfg: Any,
    split: str,
    dpi: int,
    force: bool,
    save_html: bool = True,
    max_charts: int = 200,
    output_root: Path | None = None,
    order_block_timeframes: tuple[str, ...] = (),
    fvg_timeframes: tuple[str, ...] = (),
    ifvg_timeframes: tuple[str, ...] = (),
    ema_timeframes: tuple[str, ...] = (),
    swing_timeframes: tuple[str, ...] = ("M1",),
) -> None:
    source_split_dir = run_dir / split
    split_dir = (output_root or run_dir) / split
    split_dir.mkdir(parents=True, exist_ok=True)
    source_equity = source_split_dir / "equity.csv"
    if output_root is not None and source_equity.exists():
        shutil.copy2(source_equity, split_dir / "equity.csv")
    trades = None
    trades_path = source_split_dir / "trades.csv"
    if trades_path.exists():
        trades = pd.read_csv(trades_path, parse_dates=["time"])
    _replot_split_summary(split_dir, cfg, dpi, trades=trades)
    if trades is None:
        log.warning("No trades.csv for split=%s in %s; skipping", split, run_dir)
        return

    standard_deviation_timeframes = _standard_deviation_timeframes(trades)
    idea_timeframes = _entry_idea_timeframes(trades)

    bars, secondary = _load_split_bars(cfg, split, force)
    chart_features = None
    if (
        order_block_timeframes
        or fvg_timeframes
        or ifvg_timeframes
        or swing_timeframes
        or standard_deviation_timeframes
        or idea_timeframes
    ):
        feature_cfg = _chart_feature_config(
            cfg,
            order_block_timeframes=order_block_timeframes,
            fvg_timeframes=fvg_timeframes,
            ifvg_timeframes=ifvg_timeframes,
            swing_timeframes=swing_timeframes,
            standard_deviation_timeframes=standard_deviation_timeframes,
            entry_idea_timeframes=idea_timeframes,
        )
        chart_features = build_features(bars, secondary=secondary, cfg=feature_cfg)

    bar_tz = pd.DatetimeIndex(bars.index).tz

    def align_trade_time(value: Any) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if bar_tz is None:
            return timestamp.tz_localize(None) if timestamp.tzinfo is not None else timestamp
        if timestamp.tzinfo is None:
            return timestamp.tz_localize(bar_tz)
        return timestamp.tz_convert(bar_tz)

        # pandas keeps mixed UTC offsets (for example, a local timezone crossing
        # daylight-saving time) as object dtype, which has no `.dt` accessor.
        # Normalize each event to the bar index timezone before pairing trades.

    trades["time"] = pd.DatetimeIndex(trades["time"].map(align_trade_time))

    chart_cfg = _extract_trade_chart_config(cfg)
    orders_dir = split_dir / "orders"

    # Old filenames encode the (possibly wrong) PnL, so a mis-paired trade
    # regenerates under a different filename than its corrected version.
    # Clear stale charts first so the directory doesn't accumulate both.
    if orders_dir.exists():
        shutil.rmtree(orders_dir)

    log.info(
        "Re-plotting PNG orders for split=%s (%d trade rows, max %d) → %s",
        split,
        len(trades),
        max_charts,
        orders_dir,
    )
    _plt.plot_per_trade_orders(
        bars,
        trades,
        orders_dir=orders_dir,
        dpi=dpi,
        max_charts=max_charts,
        secondary_bars=secondary,
        features=chart_features,
        order_block_timeframes=order_block_timeframes,
        fvg_timeframes=fvg_timeframes,
        ifvg_timeframes=ifvg_timeframes,
        ema_timeframes=ema_timeframes,
        swing_timeframes=swing_timeframes,
        **chart_cfg,
    )

    if save_html:
        log.info("Re-plotting HTML orders for split=%s → %s", split, orders_dir)
        _pi.plot_per_trade_orders(
            bars,
            trades,
            orders_dir=orders_dir,
            max_charts=max_charts,
            secondary_bars=secondary,
            features=chart_features,
            order_block_timeframes=order_block_timeframes,
            fvg_timeframes=fvg_timeframes,
            ifvg_timeframes=ifvg_timeframes,
            ema_timeframes=ema_timeframes,
            swing_timeframes=swing_timeframes,
            **chart_cfg,
        )
    from evaluation.plotting.trade_plots import write_trade_diagnostics

    log.info("Re-plotting trade diagnostics → %s", split_dir)
    write_trade_diagnostics(
        split_dir,
        trades,
        bars,
        dpi=dpi,
        save_plots=True,
        save_html=save_html,
        lots=float(chart_cfg.get("lots", 1.0)),
        contract_size=float(chart_cfg.get("contract_size", 1.0)),
        max_loss_per_trade_usd=chart_cfg.get("max_loss_per_trade_usd"),
        take_profit_per_trade_usd=chart_cfg.get("take_profit_per_trade_usd"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate order charts and equity/drawdown/daily-PnL figures "
        "for an existing run (no retraining, no backtest re-run)."
    )
    parser.add_argument("--run", required=True, help="Path to an existing run directory")
    parser.add_argument(
        "--output",
        default=None,
        help="Write regenerated figures to a separate directory; never replace source charts.",
    )
    parser.add_argument(
        "--split",
        choices=["training", "testing", "both"],
        default="both",
        help="Which split's orders to regenerate",
    )
    parser.add_argument("--dpi", type=int, default=150, help="PNG resolution")
    parser.add_argument(
        "--max-charts",
        type=int,
        default=None,
        help="Cap on per-trade charts per split (default: config output.max_order_charts, else 200).",
    )
    parser.add_argument(
        "--save-html",
        dest="save_html",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Render interactive HTML (default: config output.save_html).",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force the data pipeline to rebuild caches"
    )
    parser.add_argument(
        "--order-block-timeframes",
        default="",
        help="Comma-separated OB plot timeframes; use 'all' or empty",
    )
    parser.add_argument(
        "--fvg-timeframes",
        default="",
        help="Comma-separated FVG plot timeframes; use 'all' or empty",
    )
    parser.add_argument(
        "--ifvg-timeframes",
        default="",
        help="Comma-separated IFVG plot timeframes; use 'all' or empty",
    )
    parser.add_argument(
        "--ema-timeframes", default="M1", help="EMA timeframes; comma-separated, 'all', or empty"
    )
    parser.add_argument(
        "--swing-timeframes",
        default="M1",
        help="Swing timeframes; comma-separated, 'all', or empty",
    )
    args = parser.parse_args()

    run_dir = Path(args.run)
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")

    cfg = _load_run_config(run_dir)
    # A run's own snapshot is authoritative for data/split settings, but chart
    # volume is a present-day rendering choice. Let the CLI override both.
    save_html = (
        bool(getattr(cfg.output, "save_html", True)) if args.save_html is None else args.save_html
    )
    max_charts = args.max_charts
    if max_charts is None:
        max_charts = int(getattr(cfg.output, "max_order_charts", 0) or 0) or 200
    log.info(
        "Chart rendering: save_html=%s max_charts=%d (overrides snapshot)",
        save_html,
        max_charts,
    )

    splits = ["training", "testing"] if args.split == "both" else [args.split]
    output_root = Path(args.output) if args.output else None
    timeframe_ladder = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")

    def selected_timeframes(value: str) -> tuple[str, ...]:
        if not value.strip():
            return ()
        if value.strip().lower() == "all":
            return timeframe_ladder
        selected = tuple(item.strip().upper() for item in value.split(",") if item.strip())
        unsupported = sorted(set(selected).difference(timeframe_ladder))
        if unsupported:
            raise SystemExit(f"Unsupported chart timeframe(s): {unsupported}")
        return selected

    order_block_timeframes = selected_timeframes(args.order_block_timeframes)
    fvg_timeframes = selected_timeframes(args.fvg_timeframes)
    ifvg_timeframes = selected_timeframes(args.ifvg_timeframes)
    ema_timeframes = selected_timeframes(args.ema_timeframes)
    swing_timeframes = selected_timeframes(args.swing_timeframes)
    if output_root is not None:
        output_root.mkdir(parents=True, exist_ok=True)
    for split in splits:
        _replot_split(
            run_dir,
            cfg,
            split,
            args.dpi,
            args.force,
            save_html,
            max_charts,
            output_root,
            order_block_timeframes,
            fvg_timeframes,
            ifvg_timeframes,
            ema_timeframes,
            swing_timeframes,
        )

    log.info("Done. Re-plotted orders under: %s", output_root or run_dir)


if __name__ == "__main__":
    main()
