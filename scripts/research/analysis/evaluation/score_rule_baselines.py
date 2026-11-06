# mypy: ignore-errors
"""Score rule baselines in TradingEnv on the configured train and test splits.

Does not train a network. Writes one summary per rule under outputs/rule_baselines/.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from configuration.paths import repository_root

ROOT = repository_root(__file__)

from configuration import load_config  # noqa: E402
from evaluation.rollout.baseline_features import ensure_baseline_stop_features  # noqa: E402
from evaluation.rollout.episode_rollout import run_episode  # noqa: E402
from features.technical.swings import TIMEFRAME_CONFIG  # noqa: E402
from market_data.loading import run_pipeline  # noqa: E402
from market_data.splits.definitions import get_split_config, split_bars  # noqa: E402
from simulation.environment.env import TradingEnv  # noqa: E402
from trading.baselines import (  # noqa: E402  # noqa: E402
    EMAMACDRSIStrategy,
    SessionMomentumStrategy,
    fit_hold_lots,
    simulate_hold,
)

RULES = (
    "buy_and_hold",
    "ema_macd_rsi",
    "session_momentum",
)

EXPOSED_REPORT_START = pd.Timestamp("2026-01-01").date()
EXPOSED_REPORT_END = pd.Timestamp("2026-10-16").date()


def _period_scope(index: pd.Index) -> dict[str, object]:
    """Classify an interval against the project's exposed report period.

    Overlap with the previously inspected 2026 interval is report-only. Other
    intervals remain unclassified rather than being called a fresh holdout.
    """
    if index.empty:
        return {"role": "empty", "confirmatory": False, "start": None, "end": None}

    start = pd.Timestamp(index.min()).date()
    end = pd.Timestamp(index.max()).date()
    exposed = start <= EXPOSED_REPORT_END and end >= EXPOSED_REPORT_START
    return {
        "role": "exposed_report_only" if exposed else "unclassified_non_confirmatory",
        "confirmatory": False,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


def _strategy(name: str, bars: pd.DataFrame):
    if name == "ema_macd_rsi":
        strategy = EMAMACDRSIStrategy(bars)
    elif name == "session_momentum":
        strategy = SessionMomentumStrategy(bars)
    else:
        raise ValueError(name)
    return strategy


def _index_return_pct(bars: pd.DataFrame, start_index: int | None) -> float:
    """Unlevered move from the first traded bar to the last close."""
    if start_index is None or not 0 <= start_index < len(bars):
        return 0.0
    start = float(bars["close"].iloc[start_index])
    end = float(bars["close"].iloc[-1])
    if start == 0.0:
        return 0.0
    return (end / start - 1.0) * 100.0


def _score(name: str, bars: pd.DataFrame) -> dict:
    strategy = _strategy(name, bars)
    first_step_index: int | None = None
    features = bars.select_dtypes(include="number").copy()
    features, _ = ensure_baseline_stop_features(
        bars,
        features,
        swing_period=int(TIMEFRAME_CONFIG["M1"]["left"]),
    )

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=60,
        continuous_actions=True,
        episodic=False,
        reward_mode="dsr",
        block_overnight=True,
        rr_ratio_range=(1.0, 3.0),
    )

    def action_fn(_obs, _strategy=strategy):
        nonlocal first_step_index
        bar_index = env.step_idx
        if first_step_index is None:
            first_step_index = bar_index
        return np.array([_strategy.act_at(bar_index)], dtype=np.float32)

    metrics = run_episode(env, action_fn=action_fn, max_steps=len(bars) + 5)
    closes = [t for t in env.trade_log if "close" in str(t.get("type", ""))]
    return {
        "sharpe": float(metrics.sharpe),
        "total_pnl": float(metrics.total_pnl),
        "total_return_pct": float(metrics.total_return_pct),
        "max_drawdown": float(metrics.max_drawdown),
        "n_trades": int(metrics.n_trades),
        "n_closes": len(closes),
        "breach_count": int(metrics.breach_count),
        "index_return_pct": _index_return_pct(bars, first_step_index),
    }


def main() -> None:
    cfg = load_config([])
    data = run_pipeline(cfg, force=False)
    bars = data[cfg.data.primary]["M1"]
    train_end, test_start = get_split_config(cfg)
    train_bars, test_bars = split_bars(bars, train_end, test_start)
    report_scope = _period_scope(test_bars.index)
    report_period_key = str(report_scope["role"])
    out = ROOT / "outputs" / "rule_baselines"
    out.mkdir(parents=True, exist_ok=True)
    fitted = fit_hold_lots(train_bars)
    print("fitted lots", fitted, flush=True)
    report: dict[str, dict] = {
        "buy_and_hold": {
            "lots": fitted,
            "train": simulate_hold(train_bars, fitted["lots"]),
            report_period_key: simulate_hold(test_bars, fitted["lots"]),
        }
    }
    print("buy_and_hold", report["buy_and_hold"][report_period_key], flush=True)
    for name in ("ema_macd_rsi", "session_momentum"):
        print(f"scoring {name}", flush=True)
        report[name] = {
            "train": _score(name, train_bars),
            report_period_key: _score(name, test_bars),
        }
        print(name, report[name][report_period_key], flush=True)
    flat = {
        "sharpe": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "max_drawdown": 0.0,
        "n_trades": 0,
        "n_closes": 0,
        "breach_count": 0,
        "index_return_pct": 0.0,
    }
    report["flat"] = {"train": flat, report_period_key: dict(flat)}
    report["scope"] = {
        "evaluation_period": report_scope,
        "selection_use": "prohibited",
        "reason": (
            "The inspected 2026 interval is exposed exploratory data; other "
            "intervals are unclassified and are not declared holdouts."
        ),
    }
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print("wrote", out / "summary.json")


if __name__ == "__main__":
    main()
