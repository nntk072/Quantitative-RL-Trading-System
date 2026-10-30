from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import logging
from pathlib import Path
from typing import Any, cast

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from evaluation.metrics.trade_pairs import pair_trades as _pair_trades

from .order_window import _extend_trade_window as _extend_trade_window
from .order_window import _extract_window as _extract_window
from .order_window import _structure_anchors as _structure_anchors
from .plot_rendering import (
    _NOTE_FONT_PT,
    BREACH_COLOR,
    CLOSE_COLOR,
    EQUITY_COLOR,
    LONG_COLOR,
    SHORT_COLOR,
    _apply_style,
    _save,
)

log = logging.getLogger(__name__)


def plot_price_with_orders(
    bars: pd.DataFrame,
    trades: pd.DataFrame | None,
    max_points: int = 3000,
    candle_tf: str = "15min",
    out_path: Path | str | None = None,
    dpi: int = 150,
) -> Figure:
    """Candlestick chart with buy/sell/close markers.

    Resamples `bars` (M1) to `candle_tf` (e.g. "15min") and caps at
    `max_points` candles so the PNG stays readable.
    """
    try:
        import mplfinance as mpf
    except ImportError:
        return _plot_price_line_fallback(bars, trades, max_points, out_path, dpi)

    _apply_style()

    # Resample to target timeframe
    ohlcv = bars[["open", "high", "low", "close"]].copy()
    if "volume" in bars.columns:
        ohlcv["volume"] = bars["volume"]
    ohlcv = (
        ohlcv.resample(candle_tf)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                **({} if "volume" not in ohlcv.columns else {"volume": "sum"}),
            }
        )
        .dropna()
    )

    if len(ohlcv) > max_points:
        ohlcv = ohlcv.iloc[-max_points:]

    # Build addplots for orders — candle-interval binning via floor to candle_tf
    addplots = []
    if trades is not None and not trades.empty and "time" in trades.columns:
        opens = trades[trades["type"] == "open"].copy()
        closes = trades[
            trades["type"].isin(["close", "forced_close", "eod_close", "stop_close", "tp_close"])
        ].copy()

        min_ts = ohlcv.index.min()
        max_ts = ohlcv.index.max()

        def _bin_time(ts: pd.Timestamp) -> pd.Timestamp | None:
            """Floor timestamp to candle bin and drop markers outside the plotted window."""
            if ts < min_ts or ts > max_ts:
                return None
            binned = ts.floor(candle_tf)
            if binned in ohlcv.index:
                return binned
            # fallback: nearest right candle within range
            loc = int(ohlcv.index.searchsorted(ts, side="left"))
            if loc >= len(ohlcv):
                return None
            candidate = ohlcv.index[loc]
            if candidate < min_ts or candidate > max_ts:
                return None
            return pd.Timestamp(candidate)

        def _make_series(subset: pd.DataFrame, direction: int) -> pd.Series | None:
            mask = (
                (subset["direction"] == direction)
                if "direction" in subset.columns
                else pd.Series(False, index=subset.index)
            )
            rows = subset[mask] if "direction" in subset.columns else pd.DataFrame()
            if rows.empty:
                return None
            s = pd.Series(np.nan, index=ohlcv.index)
            for _, row in rows.iterrows():
                candle_ts = _bin_time(row["time"])
                if candle_ts is None:
                    continue
                loc = cast(int, ohlcv.index.get_loc(candle_ts))
                s.iloc[loc] = (
                    ohlcv["low"].iloc[loc] * 0.9995
                    if direction == 1
                    else ohlcv["high"].iloc[loc] * 1.0005
                )
            return s

        long_s = _make_series(opens, 1)
        short_s = _make_series(opens, -1)

        close_s = pd.Series(np.nan, index=ohlcv.index)
        forced_s = pd.Series(np.nan, index=ohlcv.index)
        for _, row in closes.iterrows():
            candle_ts = _bin_time(row["time"])
            if candle_ts is None:
                continue
            loc = cast(int, ohlcv.index.get_loc(candle_ts))
            if row["type"] in ("forced_close", "stop_close"):
                forced_s.iloc[loc] = ohlcv["close"].iloc[loc]
            else:
                close_s.iloc[loc] = ohlcv["close"].iloc[loc]

        if long_s is not None and long_s.notna().any():
            addplots.append(
                mpf.make_addplot(
                    long_s, type="scatter", markersize=80, marker="^", color=LONG_COLOR
                )
            )
        if short_s is not None and short_s.notna().any():
            addplots.append(
                mpf.make_addplot(
                    short_s, type="scatter", markersize=80, marker="v", color=SHORT_COLOR
                )
            )
        if close_s.notna().any():
            addplots.append(
                mpf.make_addplot(
                    close_s, type="scatter", markersize=50, marker="x", color=CLOSE_COLOR
                )
            )
        if forced_s.notna().any():
            addplots.append(
                mpf.make_addplot(
                    forced_s, type="scatter", markersize=80, marker="X", color=BREACH_COLOR
                )
            )

    mc = mpf.make_marketcolors(
        up=LONG_COLOR, down=SHORT_COLOR, edge="inherit", wick="inherit", volume="in"
    )
    s = mpf.make_mpf_style(
        base_mpf_style="yahoo",
        marketcolors=mc,
        facecolor="#ffffff",
        figcolor="#ffffff",
        gridcolor="#e6e6e6",
        gridstyle="--",
    )

    save_kwargs: dict[str, Any] = {}
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        save_kwargs["savefig"] = dict(fname=str(out_path), dpi=dpi, bbox_inches="tight")

    plot_kwargs: dict[str, Any] = {
        "type": "candle",
        "style": s,
        "title": "Price + Orders",
        "warn_too_much_data": len(ohlcv) + 1,
        "returnfig": True,
        **save_kwargs,
    }
    if addplots:
        plot_kwargs["addplot"] = addplots

    fig_any, _ = mpf.plot(ohlcv, **plot_kwargs)
    fig = cast(Figure, fig_any)
    plt.close(fig)
    return fig


def _plot_price_line_fallback(
    bars: pd.DataFrame,
    trades: pd.DataFrame | None,
    max_points: int,
    out_path: Path | str | None,
    dpi: int,
) -> Figure:
    """Fallback to a simple line chart when mplfinance is not installed."""
    _apply_style()
    close = bars["close"].copy()
    if len(close) > max_points:
        close = close.iloc[-max_points:]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(close.index, close.to_numpy(), color=EQUITY_COLOR, linewidth=0.8, label="Close")

    if trades is not None and not trades.empty and "time" in trades.columns:
        opens = trades[trades["type"] == "open"]
        long_opens = (
            opens[opens.get("direction", pd.Series()) == 1]
            if "direction" in opens.columns
            else pd.DataFrame()
        )
        short_opens = (
            opens[opens.get("direction", pd.Series()) == -1]
            if "direction" in opens.columns
            else pd.DataFrame()
        )
        closes = trades[
            trades["type"].isin(["close", "forced_close", "eod_close", "stop_close", "tp_close"])
        ]

        if not long_opens.empty:
            ax.scatter(
                long_opens["time"],
                long_opens["price"]
                if "price" in long_opens.columns
                else close.reindex(long_opens["time"], method="nearest").to_numpy(),
                marker="^",
                color=LONG_COLOR,
                s=40,
                label="Long",
                zorder=5,
            )
        if not short_opens.empty:
            ax.scatter(
                short_opens["time"],
                short_opens["price"]
                if "price" in short_opens.columns
                else close.reindex(short_opens["time"], method="nearest").to_numpy(),
                marker="v",
                color=SHORT_COLOR,
                s=40,
                label="Short",
                zorder=5,
            )
        if not closes.empty and "equity" in closes.columns:
            close_prices = close.reindex(closes["time"], method="nearest")
            ax.scatter(
                closes["time"],
                close_prices.to_numpy(),
                marker="x",
                color=CLOSE_COLOR,
                s=30,
                label="Close",
                zorder=5,
            )

    ax.set_title("Price + Orders", fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.legend(fontsize=8)
    ax.grid(True)
    fig.autofmt_xdate()
    fig.tight_layout()

    if out_path:
        _save(fig, out_path, dpi)
    return fig


def _per_trade_equity(
    pairs: list[tuple[pd.Series, pd.Series]],
    equity: pd.Series,
) -> tuple[pd.DatetimeIndex, np.ndarray[Any, Any]]:
    """Equity after each completed trade.

    Prefer the close-row ``equity`` from the trade log (authoritative). Only
    fall back to reindexing the continuous equity series when that column is
    missing — reindex is unsafe when equity timestamps were misaligned.
    """
    # Trades can combine timestamps emitted by different market-data paths,
    # some naive and some timezone-aware. Normalize them before constructing
    # the index so report export remains robust across both paths.
    times = pd.to_datetime([c["time"] for _, c in pairs], utc=True, format="mixed")
    vals = np.empty(len(pairs), dtype=float)
    need_fallback = False
    for i, (_, close_row) in enumerate(pairs):
        if "equity" in close_row.index and pd.notna(close_row["equity"]):
            vals[i] = float(close_row["equity"])
        else:
            vals[i] = np.nan
            need_fallback = True
    if need_fallback:
        filled = equity.reindex(times).ffill().bfill()
        miss = np.isnan(vals)
        vals[miss] = np.asarray(filled.to_numpy(dtype=float))[miss]
    return pd.DatetimeIndex(times), vals


def _candle_body_days(index: pd.DatetimeIndex) -> float:
    """Body width of one bar, in matplotlib day units."""
    if len(index) < 2:
        step = pd.Timedelta("1min")
    else:
        deltas = index[1:] - index[:-1]
        positive = deltas[deltas > pd.Timedelta(0)]
        step = pd.Timedelta(pd.Series(positive).median()) if len(positive) else pd.Timedelta("1min")
        if step <= pd.Timedelta(0):
            step = pd.Timedelta("1min")
    return float(step / pd.Timedelta("1D"))


def _axis_date_format(window: pd.DataFrame) -> str:
    """``%H:%M`` for a single calendar day; include month/day otherwise."""
    idx = pd.DatetimeIndex(window.index)
    if len(idx) == 0:
        return "%H:%M"
    days = idx.normalize().unique()
    return "%H:%M" if len(days) == 1 else "%m/%d %H:%M"


def _close_time_label(t_open: pd.Timestamp, t_close: pd.Timestamp) -> str:
    """Close time for chart titles; include the date when it differs from open."""
    if pd.Timestamp(t_open).normalize() == pd.Timestamp(t_close).normalize():
        return pd.Timestamp(t_close).strftime("%H:%M")
    return pd.Timestamp(t_close).strftime("%Y-%m-%d %H:%M")


def _trade_filename(
    idx: int,
    open_row: pd.Series,
    close_row: pd.Series,
    ext: str,
    *,
    pnl_override: float | None = None,
) -> str:
    """Build a descriptive filename for a per-trade chart.

    Format: ``trade_NNNN_YYYYMMDD_HHMMopen_HHMMclose_{L|S}_{p|m}PnL.{ext}``
    """
    t_open = pd.Timestamp(open_row["time"])
    t_close = pd.Timestamp(close_row["time"])
    date = t_open.strftime("%Y%m%d")
    t_o = t_open.strftime("%H%M")
    t_c = t_close.strftime("%H%M")
    side = "L" if open_row.get("direction", 0) == 1 else "S"
    pnl = (
        float(pnl_override)
        if pnl_override is not None
        else (float(close_row["pnl"]) if pd.notna(close_row.get("pnl")) else 0.0)
    )
    sign = "p" if pnl >= 0 else "m"
    return f"trade_{idx:04d}_{date}_{t_o}_{t_c}_{side}_{sign}{abs(pnl):.1f}.{ext}"


_EXIT_TYPES = {"tp_partial_close", "close", "forced_close", "eod_close", "stop_close", "tp_close"}


def _position_events(
    trades: pd.DataFrame,
    open_row: pd.Series,
    close_row: pd.Series,
    *,
    breakeven_buffer_pts: float = 0.0,
) -> pd.DataFrame:
    """Return lifecycle rows for one position, including partials and SL changes."""
    position_id = open_row.get("position_id")
    if position_id is not None and pd.notna(position_id) and "position_id" in trades.columns:
        events: pd.DataFrame = trades.loc[trades["position_id"] == position_id].copy()
    else:
        events = pd.DataFrame([open_row.to_dict(), close_row.to_dict()])
    # Old trade ledgers did not emit the automatic post-partial stop update.
    # Reconstruct it only when the run's saved config supplies a positive
    # buffer, and label it as reconstructed in the chart note.
    if (
        breakeven_buffer_pts > 0.0
        and "type" in events
        and not events["type"].eq("sl_update").any()
        and events["type"].eq("tp_partial_close").any()
        and pd.notna(open_row.get("sl_price"))
        and pd.notna(open_row.get("price"))
    ):
        direction = int(open_row.get("direction", 0))
        entry = float(open_row["price"])
        initial_sl = float(open_row["sl_price"])
        stop = entry + direction * breakeven_buffer_pts
        tightens = stop > initial_sl if direction == 1 else stop < initial_sl
        if direction in (-1, 1) and tightens:
            partial = events.loc[events["type"].eq("tp_partial_close")].iloc[0]
            reconstructed: dict[str, object] = {column: None for column in events.columns}
            reconstructed.update(
                {
                    "type": "sl_update",
                    "position_id": open_row.get("position_id"),
                    "time": partial.get("time"),
                    "effective_time": partial.get("actual_tick_time", partial.get("time")),
                    "direction": direction,
                    "previous_price": initial_sl,
                    "price": stop,
                    "reference": "entry",
                    "reference_price": entry,
                    "reason": "post_partial_breakeven_reconstructed_from_config",
                }
            )
            events = pd.concat([events, pd.DataFrame([reconstructed])], ignore_index=True)
    if "bar" in events.columns:
        events = events.sort_values("bar", kind="stable")
    elif "time" in events.columns:
        events = events.sort_values("time", kind="stable")
    return events


def _position_pnl_from_fills(
    events: pd.DataFrame, direction: int, entry: float, initial_lots: float, contract: float
) -> float:
    exits = events.loc[events["type"].isin(_EXIT_TYPES)]
    logged = (
        pd.to_numeric(exits["pnl"], errors="coerce")
        if "pnl" in exits.columns
        else pd.Series(dtype=float)
    )
    if logged.notna().any():
        return float(logged.fillna(0.0).sum())
    if "price" not in exits or "size" not in exits:
        return 0.0
    return float(((exits["price"] - entry) * direction * exits["size"] * contract).sum())


def _clock_label(value: object) -> str:
    text = str(value)
    return text[11:23] if len(text) >= 19 else text


def _draw_position_fills(ax: Any, events: pd.DataFrame) -> None:
    """Mark actual logged partial/final fills and stop changes distinctly."""
    for _, event in events.iterrows():
        event_type = event.get("type")
        if event_type in _EXIT_TYPES:
            when, price = event.get("time"), event.get("price")
            if pd.notna(when) and pd.notna(price):
                partial = event_type == "tp_partial_close"
                ax.scatter(
                    [pd.Timestamp(when)],
                    [float(price)],
                    marker="s" if partial else "X",
                    s=36,
                    color="#00897b" if partial else "#c62828",
                    zorder=8,
                    label="Partial exit fill" if partial else "Final exit fill",
                )


def _draw_target_updates(ax: Any, events: pd.DataFrame) -> None:
    """Show changed structural targets through their matching partial fill."""
    if "type" not in events or "tp_slot" not in events:
        return
    updates = events.loc[events["type"].eq("tp_update")]
    for update_i, (_, update) in enumerate(updates.iterrows()):
        slot = update.get("tp_slot")
        matches = events.loc[
            events["type"].eq("tp_partial_close") & (events["tp_slot"].astype(str) == str(slot))
        ]
        start_value = update.get("effective_time", update.get("time"))
        if pd.isna(start_value) or pd.isna(update.get("price")):
            continue
        start = pd.Timestamp(start_value)
        matching_times = matches["time"].dropna() if "time" in matches else pd.Series(dtype=object)
        event_times = events["time"].dropna() if "time" in events else pd.Series(dtype=object)
        if not matching_times.empty:
            end = pd.Timestamp(matching_times.iloc[0])
        elif not event_times.empty:
            end = pd.Timestamp(event_times.iloc[-1])
        else:
            # A malformed or incomplete close timestamp should not prevent
            # the valid target update itself from being rendered.
            end = start
        price = float(update["price"])
        ax.plot(
            [start, end],
            [price, price],
            color="#00897b",
            linewidth=1.3,
            linestyle="--",
            zorder=6,
            label="Updated take-profit level" if update_i == 0 else None,
        )
        ax.scatter([start], [price], marker="s", s=28, color="#00897b", zorder=8)
        ax.annotate(
            f"TP {slot} updated {price:.2f}",
            xy=(start, price),
            xytext=(5, 7),
            textcoords="offset points",
            fontsize=7,
            color="#00695c",
        )


def plot_per_trade_orders(
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    orders_dir: Path | str,
    context_bars: int = 60,
    max_charts: int = 200,
    dpi: int = 150,
    max_loss_per_trade_usd: float | None = None,
    take_profit_per_trade_usd: float | None = None,
    lots: float = 1.0,
    contract_size: float = 1.0,
    show_mae_mfe: bool = True,
    show_sl_tp: bool = True,
    show_vwap: bool = False,
    secondary_bars: pd.DataFrame | None = None,
    features: pd.DataFrame | None = None,
    breakeven_buffer_pts: float = 0.0,
    order_block_timeframes: tuple[str, ...] = (),
    fvg_timeframes: tuple[str, ...] = (),
    ifvg_timeframes: tuple[str, ...] = (),
    ema_timeframes: tuple[str, ...] = ("M1",),
    swing_timeframes: tuple[str, ...] = ("M1",),
    entry_idea_plot_config: dict[str, Any] | None = None,
) -> None:
    """Generate 2-panel PNG per trade with datetime axes, EMA50, MACD, and trade info.

    Filenames encode the key trade metadata::

        trade_NNNN_YYYYMMDD_HHMMopen_HHMMclose_{L|S}_{p|m}PnL.png

    Parameters
    ----------
    bars : M1 price bars (DatetimeIndex, open/high/low/close columns).
    trades : Trade log with type/direction/price/time/pnl columns.
    orders_dir : Destination folder; created if absent.
    context_bars : M1 bars to show before entry and after exit (~1 min each).
    max_charts : Cap on number of charts; trades are sampled evenly when
        the total exceeds this limit.
    dpi : PNG resolution.
    max_loss_per_trade_usd : Maximum loss limit for SL calculation.
    take_profit_per_trade_usd : Take profit limit for TP calculation.
    lots : Position size in lots.
    contract_size : Contract size.
    show_mae_mfe : Whether to plot MAE/MFE lines.
    show_sl_tp : Whether to plot SL/TP lines.
    show_vwap : Draw session VWAP. Off until the feed has real tick volume.
    secondary_bars : Optional US500 (or correlated) bars for SMT lines.
    """

    from evaluation.reporting.trade_note import build_trade_plot_note

    from .chart_indicators import (
        break_overlay_gaps,
        compute_chart_overlays_full,
        compute_mtf_ema_overlays,
        select_ema_overlays,
    )
    from .chart_overlays import (
        VWAP_COLOR,
        build_overlay_events,
        draw_macd_rsi_mpl,
        draw_overlays_mpl,
    )
    from .order_chart_renderers import draw_order_levels_mpl
    from .order_window import _session_end_positions, prepare_order_chart
    from .overlay_events import candidate_sweep_line, confirmed_pivots

    orders_dir = Path(orders_dir)
    orders_dir.mkdir(parents=True, exist_ok=True)
    trades = trades.copy()

    # Normalize event and tick timestamps to the candle index timezone before
    # creating markers or captions. R1 ledgers store tick instants in UTC while
    # their minute bars are in the configured local market timezone.
    if isinstance(bars.index, pd.DatetimeIndex) and bars.index.tz is not None:
        for column in ("time", "actual_tick_time", "fill_time", "effective_time"):
            if column not in trades.columns:
                continue
            timestamps = pd.to_datetime(trades[column], errors="coerce", utc=True)
            trades[column] = timestamps.dt.tz_convert(bars.index.tz)

    # Older ledgers recorded the candidate's bar but not its timestamp. Recover
    # the source candle directly from the run's bar index so the chart caption
    # can distinguish setup time from the later policy trigger.
    if "entry_origin_time" not in trades.columns:
        trades["entry_origin_time"] = pd.NaT
    if {"type", "entry_origin_bar"}.issubset(trades.columns):
        open_rows = trades["type"].astype(str).eq("open")
        origin_bars = pd.to_numeric(trades["entry_origin_bar"], errors="coerce")
        for row_index in trades.index[open_rows & origin_bars.notna()]:
            if pd.notna(trades.at[row_index, "entry_origin_time"]):
                continue
            origin_bar = int(float(cast(Any, origin_bars.at[row_index])))
            if 0 <= origin_bar < len(bars.index):
                trades.at[row_index, "entry_origin_time"] = bars.index[origin_bar]

    pairs = _pair_trades(trades)
    if not pairs:
        return

    total = len(pairs)
    if total > max_charts:
        indices = np.linspace(0, total - 1, max_charts, dtype=int).tolist()
        pairs = [pairs[i] for i in indices]
        log.info("Per-trade PNG: sampling %d/%d trades → %s", max_charts, total, orders_dir)
    else:
        log.info("Per-trade PNG: %d charts → %s", total, orders_dir)

    # Compute EMA50/MACD/RSI/VWAP once on the full history so indicators are
    # warmed up and match the strategy's real signals, then slice per trade.
    full_overlays = compute_chart_overlays_full(bars)
    full_overlays.update(compute_mtf_ema_overlays(bars, ema_timeframes))
    full_overlays = select_ema_overlays(full_overlays, ema_timeframes)
    overlay_events = build_overlay_events(bars, secondary=secondary_bars)
    confirmed_events = confirmed_pivots(overlay_events, bars)
    if "M1" not in {str(tf).upper() for tf in swing_timeframes}:
        confirmed_events.swings = []
    session_end_positions = _session_end_positions(pd.DatetimeIndex(bars.index))

    for seq_i, (open_row, close_row) in enumerate(pairs):
        prepared = prepare_order_chart(
            bars,
            open_row,
            close_row,
            overlay_events=overlay_events,
            full_overlays=full_overlays,
            context_bars=context_bars,
            max_loss_per_trade_usd=max_loss_per_trade_usd,
            take_profit_per_trade_usd=take_profit_per_trade_usd,
            lots=lots,
            contract_size=contract_size,
            show_mae_mfe=show_mae_mfe,
            show_sl_tp=show_sl_tp,
            features=features,
            order_block_timeframes=order_block_timeframes,
            fvg_timeframes=fvg_timeframes,
            ifvg_timeframes=ifvg_timeframes,
            swing_timeframes=swing_timeframes,
            entry_idea_plot_config=entry_idea_plot_config,
            confirmed_events=confirmed_events,
            session_end_positions=session_end_positions,
        )
        if prepared is None:
            continue
        window = prepared.window
        metrics = prepared.metrics
        overlays = prepared.overlays
        levels = prepared.levels
        events = prepared.events
        t_open = prepared.t_open
        t_close = prepared.t_close
        close_row_for_plot = close_row.copy()
        close_row_for_plot["time"] = t_close
        selected_sweep = candidate_sweep_line(bars, open_row, features, events)
        if selected_sweep is None or not (
            window.index[0] <= selected_sweep.t0 <= window.index[-1]
            and window.index[0] <= selected_sweep.t1 <= window.index[-1]
        ):
            events.sweeps = []
        else:
            events.sweeps = [selected_sweep]
        overlays = break_overlay_gaps(overlays)

        direction = int(open_row["direction"]) if pd.notna(open_row.get("direction")) else 0
        position_events = _position_events(
            trades,
            open_row,
            close_row,
            breakeven_buffer_pts=breakeven_buffer_pts,
        )
        pnl = _position_pnl_from_fills(
            position_events,
            direction,
            metrics.entry_price,
            float(open_row.get("lots", lots) or lots),
            contract_size,
        )
        close_type = str(close_row["type"])

        # Create 2-panel figure: price + dual-axis MACD/RSI
        fig, (ax_price, ax_osc) = plt.subplots(
            2,
            1,
            figsize=(14, 9),
            gridspec_kw={"height_ratios": [2, 1]},
            sharex=True,
        )

        # --- Top panel: Candlesticks + EMA50 + Entry/Exit + MAE/MFE/SL/TP ---
        colors_up = [
            LONG_COLOR if o <= c else SHORT_COLOR for o, c in zip(window["open"], window["close"])
        ]

        body_width = _candle_body_days(pd.DatetimeIndex(window.index))
        for i, (idx, row) in enumerate(window.iterrows()):
            hl_color = colors_up[i]
            # High-low line
            ax_price.plot(
                [idx, idx],
                [row["low"], row["high"]],
                color=hl_color,
                linewidth=0.5,
            )
            # Open-close body
            body_height = abs(row["close"] - row["open"])
            body_bottom = min(row["open"], row["close"])
            x0 = mdates.date2num(cast(pd.Timestamp, idx)) - body_width / 2
            rect = Rectangle(
                (x0, body_bottom),
                body_width,
                body_height,
                facecolor=hl_color,
                edgecolor=hl_color,
                linewidth=0.8,
            )
            ax_price.add_patch(rect)

        # EMA50
        ema = overlays.get("ema50")
        if ema is not None:
            ax_price.plot(
                ema.index,
                ema.to_numpy(),
                color="#0066cc",
                linewidth=2,
                label="M1 EMA 50",
                zorder=3,
            )
        # Keep the chart readable: the feature set retains all EMA periods,
        # while trade charts show only the two requested context lines.
        ema_colors = {21: "#6a1b9a", 50: "#0066cc"}
        for timeframe in ema_timeframes:
            tf = str(timeframe).upper()
            for period, color in ema_colors.items():
                key = f"{tf}_ema_{period}"
                if key not in overlays or (tf == "M1" and period == 50):
                    continue
                ax_price.plot(
                    overlays[key].index,
                    overlays[key].to_numpy(),
                    color=color,
                    linewidth=1.1,
                    label=f"{tf} EMA {period}",
                    zorder=3,
                )
        if show_vwap:
            vwap = overlays["vwap"]
            ax_price.plot(
                vwap.index,
                vwap.to_numpy(),
                color=VWAP_COLOR,
                linewidth=1.7,
                linestyle="-.",
                label="VWAP",
                zorder=3,
            )
        draw_overlays_mpl(ax_price, events)
        draw_order_levels_mpl(ax_price, levels, position_events)
        _draw_position_fills(ax_price, position_events)
        _draw_target_updates(ax_price, position_events)
        # Structure lines must not stretch a one-minute trade across later months.
        pad = float(pd.Timedelta("30s") / pd.Timedelta("1D"))
        ax_price.set_xlim(
            mdates.date2num(pd.Timestamp(window.index[0])) - pad,
            mdates.date2num(pd.Timestamp(window.index[-1])) + pad,
        )

        # Formatting
        ax_price.set_ylabel("Price")
        ax_price.grid(True, alpha=0.3)

        # Format x-axis in the bars' own timezone. Use month/day when the
        # window spans multiple calendar days so labels cannot collide.
        axis_tz = pd.DatetimeIndex(window.index).tz
        date_fmt = _axis_date_format(window)
        ax_price.xaxis.set_major_formatter(mdates.DateFormatter(date_fmt, tz=axis_tz))
        ax_price.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=12))
        plt.setp(ax_price.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # --- Bottom panel: MACD (left) + RSI (right) ---
        ax_rsi = draw_macd_rsi_mpl(ax_osc, window, overlays)
        legend_handles: list[Any] = []
        legend_labels: list[str] = []
        for legend_axis in (ax_price, ax_osc, ax_rsi):
            handles, labels = legend_axis.get_legend_handles_labels()
            for handle, label in zip(handles, labels, strict=False):
                if label and not label.startswith("_") and label not in legend_labels:
                    legend_handles.append(handle)
                    legend_labels.append(label)
            legend = legend_axis.get_legend()
            if legend is not None:
                legend.remove()
        if legend_handles:
            fig.legend(
                legend_handles,
                legend_labels,
                loc="lower center",
                bbox_to_anchor=(0.5, 0.015),
                ncol=min(6, len(legend_labels)),
                fontsize=7,
                frameon=True,
            )
        ax_osc.set_xlabel("Time (M1)")
        ax_osc.xaxis.set_major_formatter(mdates.DateFormatter(date_fmt, tz=axis_tz))
        ax_osc.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=12))
        plt.setp(ax_osc.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # --- Compact trade note inside the price panel ---
        lots_val = float(open_row.get("lots", 1.0)) if pd.notna(open_row.get("lots")) else 1.0
        close_reason_detail = (
            str(close_row.get("reason")) if pd.notna(close_row.get("reason")) else close_type
        )

        note_lines = build_trade_plot_note(
            open_row,
            close_row,
            entry_price=metrics.entry_price,
            exit_price=metrics.exit_price,
            direction=direction,
            pnl=pnl,
            lots=lots_val,
            close_reason_detail=close_reason_detail,
            position_events=position_events,
            signal_time=open_row.get("signal_time", open_row.get("decision_time")),
            entry_fill_time=open_row.get("actual_tick_time", open_row.get("time")),
        )
        ax_price.text(
            0.99,
            0.985,
            "\n".join(note_lines),
            transform=ax_price.transAxes,
            fontsize=_NOTE_FONT_PT,
            family="monospace",
            ha="right",
            va="top",
            zorder=20,
            clip_on=True,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "alpha": 0.9},
        )

        # --- Title ---
        dir_label = "Long" if direction == 1 else "Short"
        close_reason = close_type if close_type != "close" else "normal"
        title = (
            f"{dir_label} | Open {t_open.strftime('%Y-%m-%d %H:%M')} "
            f"→ Close {_close_time_label(t_open, t_close)} | "
            f"PnL: {pnl:+.2f} | {close_reason}"
        )
        fig.suptitle(title, fontsize=11, fontweight="bold")

        # Save
        fname = _trade_filename(seq_i + 1, open_row, close_row_for_plot, "png", pnl_override=pnl)
        try:
            fig.tight_layout(rect=(0.008, 0.14, 0.995, 0.94))
            fig.savefig(str(orders_dir / fname), dpi=dpi, bbox_inches="tight")
            plt.close(fig)
        except Exception as exc:
            log.debug("Skipping per-trade PNG %d: %s", seq_i + 1, exc)
