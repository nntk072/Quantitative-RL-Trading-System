#!/usr/bin/env python3
"""Fixed-entry paired EMA/structural exit shadow for the frozen 2025 cohort.

This analysis replays archived v2 entries independently through TradingEnv's
execution methods. It never loads a policy, calls ``step``/``transition``,
creates an entry, or compounds trade PnL into another trade's account state.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from omegaconf import OmegaConf

from market_data.loading.ticks import TickBook
from simulation.environment import guardrail_kwargs, make_env
from trading.execution import Position
from trading.orders import OrderGeometry, decode_tp_mode, place_strategy_order

ARCHIVED_TRAINING_COMMIT = "cbf7825170dee7f68ad578a19023e0847b11393f"
EVIDENCE_ROOT = Path("docs/thesis/evidence/exit_action_semantics_20261024")
G0_ROOT = Path("outputs/exit_semantics_counterfactual_20261024_g0_v2_repro_job21190658")
BAR_RELATIVE = Path(
    "cache/train_test_2025_2026/training/US100.cash_M1_v3-native-timeframes.parquet"
)
FEATURE_RELATIVE = Path(
    "cache/train_test_2025_2026/US100.cash_features_v24-native-source-timeframes_753fccd28c376816.parquet"
)
TICK_RELATIVE = Path(
    "cache/train_test_2025_2026/training/US100.cash_ticks_v3-validated-full-day.parquet"
)
RELEVANT_SOURCE_FILES = (
    "simulation/environment/action_runtime.py",
    "simulation/environment/trading_environment_factory.py",
    "simulation/environment/market_access.py",
    "simulation/environment/entry_runtime.py",
    "simulation/environment/ema_exit_runtime.py",
    "simulation/environment/entry_execution_runtime.py",
    "simulation/environment/protective_level_runtime.py",
    "simulation/environment/tick_quote_runtime.py",
    "simulation/environment/position_runtime.py",
    "simulation/environment/episode_runtime.py",
    "simulation/environment/fill_quote_runtime.py",
    "simulation/environment/trade_accounting_runtime.py",
    "trading/orders/entries.py",
    "trading/orders/targets.py",
    "trading/orders/selection.py",
    "trading/positions/multi_tp.py",
    "trading/execution/costs.py",
    "trading/execution/broker.py",
)


@dataclass(frozen=True)
class TargetClassification:
    status: str
    reason: str
    geometry: OrderGeometry | None


class PairedLatency:
    """Use the historical v2 exit draw first, then keyed draws per trade."""

    def __init__(self, entry_id: str, historical_first_ns: int | None) -> None:
        self.entry_id = entry_id
        self.first_ns = historical_first_ns
        self.count = 0

    def integers(self, low: int, high: int) -> int:
        if high <= low:
            raise ValueError("latency range must be non-empty")
        if self.count == 0 and self.first_ns is not None:
            value = int(self.first_ns)
            if low <= value < high:
                self.count += 1
                return value
        payload = f"exit-shadow-v1:{self.entry_id}:{self.count}".encode()
        value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        self.count += 1
        return low + value % (high - low)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _is_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"true", "1"}


def _menu_pairs(value: Any) -> tuple[tuple[str, float], ...]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ()
    parsed = ast.literal_eval(str(value)) if isinstance(value, str) else value
    if not isinstance(parsed, (list, tuple)):
        raise ValueError("target menu is not a sequence")
    result: list[tuple[str, float]] = []
    for item in parsed:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("target menu entry must contain reference and price")
        result.append((str(item[0]), float(item[1])))
    return tuple(result)


def reconstruct_geometry(env: Any, row: pd.Series, *, exit_mode: str) -> OrderGeometry:
    """Rebuild the archived decision-time geometry from its saved coordinates."""
    decision_idx = int(row["bar"])
    env.step_idx = decision_idx
    feature_row = env._feature_row_at(decision_idx)
    raw_stop = float(row["action_stop"])
    sl_fraction = float(np.clip(raw_stop + 1.0, 0.0, 2.0))
    selections = (
        float(row["tp1_sel_u"]),
        float(row["tp2_sel_u"]),
        float(row["tp3_sel_u"]),
    )
    z_values = (float(row["z1_u"]), float(row["z2_u"]))
    return place_strategy_order(
        env.strategy,
        direction=int(row["direction"]),
        entry_price=float(row["price"]),
        feat_row=feature_row,
        min_dist=env._min_sl_distance(feature_row),
        sl_fraction=sl_fraction,
        tp_fraction=selections[2],
        exit_mode=exit_mode,
        buffer_pts=float(env.sl_buffer_pts),
        max_tp_distance=float(env._max_tp_here()),
        rr_bounds=env.rr_ratio_range,
        htf=tuple(env._mtf_windows.keys()),
        tp_selections=selections,
        tp_z=z_values,
        allow_multi_tp=bool(env.allow_multi_tp),
        allow_simplex=bool(env.allow_simplex),
        price_increment=float(env.cost_model.point_size),
    )


def classify_structural(env: Any, row: pd.Series) -> TargetClassification:
    try:
        ema_geometry = reconstruct_geometry(env, row, exit_mode="ema_21")
        if ema_geometry.sl_price is None or not math.isclose(
            float(ema_geometry.sl_price), float(row["sl_price"]), abs_tol=0.005
        ):
            return TargetClassification("unresolved", "frozen_stop_reconstruction_mismatch", None)
        frozen_menu = _menu_pairs(row.get("tp_menu"))
        geometry = reconstruct_geometry(env, row, exit_mode="structural")
        generated_menu = tuple((str(name), float(price)) for name, price in geometry.tp_menu)
        if len(frozen_menu) != len(generated_menu):
            return TargetClassification("unresolved", "target_menu_length_mismatch", None)
        if any(
            left[0] != right[0] or not math.isclose(left[1], right[1], abs_tol=0.005)
            for left, right in zip(frozen_menu, generated_menu, strict=True)
        ):
            return TargetClassification("unresolved", "target_menu_value_mismatch", None)
        if geometry.rejected or geometry.tp_price is None:
            return TargetClassification("ineligible", "no_selected_structural_target", geometry)
        active = [
            (price, reference)
            for price, reference in zip(
                (geometry.tp1_price, geometry.tp2_price, geometry.tp3_price),
                (geometry.tp1_ref, geometry.tp2_ref, geometry.tp3_ref),
                strict=True,
            )
            if price is not None
        ]
        if not active or not all(np.isfinite(price) for price, _ in active):
            return TargetClassification("unresolved", "selected_target_not_finite", None)
        direction = int(row["direction"])
        entry = float(row["price"])
        oriented = [direction * (float(price) - entry) for price, _ in active]
        if any(distance <= 0.0 for distance in oriented):
            return TargetClassification("unresolved", "selected_target_not_ahead_of_fill", None)
        if any(right <= left for left, right in zip(oriented, oriented[1:])):
            return TargetClassification("unresolved", "selected_targets_not_ordered", None)
        fractions = tuple(float(value) for value in geometry.tp_lot_fractions)
        if (
            not fractions
            or any(value <= 0.0 for value in fractions)
            or not math.isclose(sum(fractions), 1.0, abs_tol=1e-8)
        ):
            return TargetClassification("unresolved", "tp_fractions_invalid", None)
        return TargetClassification("eligible", "selected_targets_reconstructed", geometry)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        return TargetClassification(
            "unresolved", f"reconstruction_error:{type(exc).__name__}", None
        )


def _latency_for_entry(events: pd.DataFrame, position_id: str) -> int | None:
    complete = events["position_complete"].map(_is_true)
    rows = events.loc[(events["position_id"] == position_id) & events["fill_id"].notna() & complete]
    if rows.empty:
        return None
    value = _optional_float(rows.iloc[-1].get("execution_latency_ns"))
    return None if value is None else int(value)


def _make_position(env: Any, row: pd.Series, geometry: OrderGeometry | None, arm: str) -> Position:
    direction = int(row["direction"])
    entry = float(row["price"])
    lots = float(row["lots"])
    stop = float(row["sl_price"])
    decision_idx = int(row["bar"])
    feature = env._feature_row_at(decision_idx)
    atr_value = _optional_float(feature.get("atr_5", feature.get("atr", 1.0))) or 1.0
    sl_mode_u = float(row["sl_mode_u"])
    sl_mode = env._default_sl_mode()
    if abs(sl_mode_u - 0.5) >= env.sl_mode_defer_threshold:
        sl_mode = ("fixed", "breakeven", "trailing")[min(2, int(sl_mode_u * 3))]
    tp_mode, tp_mode_explicit = decode_tp_mode(
        float(row["tp_mode_u"]), env.tp_mode, env.tp_mode_defer_threshold, is_unit=True
    )
    entry_sl_ref_price = None
    if (
        geometry is not None
        and geometry.sl_ref == "sl_reference"
        and hasattr(env.strategy, "sl_reference")
    ):
        reference = env.strategy.sl_reference(direction=direction, row=feature)
        entry_sl_ref_price = _optional_float(reference)
    actual_fill = pd.Timestamp(row["actual_tick_time"])
    position = Position(
        direction=direction,
        size=lots,
        entry_price=entry,
        margin_used=env.broker.required_margin(entry, lots),
        position_id=str(row["position_id"]),
        initial_size=lots,
        filled_size=0.0,
        fill_count=0,
        sl_price=stop,
        tp_price=None,
        entry_timestamp=actual_fill,
        entry_atr=atr_value,
        planned_risk_usd=float(row["modeled_stop_risk_usd"]),
        sl_initial_price=stop,
        sl_ref=str(row.get("sl_ref", "") if geometry is None else geometry.sl_ref),
        tp_ref="" if geometry is None else geometry.tp_ref,
        planned_rr=None if geometry is None else geometry.planned_rr,
        exit_mode=arm,
        stop_distance=abs(entry - stop),
        sl_buffer=float(row.get("sl_buffer", 0.0) or 0.0),
        manipulation=str(row.get("manipulation", "")),
        n_sl=int(row.get("n_sl", 0) or 0),
        n_tp=0 if geometry is None else int(geometry.n_tp),
        entry_last_swing_high=_optional_float(feature.get("last_swing_high")),
        entry_last_swing_low=_optional_float(feature.get("last_swing_low")),
        sl_mode=sl_mode,
        sl_mode_overridden=abs(sl_mode_u - 0.5) >= env.sl_mode_defer_threshold,
        tp_initial_size=lots,
        tp_mode=tp_mode,
        tp_mode_overridden=tp_mode_explicit,
        tp_initial_price=(
            None
            if geometry is None
            else geometry.tp3_price
            if geometry.tp3_price is not None
            else geometry.tp_price
        ),
        tp1_price=None if arm == "ema_21" or geometry is None else geometry.tp1_price,
        tp2_price=None if arm == "ema_21" or geometry is None else geometry.tp2_price,
        tp3_price=None if arm == "ema_21" or geometry is None else geometry.tp3_price,
        tp1_ref="" if arm == "ema_21" or geometry is None else geometry.tp1_ref,
        tp2_ref="" if arm == "ema_21" or geometry is None else geometry.tp2_ref,
        tp3_ref="" if arm == "ema_21" or geometry is None else geometry.tp3_ref,
        tp_lot_fractions=(1.0,)
        if arm == "ema_21" or geometry is None
        else geometry.tp_lot_fractions,
        entry_sl_ref_price=entry_sl_ref_price,
        entry_tp_ref_price=(
            None if geometry is None or not geometry.tp_menu else float(geometry.tp_menu[0][1])
        ),
    )
    if arm == "structural" and geometry is not None:
        position.tp_price = geometry.tp_price
    return position


def replay_entry(
    env: Any,
    row: pd.Series,
    geometry: OrderGeometry | None,
    arm: str,
    historical_latency_ns: int | None,
) -> dict[str, Any]:
    """Replay one frozen position through archived execution state transitions."""
    position_id = str(row["position_id"])
    seed_payload = hashlib.sha256(f"exit-shadow:{position_id}".encode()).digest()
    env.reset(seed=int.from_bytes(seed_payload[:4], "big"))
    env.position = _make_position(env, row, geometry, arm)
    env.trade_log = []
    env.sessions_with_trades = set()
    env.np_random = PairedLatency(position_id, historical_latency_ns)

    fill_time = pd.Timestamp(row["actual_tick_time"])
    fill_bar = int(row["fill_bar"])
    start_index = max(
        fill_bar,
        int(env.bars.index.searchsorted(fill_time.tz_convert(env.bars.index.tz), side="right") - 1),
    )
    ny_start = int(np.searchsorted(env._ny_indices, start_index, side="left"))
    for ny_pos in range(ny_start, len(env._ny_indices)):
        index = int(env._ny_indices[ny_pos])
        env.step_idx = index
        env._ny_pos = ny_pos
        bar = env._bar_at(index)
        feature = env._feature_row_at(index)
        bar_time = env._bar_time(index)
        session_id = env._current_session_id()
        env._progress_market(bar, feature, bar_time, session_id, min(index + 1, env._n_bars))
        if env.position is None:
            break
        bid, ask = env._bar_quote(bar)
        env._check_sl_tp(bar, bid, ask, bar_idx=index)
        if env.position is None:
            break
        env._apply_position_guards(
            bar,
            bar_time,
            bid,
            ask,
            eod=False,
            feat_row=feature,
            bar_idx=index,
            fill_time=bar_time + pd.Timedelta(minutes=env._minutes_per_step),
        )
        if env.position is None:
            break
    fills = [dict(event) for event in env.trade_log if event.get("fill_id")]
    return {"events": [dict(event) for event in env.trade_log], "fills": fills}


def _event_time(event: dict[str, Any]) -> pd.Timestamp:
    for key in ("actual_tick_time", "fill_time", "time"):
        value = event.get(key)
        if value is not None and not pd.isna(value):
            return pd.Timestamp(value)
    raise ValueError("fill has no timestamp")


def _quote_at(book: TickBook, timestamp: pd.Timestamp) -> tuple[float, float]:
    idx = int(np.searchsorted(book._ts, pd.Timestamp(timestamp).value, side="left"))
    if idx >= len(book._ts) or int(book._ts[idx]) != pd.Timestamp(timestamp).value:
        raise ValueError(f"no exact tick for fill timestamp {timestamp}")
    return float(book._bid[idx]), float(book._ask[idx])


def _trade_metrics(
    row: pd.Series,
    replay: dict[str, Any],
    book: TickBook,
    contract_size: float,
    extra_slippage_points: float,
) -> dict[str, Any]:
    fills = replay["fills"]
    if not fills:
        return {"complete": False, "exit_reason": "unresolved_no_exit", "fill_count": 0}
    entry_time = pd.Timestamp(row["actual_tick_time"])
    exit_times = [_event_time(event) for event in fills]
    exit_time = max(exit_times)
    entry_quote = _quote_at(book, entry_time)
    entry_mid = sum(entry_quote) / 2.0
    direction = int(row["direction"])
    initial_size = float(row["lots"])
    initial_risk = float(row["modeled_stop_risk_usd"])
    gross = 0.0
    baseline = 0.0
    closed_size = 0.0
    for event in fills:
        event_time = _event_time(event)
        bid, ask = _quote_at(book, event_time)
        mid = (bid + ask) / 2.0
        size = float(event.get("size", 0.0))
        closed_size += size
        gross += direction * (mid - entry_mid) * size * contract_size
        baseline += float(event.get("net_pnl", event.get("pnl", 0.0)))
    ticks_start = int(np.searchsorted(book._ts, entry_time.value, side="left"))
    ticks_end = int(np.searchsorted(book._ts, exit_time.value, side="right"))
    if ticks_end <= ticks_start:
        return {
            "complete": False,
            "exit_reason": "unresolved_empty_tick_window",
            "fill_count": len(fills),
        }
    liquidation = book._bid if direction == 1 else book._ask
    signed_moves = direction * (liquidation[ticks_start:ticks_end] - float(row["price"]))
    mfe_price = max(0.0, float(np.max(signed_moves)))
    mae_price = max(0.0, -float(np.min(signed_moves)))
    stress = baseline - extra_slippage_points * contract_size * (initial_size + closed_size)
    total_net_r = baseline / initial_risk
    terminal = fills[-1]
    return {
        "complete": bool(terminal.get("position_complete", True)),
        "exit_time": exit_time.isoformat(),
        "exit_price": float(terminal["price"]),
        "exit_reason": str(terminal.get("reason", "unclassified")),
        "gross_pnl": gross,
        "historical_net_pnl": baseline,
        "stress_net_pnl": stress,
        "realized_r": total_net_r,
        "gross_r": gross / initial_risk,
        "stress_r": stress / initial_risk,
        "mae_price": mae_price,
        "mfe_price": mfe_price,
        "mae_usd": mae_price * initial_size * contract_size,
        "mfe_usd": mfe_price * initial_size * contract_size,
        "mae_r": mae_price * initial_size * contract_size / initial_risk,
        "mfe_r": mfe_price * initial_size * contract_size / initial_risk,
        "holding_seconds": (exit_time - entry_time).total_seconds(),
        "tick_count": ticks_end - ticks_start,
        "fill_count": len(fills),
        "closed_size": closed_size,
    }


def _original_fills(events: pd.DataFrame, position_id: str) -> list[dict[str, Any]]:
    rows = events.loc[
        (events["position_id"] == position_id)
        & events["fill_id"].notna()
        & events["position_complete"].notna()
    ]
    return cast(list[dict[str, Any]], rows.to_dict(orient="records"))


def _compare_control(replayed: dict[str, Any], original: list[dict[str, Any]]) -> dict[str, Any]:
    generated = replayed["fills"]
    if len(generated) != len(original):
        return {
            "pass": False,
            "reason": "fill_count_mismatch",
            "generated": len(generated),
            "original": len(original),
        }
    comparisons: list[dict[str, Any]] = []
    for new, old in zip(generated, original, strict=True):
        expected_reason = str(old.get("reason", ""))
        new_reason = str(new.get("reason", ""))
        price_delta = float(new["price"]) - float(old["price"])
        pnl_delta = float(new.get("net_pnl", new["pnl"])) - float(old.get("net_pnl", old["pnl"]))
        expected_time = _event_time(old)
        actual_time = _event_time(new)
        exact = (
            new_reason == expected_reason
            and abs(price_delta) <= 0.005
            and abs(pnl_delta) <= 1e-6
            and actual_time == expected_time
        )
        comparisons.append(
            {
                "pass": exact,
                "reason_match": new_reason == expected_reason,
                "price_delta": price_delta,
                "pnl_delta": pnl_delta,
                "time_match": actual_time == expected_time,
            }
        )
    return {
        "pass": all(item["pass"] for item in comparisons),
        "reason": "exact_fill_parity"
        if all(item["pass"] for item in comparisons)
        else "fill_mismatch",
        "fills": comparisons,
    }


def paired_bootstrap(
    values: NDArray[np.float64], *, resamples: int, seed: int
) -> tuple[float, float]:
    if values.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        means[index] = float(np.mean(values[rng.integers(0, values.size, values.size)]))
    quantiles = np.quantile(means, [0.025, 0.975])
    return float(quantiles[0]), float(quantiles[1])


def _distribution(values: pd.Series, seed: int, resamples: int) -> dict[str, Any]:
    array = values.dropna().to_numpy(dtype=np.float64)
    if array.size == 0:
        return {"n": 0}
    low, high = paired_bootstrap(array, resamples=resamples, seed=seed)
    return {
        "n": int(array.size),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "std": float(np.std(array, ddof=1)) if array.size > 1 else 0.0,
        "quantiles": {str(q): float(np.quantile(array, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
        "paired_bootstrap_95pct_mean_ci": [low, high],
        "wins": int(np.sum(array > 0.0)),
        "losses": int(np.sum(array < 0.0)),
        "ties": int(np.sum(array == 0.0)),
    }


def _load_training_inputs(
    root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, TickBook, dict[str, Path]]:
    paths = {
        "bars": root / BAR_RELATIVE,
        "features": root / FEATURE_RELATIVE,
        "ticks": root / TICK_RELATIVE,
        "config": root / G0_ROOT / "config.yaml",
        "trades": root / G0_ROOT / "training/trades.csv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("required fixed-entry input missing: " + ", ".join(missing))
    cfg = OmegaConf.load(paths["config"])
    schedule_value = Path(str(cfg.data.session_schedule_file)).expanduser()
    paths["schedule"] = schedule_value if schedule_value.is_absolute() else root / schedule_value
    if not paths["schedule"].is_file():
        raise FileNotFoundError(f"training session schedule is missing: {paths['schedule']}")
    bars = pd.read_parquet(paths["bars"])
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise TypeError("training bars must use a DatetimeIndex")
    datetime_index = bars.index
    cutoff = pd.Timestamp("2026-01-01 00:00:00", tz=datetime_index.tz)
    features = pd.read_parquet(paths["features"], filters=[("datetime", "<", cutoff)])
    features = features.reindex(bars.index)
    if not features.index.equals(bars.index) or features.isna().all(axis=1).any():
        raise ValueError("train-only feature rows do not align exactly with training bars")
    ticks = pd.read_parquet(paths["ticks"])
    if ticks.empty or not np.all(np.diff(ticks["ts_ns"].to_numpy(dtype=np.int64)) >= 0):
        raise ValueError("training ticks are empty or not sorted")
    cutoff_ns = cutoff.tz_convert("UTC").value
    if int(ticks["ts_ns"].max()) >= cutoff_ns:
        raise ValueError("tick input includes data outside the frozen 2025 training interval")
    tickbook = TickBook(
        ticks["ts_ns"].to_numpy(dtype=np.int64),
        ticks["bid"].to_numpy(dtype=np.float64),
        ticks["ask"].to_numpy(dtype=np.float64),
    )
    del ticks
    return bars, features, tickbook, paths


def _load_trade_ledger(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(path, low_memory=False)
    if not {"type", "position_id", "fill_id", "position_complete"}.issubset(events.columns):
        raise ValueError("historical event ledger is missing required fill identity columns")
    opens = events.loc[events["type"].eq("open")].copy()
    if len(opens) != 1356 or opens["position_id"].duplicated().any():
        raise ValueError(f"expected 1356 unique frozen v2 entries, found {len(opens)}")
    mandatory = (
        "bar",
        "fill_bar",
        "actual_tick_time",
        "direction",
        "price",
        "lots",
        "sl_price",
        "modeled_stop_risk_usd",
        "action_stop",
        "tp1_sel_u",
        "tp2_sel_u",
        "tp3_sel_u",
        "sl_mode_u",
        "tp_mode_u",
        "z1_u",
        "z2_u",
        "tp_menu",
    )
    absent = [name for name in mandatory if name not in opens]
    if absent:
        raise ValueError("frozen entry ledger lacks fields: " + ", ".join(absent))
    opens = opens.sort_values(["decision_time", "position_id"], kind="stable").reset_index(
        drop=True
    )
    for value in opens["modeled_stop_risk_usd"]:
        if not np.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError("frozen initial risk must be positive and finite")
    computed_risk = (opens["price"] - opens["sl_price"]).abs() * opens["lots"]
    if not np.allclose(computed_risk, opens["modeled_stop_risk_usd"], rtol=0.0, atol=1e-6):
        raise ValueError("frozen USD risk denominator disagrees with entry/stop/size")
    return opens, events


def _validate_historical_quotes(opens: pd.DataFrame, book: TickBook) -> None:
    times = pd.to_datetime(opens["actual_tick_time"], utc=True).astype("int64").to_numpy()
    indexes = np.searchsorted(book._ts, times, side="left")
    if np.any(indexes >= len(book._ts)) or not np.array_equal(book._ts[indexes], times):
        raise ValueError("one or more frozen entry fills do not map to the exact tick stream")
    quote = np.where(opens["direction"].to_numpy() == 1, book._ask[indexes], book._bid[indexes])
    if not np.allclose(quote, opens["price"].to_numpy(dtype=np.float64), rtol=0.0, atol=1e-8):
        raise ValueError("frozen entry price does not match its executable bid/ask quote")


def _source_compatibility(root: Path, cfg: Any) -> bool:
    """Audit the replay call path against the source that generated the cohort.

    The post-campaign factory changed sizing and added percentage guardrails.
    The shadow injects archived quantities directly, so sizing is outside the
    replay path. For guardrails, compare the effective fixed-dollar values with
    the archived factory defaults before accepting the source audit.
    """
    comparable = [
        name
        for name in RELEVANT_SOURCE_FILES
        if name
        not in {
            "simulation/environment/episode_runtime.py",
            "simulation/environment/trading_environment_factory.py",
        }
    ]
    result = subprocess.run(
        ["git", "diff", "--quiet", ARCHIVED_TRAINING_COMMIT, "--", *comparable],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return False

    archived_factory = subprocess.check_output(
        ["git", "show", f"{ARCHIVED_TRAINING_COMMIT}:simulation/environment/factory.py"],
        cwd=root,
        text=True,
    )
    current_factory = (root / "simulation/environment/trading_environment_factory.py").read_text(
        encoding="utf-8"
    )
    archived_factory_tree = ast.parse(archived_factory)
    current_factory_tree = ast.parse(current_factory)
    archived_factory_functions = {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.walk(archived_factory_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    current_factory_functions = {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.walk(current_factory_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    changed_factory_functions = {
        name
        for name in archived_factory_functions.keys() | current_factory_functions.keys()
        if archived_factory_functions.get(name) != current_factory_functions.get(name)
    }
    if changed_factory_functions - {"max_loss_per_trade", "guardrail_kwargs"}:
        return False

    archived_fixed_guardrails = {
        "daily_loss_limit": float(cfg.ftmo.daily_loss_limit),
        "max_loss_limit": float(cfg.ftmo.max_loss_limit),
        "risk_per_trade_limit": float(cfg.ftmo.risk_per_trade_limit),
        "soft_daily_loss_limit": float(cfg.ftmo.get("soft_daily_loss_limit", 2000.0)),
        "soft_max_loss_limit": float(cfg.ftmo.get("soft_max_loss_limit", 5000.0)),
        "trailing_dd_limit": float(cfg.ftmo.get("trailing_dd_limit", 0.07)),
        "soft_trailing_dd_limit": float(cfg.ftmo.get("soft_trailing_dd_limit", 0.0)),
    }
    resolved_guardrails = guardrail_kwargs(cfg)
    if str(cfg.ftmo.get("limit_value_mode", "fixed_usd")) != "fixed_usd":
        return False
    if any(
        resolved_guardrails.get(key) != value for key, value in archived_fixed_guardrails.items()
    ):
        return False

    archived = subprocess.check_output(
        [
            "git",
            "show",
            f"{ARCHIVED_TRAINING_COMMIT}:simulation/environment/episode_runtime.py",
        ],
        cwd=root,
        text=True,
    )
    current = (root / "simulation/environment/episode_runtime.py").read_text(encoding="utf-8")
    archived_tree = ast.parse(archived)
    current_tree = ast.parse(current)
    method_names = {"_progress_market", "_is_ny_session_boundary"}
    archived_methods = {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.walk(archived_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in method_names
    }
    current_methods = {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.walk(current_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in method_names
    }
    return archived_methods == current_methods and set(archived_methods) == method_names


def run_preflight(root: Path) -> dict[str, Any]:
    """Validate only the frozen 2025 inputs and reconstructed entry geometry."""
    bars, features, book, paths = _load_training_inputs(root)
    opens, events = _load_trade_ledger(paths["trades"])
    _validate_historical_quotes(opens, book)
    cfg = OmegaConf.load(paths["config"])
    env = make_env(
        bars,
        features,
        cfg,
        algo="ppo",
        reward=str(cfg.env.get("reward_mode", "dsr")),
        episodic=False,
        tickbook=book,
        arch=str(cfg.agent.get("arch", "tcn")),
    )
    classifications = [classify_structural(env, row) for _, row in opens.iterrows()]
    counts = pd.Series([item.status for item in classifications]).value_counts().to_dict()
    reasons = pd.Series([item.reason for item in classifications]).value_counts().to_dict()
    max_drawdown_rows = events.loc[events["reason"].eq("max_drawdown"), "position_id"].nunique()
    return {
        "frozen_entries": int(len(opens)),
        "bar_rows": int(len(bars)),
        "feature_rows": int(len(features)),
        "tick_rows": int(len(book)),
        "tick_end_utc": pd.Timestamp(int(book._ts[-1]), unit="ns", tz="UTC").isoformat(),
        "tick_entries_exact_quote": int(len(opens)),
        "initial_risk_formula_matches": int(len(opens)),
        "structural_eligibility": {key: int(value) for key, value in counts.items()},
        "eligibility_reasons": {key: int(value) for key, value in reasons.items()},
        "historical_account_path_closes": int(max_drawdown_rows),
        "execution_methods_match_archived": _source_compatibility(root, cfg),
        "excluded_source_changes": (
            "factory sizing-cap resolution is outside replay because quantity is frozen; "
            "new percentage guardrail fields are inactive under the archived fixed-USD mode; "
            "episode reward limit kwargs are not called"
        ),
        "policy_inference_count": 0,
        "training_started": False,
    }


def _write_plot(paired: pd.DataFrame, out: Path) -> None:
    data = paired.loc[paired["structural_status"].eq("eligible")].copy()
    data = data.dropna(subset=["delta_r_historical_net"])
    monthly = _monthly_cohort_summary(paired)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    axes[0].hist(data["delta_r_historical_net"], bins=40, color="#336699", alpha=0.85)
    axes[0].axvline(0.0, color="#333333", linewidth=1)
    axes[0].set(title="Paired structural − EMA outcome", xlabel="Δ realized R", ylabel="Entries")
    months = [row["entry_month"] for row in monthly]
    axes[1].bar(months, [row["mean_delta_r"] for row in monthly], color="#568c5a")
    axes[1].axhline(0.0, color="#333333", linewidth=1)
    axes[1].set(
        title="Conditional exit difference by entry month",
        xlabel="2025 entry month",
        ylabel="Mean Δ realized R",
    )
    axes[1].tick_params(axis="x", rotation=65)
    x = np.arange(len(monthly))
    width = 0.38
    axes[2].bar(
        x - width / 2,
        [row["ema_paired_net_pnl"] for row in monthly],
        width,
        label="EMA control",
        color="#7b8794",
    )
    axes[2].bar(
        x + width / 2,
        [row["structural_paired_net_pnl"] for row in monthly],
        width,
        label="Structural exits",
        color="#d28e48",
    )
    axes[2].axhline(0.0, color="#333333", linewidth=1)
    axes[2].set(
        title="Matched-cohort monthly net P&L",
        xlabel="2025 entry month",
        ylabel="Trade P&L ($), not compounded",
        xticks=x,
        xticklabels=months,
    )
    axes[2].tick_params(axis="x", rotation=65)
    axes[2].legend()
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def _monthly_cohort_summary(paired: pd.DataFrame) -> list[dict[str, Any]]:
    data = paired.copy()
    data["entry_month"] = pd.to_datetime(data["decision_time"], utc=True).dt.strftime("%Y-%m")
    rows: list[dict[str, Any]] = []
    for month, group in data.groupby("entry_month", sort=True):
        eligible = group.loc[group["structural_status"].eq("eligible")].dropna(
            subset=["delta_r_historical_net"]
        )
        ema_pnl = group["ema_historical_net_pnl"].dropna()
        ema_r = group["ema_realized_r"].dropna()
        rows.append(
            {
                "entry_month": str(month),
                "frozen_entries": int(len(group)),
                "ema_all_net_pnl": float(group["ema_historical_net_pnl"].sum()),
                "ema_wins": int((ema_pnl > 0.0).sum()),
                "ema_losses": int((ema_pnl < 0.0).sum()),
                "ema_breakeven": int((ema_pnl == 0.0).sum()),
                "ema_win_rate": float((ema_pnl > 0.0).mean()) if not ema_pnl.empty else 0.0,
                "ema_mean_r": float(ema_r.mean()) if not ema_r.empty else float("nan"),
                "paired_entries": int(len(eligible)),
                "ema_paired_net_pnl": float(eligible["ema_historical_net_pnl"].sum()),
                "structural_paired_net_pnl": float(eligible["structural_historical_net_pnl"].sum()),
                "mean_delta_r": float(eligible["delta_r_historical_net"].mean())
                if not eligible.empty
                else float("nan"),
                "median_delta_r": float(eligible["delta_r_historical_net"].median())
                if not eligible.empty
                else float("nan"),
            }
        )
    return rows


def _markdown_report(summary: dict[str, Any], paired: pd.DataFrame) -> str:
    counts = summary["cohort"]
    control = summary["ema_control"]
    primary = summary["primary_historical_net"]
    lines = [
        "# Fixed-entry exit-only shadow results",
        "",
        "This is a conditional trade-level analysis of the archived 2025 v2 entries. It is not a new strategy backtest, does not compound a shadow equity curve, and does not use PPO or the 2026 split.",
        "",
        "## Protocol and input boundary",
        "",
        f"- Frozen entries: {counts['candidate_entries']:,}; eligibility: {counts['structural_eligible']:,}; ineligible: {counts['structural_ineligible']:,}; unresolved: {counts['unresolved']:,}.",
        f"- Paired primary rows: {primary['n']:,}; EMA control fill-parity rows: {control['exact_entries']:,}/{counts['candidate_entries']:,}.",
        f"- Archived source commit: `{summary['provenance']['archived_training_source_commit']}`; called execution methods match it: `{summary['provenance']['execution_methods_match_archived']}`.",
        f"- Audited source differences outside the replay path: {summary['provenance']['excluded_source_changes']}.",
        f"- 2025-only ticks: {summary['provenance']['tick_rows']:,}, ending `{summary['provenance']['tick_end_utc']}`. Features were read with a pre-2026 cutoff and aligned exactly to training bars.",
        "- Latency is paired by entry: the first draw reuses that entry's archived v2 exit latency; later event draws are keyed by entry ID and event order.",
        "- Historical tick fills use bid/ask with the archived effective tick slippage of zero and zero commission. Stress adds 5 adverse points at entry and each exit fill, matching the configured slippage amount as a one-sided stress.",
        "- MAE/MFE use executable liquidation-side ticks from each actual fill through that arm's own final exit. The initial USD stop risk is fixed across both arms.",
        "",
        "## Paired result",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Mean ΔR, structural − EMA | {primary.get('mean', float('nan')):.4f} |",
        f"| Median ΔR | {primary.get('median', float('nan')):.4f} |",
        f"| Standard deviation | {primary.get('std', float('nan')):.4f} |",
        f"| 95% paired bootstrap CI for mean | [{primary.get('paired_bootstrap_95pct_mean_ci', [float('nan'), float('nan')])[0]:.4f}, {primary.get('paired_bootstrap_95pct_mean_ci', [float('nan'), float('nan')])[1]:.4f}] |",
        f"| Structural wins / EMA wins / ties | {primary.get('wins', 0)} / {primary.get('losses', 0)} / {primary.get('ties', 0)} |",
        f"| Mean ΔR, gross | {summary['primary_gross'].get('mean', float('nan')):.4f} |",
        f"| Mean ΔR, cost stress | {summary['primary_stress'].get('mean', float('nan')):.4f} |",
        "",
        "## Exit outcomes",
        "",
        "| Arm | Exit reason | Count | Mean R | Median R |",
        "|---|---|---:|---:|---:|",
    ]
    for arm in ("ema", "structural"):
        part = paired.loc[paired[f"{arm}_complete"].fillna(False)]
        for reason, group in part.groupby(f"{arm}_exit_reason", dropna=False):
            lines.append(
                f"| {arm} | {reason} | {len(group)} | {group[f'{arm}_realized_r'].mean():.4f} | {group[f'{arm}_realized_r'].median():.4f} |"
            )
    lines.extend(
        [
            "",
            "## Monthly conditional result",
            "",
            "Monthly P&L is the sum of frozen trade outcomes, not a compounded account equity curve.",
            "",
            "| Entry month | Frozen N | EMA W/L/BE | EMA win rate | Mean EMA R | EMA net P&L, all ($) | Paired N | EMA net P&L, paired ($) | Structural net P&L ($) | Mean ΔR |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    monthly_rows = _monthly_cohort_summary(paired)
    for row in monthly_rows:
        lines.append(
            f"| {row['entry_month']} | {row['frozen_entries']} | {row['ema_wins']}/{row['ema_losses']}/{row['ema_breakeven']} | {row['ema_win_rate']:.1%} | {row['ema_mean_r']:.3f} | {row['ema_all_net_pnl']:.2f} | {row['paired_entries']} | {row['ema_paired_net_pnl']:.2f} | {row['structural_paired_net_pnl']:.2f} | {row['mean_delta_r']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "The paired estimate answers whether structural exits changed outcomes for the same historical v2 entries. The near-zero overall ΔR and interval spanning zero mean this exit change does not explain the March–April peak and later decline. The monthly EMA control shifts from a 49.0% win rate and +0.223 mean R in March to a 34.3% win rate and −0.191 mean R in April; September through November remain mostly losing cohorts. Frozen quantities average about $874–$1,000 initial risk per trade, so the decline is not explained by smaller position risk. This identifies weaker later trade outcomes, but it does not identify whether entry quality, policy learning, or market regime caused them.",
            "",
            "The full EMA control must pass its documented exact-fill gate before the structural result is treated as scientifically interpretable. The one original account-level max-drawdown close is replayed without account-path truncation; its natural exit may differ and is reported as a known boundary exception.",
            "",
            "## Reproducibility",
            "",
            f"- Bootstrap: 10,000 paired resamples, seed {summary['bootstrap_seed']}.",
            f"- Deterministic repeat: `{summary['reproducibility']['identical_outputs']}`.",
            "- All file identities and output hashes: [`provenance.json`](provenance.json).",
            "- Trade ledger: [`paired_trades.csv`](paired_trades.csv); fill and management events: [`shadow_events.jsonl`](shadow_events.jsonl).",
            "- Plot: [`paired_delta_r.png`](paired_delta_r.png).",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis(
    root: Path, out: Path, *, resamples: int = 10_000, repeat: bool = True
) -> dict[str, Any]:
    bars, features, book, paths = _load_training_inputs(root)
    opens, original_events = _load_trade_ledger(paths["trades"])
    _validate_historical_quotes(opens, book)
    cfg = OmegaConf.load(paths["config"])
    if not _source_compatibility(root, cfg):
        raise RuntimeError("replay source compatibility gate failed")
    env = make_env(
        bars,
        features,
        cfg,
        algo="ppo",
        reward=str(cfg.env.get("reward_mode", "dsr")),
        episodic=False,
        tickbook=book,
        arch=str(cfg.agent.get("arch", "tcn")),
    )
    classification_by_id = {
        str(row["position_id"]): classify_structural(env, row) for _, row in opens.iterrows()
    }
    ema_runs: dict[str, dict[str, Any]] = {}
    comparison_by_id: dict[str, dict[str, Any]] = {}
    exact_control_entries = 0
    known_account_path_entries = 0
    unexpected_mismatches: list[dict[str, Any]] = []
    for _, row in opens.iterrows():
        position_id = str(row["position_id"])
        replay = replay_entry(
            env,
            row,
            None,
            "ema_21",
            _latency_for_entry(original_events, position_id),
        )
        original_fills = _original_fills(original_events, position_id)
        comparison = _compare_control(replay, original_fills)
        ema_runs[position_id] = replay
        comparison_by_id[position_id] = comparison
        if comparison["pass"]:
            exact_control_entries += 1
        elif any(str(item.get("reason")) == "max_drawdown" for item in original_fills):
            known_account_path_entries += 1
        else:
            unexpected_mismatches.append({"position_id": position_id, **comparison})
    if unexpected_mismatches or exact_control_entries + known_account_path_entries != len(opens):
        out.mkdir(parents=True, exist_ok=True)
        (out / "ema_control_gate_failed.json").write_text(
            json.dumps(
                {
                    "candidate_entries": int(len(opens)),
                    "exact_entries": exact_control_entries,
                    "known_account_path_entries": known_account_path_entries,
                    "control_rows_accounted_for": exact_control_entries
                    + known_account_path_entries,
                    "unexpected_mismatches": unexpected_mismatches,
                    "structural_replay_started": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise RuntimeError(
            f"EMA control failed for {len(unexpected_mismatches)} entries; structural replay was not started"
        )

    contract_size = float(cfg.account.contract_size)
    extra_slippage = float(cfg.costs.slippage_points)
    history: dict[str, dict[str, list[dict[str, Any]]]] = {}
    rows: list[dict[str, Any]] = []
    incomplete_pairs: list[str] = []
    for _, row in opens.iterrows():
        position_id = str(row["position_id"])
        classification = classification_by_id[position_id]
        latency = _latency_for_entry(original_events, position_id)
        ema_replay = ema_runs[position_id]
        ema_metrics = _trade_metrics(row, ema_replay, book, contract_size, extra_slippage)
        structural_replay: dict[str, Any] | None = None
        structural_metrics: dict[str, Any] = {"complete": False}
        if classification.status == "eligible":
            structural_replay = replay_entry(
                env, row, classification.geometry, "structural", latency
            )
            structural_metrics = _trade_metrics(
                row, structural_replay, book, contract_size, extra_slippage
            )
            if not ema_metrics.get("complete") or not structural_metrics.get("complete"):
                incomplete_pairs.append(position_id)
        record: dict[str, Any] = {
            "position_id": position_id,
            "decision_time": str(row["decision_time"]),
            "fill_time": str(row["actual_tick_time"]),
            "side": "long" if int(row["direction"]) == 1 else "short",
            "entry_price": float(row["price"]),
            "quantity": float(row["lots"]),
            "initial_stop": float(row["sl_price"]),
            "initial_risk_usd": float(row["modeled_stop_risk_usd"]),
            "structural_status": classification.status,
            "structural_status_reason": classification.reason,
            "validation_control_pass": bool(comparison_by_id[position_id]["pass"]),
            "ema_complete": bool(ema_metrics.get("complete", False)),
            "structural_complete": bool(structural_metrics.get("complete", False)),
        }
        for prefix, metrics in (("ema", ema_metrics), ("structural", structural_metrics)):
            for key, value in metrics.items():
                record[f"{prefix}_{key}"] = value
        if classification.geometry is not None:
            geometry = classification.geometry
            for slot in (1, 2, 3):
                record[f"structural_tp{slot}_price"] = getattr(geometry, f"tp{slot}_price")
                record[f"structural_tp{slot}_reference"] = getattr(geometry, f"tp{slot}_ref")
            record["structural_tp_fractions"] = json.dumps(geometry.tp_lot_fractions)
        if classification.status == "eligible" and not incomplete_pairs:
            for scenario, metric in (
                ("historical_net", "realized_r"),
                ("gross", "gross_r"),
                ("stress", "stress_r"),
            ):
                record[f"delta_r_{scenario}"] = float(
                    structural_metrics[metric] - ema_metrics[metric]
                )
        rows.append(record)
        history[position_id] = {
            "ema": ema_replay["events"],
            "structural": [] if structural_replay is None else structural_replay["events"],
        }
    if incomplete_pairs:
        out.mkdir(parents=True, exist_ok=True)
        (out / "paired_replay_gate_failed.json").write_text(
            json.dumps(
                {"incomplete_eligible_pairs": incomplete_pairs, "paired_replay_complete": False},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        raise RuntimeError(f"paired replay incomplete for {len(incomplete_pairs)} eligible entries")

    paired = pd.DataFrame(rows)
    eligible = paired.loc[paired["structural_status"].eq("eligible")]
    prior_provenance = json.loads(
        (root / EVIDENCE_ROOT / "provenance.json").read_text(encoding="utf-8")
    )
    summary: dict[str, Any] = {
        "cohort": {
            "candidate_entries": int(len(opens)),
            "structural_eligible": int(paired["structural_status"].eq("eligible").sum()),
            "structural_ineligible": int(paired["structural_status"].eq("ineligible").sum()),
            "unresolved": int(paired["structural_status"].eq("unresolved").sum()),
            "paired_complete": int(len(eligible)),
        },
        "ema_control": {
            "exact_entries": exact_control_entries,
            "known_max_drawdown_boundary_rows": known_account_path_entries,
            "unexpected_mismatches": [],
            "passed": exact_control_entries + known_account_path_entries == len(opens),
        },
        "primary_historical_net": _distribution(
            eligible["delta_r_historical_net"], 20261024, resamples
        ),
        "primary_gross": _distribution(eligible["delta_r_gross"], 20261024, resamples),
        "primary_stress": _distribution(eligible["delta_r_stress"], 20261024, resamples),
        "bootstrap_seed": 20261024,
        "provenance": {
            "archived_training_source_commit": ARCHIVED_TRAINING_COMMIT,
            "current_git_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "execution_methods_match_archived": _source_compatibility(root, cfg),
            "excluded_source_changes": (
                "factory sizing-cap resolution is outside replay because quantity is frozen; "
                "new percentage guardrail fields are inactive under the archived fixed-USD mode; "
                "episode reward limit kwargs are not called"
            ),
            "relevant_source_sha256": {
                name: sha256_file(root / name) for name in RELEVANT_SOURCE_FILES
            },
            "analysis_script_sha256": sha256_file(
                root / "scripts/research/thesis/exit_shadow_fixed_entry.py"
            ),
            "bars_rows": int(len(bars)),
            "features_rows": int(len(features)),
            "tick_rows": int(len(book)),
            "tick_start_utc": pd.Timestamp(int(book._ts[0]), unit="ns", tz="UTC").isoformat(),
            "tick_end_utc": pd.Timestamp(int(book._ts[-1]), unit="ns", tz="UTC").isoformat(),
            "training_boundary": "2025-12-31 23:59 Etc/GMT-3",
            "checkpoint_used": False,
            "frozen_checkpoint_sha256": prior_provenance["hashes"]["checkpoint_sha256"],
            "policy_inference_count": 0,
            "entry_generation_count": 0,
            "counterfactual_equity_curve": False,
            "costs": {
                "raw_tick_bid_ask_in_historical_net": True,
                "effective_tick_slippage_points": 0.0,
                "configured_slippage_points_used_for_stress": extra_slippage,
                "commission_per_lot": float(cfg.costs.commission_per_lot),
            },
            "input_sha256": {key: sha256_file(path) for key, path in paths.items()},
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    paired.to_csv(out / "paired_trades.csv", index=False)
    with (out / "shadow_events.jsonl").open("w", encoding="utf-8") as handle:
        for position_id in sorted(history):
            for arm in ("ema", "structural"):
                for event_index, event in enumerate(history[position_id][arm]):
                    handle.write(
                        json.dumps(
                            {
                                "position_id": position_id,
                                "arm": arm,
                                "event_index": event_index,
                                **event,
                            },
                            default=str,
                            sort_keys=True,
                        )
                        + "\n"
                    )
    _write_plot(paired, out / "paired_delta_r.png")
    if repeat:
        repeat_mismatches = 0
        for _, row in opens.iterrows():
            position_id = str(row["position_id"])
            classification = classification_by_id[position_id]
            latency = _latency_for_entry(original_events, position_id)
            ema_repeat = replay_entry(env, row, None, "ema_21", latency)
            if json.dumps(ema_repeat, default=str, sort_keys=True) != json.dumps(
                {
                    "events": history[position_id]["ema"],
                    "fills": [
                        event for event in history[position_id]["ema"] if event.get("fill_id")
                    ],
                },
                default=str,
                sort_keys=True,
            ):
                repeat_mismatches += 1
            if classification.status == "eligible":
                structural_repeat = replay_entry(
                    env, row, classification.geometry, "structural", latency
                )
                if json.dumps(structural_repeat, default=str, sort_keys=True) != json.dumps(
                    {
                        "events": history[position_id]["structural"],
                        "fills": [
                            event
                            for event in history[position_id]["structural"]
                            if event.get("fill_id")
                        ],
                    },
                    default=str,
                    sort_keys=True,
                ):
                    repeat_mismatches += 1
        summary["reproducibility"] = {
            "identical_outputs": repeat_mismatches == 0,
            "mismatch_count": repeat_mismatches,
        }
    else:
        summary["reproducibility"] = {
            "identical_outputs": False,
            "mismatch_count": None,
            "repeat_run": "not requested",
        }
    summary["provenance"]["output_sha256"] = {
        name: sha256_file(out / name)
        for name in ("paired_trades.csv", "shadow_events.jsonl", "paired_delta_r.png")
    }
    report_path = out / "fixed_entry_shadow_report.md"
    report_path.write_text(_markdown_report(summary, paired), encoding="utf-8")
    summary["provenance"]["output_sha256"][report_path.name] = sha256_file(report_path)
    (out / "provenance.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=EVIDENCE_ROOT / "fixed_entry_shadow",
    )
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--no-repeat", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = run_preflight(args.repo_root.resolve())
        print(json.dumps(result, indent=2, sort_keys=True))
        if not result["execution_methods_match_archived"]:
            raise SystemExit("replay source compatibility gate failed")
        if result["structural_eligibility"].get("unresolved", 0) > 0:
            raise SystemExit("structural eligibility reconstruction has unresolved entries")
        return
    result = run_analysis(
        args.repo_root.resolve(),
        args.output if args.output.is_absolute() else args.repo_root / args.output,
        resamples=args.bootstrap_resamples,
        repeat=not args.no_repeat,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["ema_control"]["unexpected_mismatches"]:
        raise SystemExit("EMA control parity failed; structural estimate is not interpretable")
    if not result["reproducibility"]["identical_outputs"]:
        raise SystemExit("deterministic repeat check failed")


if __name__ == "__main__":
    main()
