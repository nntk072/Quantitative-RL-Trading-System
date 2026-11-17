"""Evaluate step-indexed baselines on a configured report split.

Runs registered `BaseStrategy` policies through the shared evaluation pipeline
(`run_episode` + `TradingEnv`) on a configured report split. The default 2026
interval is already exposed and is labeled report-only. This continuous-action
evaluator does not by itself provide a matched registry for every RL action
schema. Writes one `metrics.json` per strategy, retaining the `out_of_sample`
report block for compatibility with `scripts/report_g3.py`.

Example:
    python scripts/run_baseline_eval.py --bars-csv data/us100_2025.csv \
        --out outputs/rl_runs/baselines
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from evaluation import build_run_report, run_episode  # noqa: E402
from evaluation.rollout.baseline_features import (  # noqa: E402
    STOP_FEATURES,
    ensure_baseline_stop_features,
)
from evaluation.rollout.baseline_signal_actions import (  # noqa: E402
    discrete_actions_for_position_targets,
)
from features.technical.swings import TIMEFRAME_CONFIG  # noqa: E402
from market_data.splits.definitions import split_train_test  # noqa: E402
from simulation.environment.env import TradingEnv  # noqa: E402
from trading.baselines import (  # noqa: E402
    BaseStrategy,
    BuyAndHoldStrategy,
    EMAMACDRSIStrategy,
    MultiLevelBreakoutStrategy,
    SessionMomentumStrategy,
    SignalSeriesStrategy,
    macd_baseline,
    rsi_mean_reversion,
)


def build_strategies(bars: pd.DataFrame) -> dict[str, BaseStrategy]:
    """Instantiate each precomputed baseline over the evaluation bars."""
    return {
        "always_flat": BuyAndHoldStrategy(n_bars=len(bars), size=0.0),
        "buy_and_hold": BuyAndHoldStrategy(n_bars=len(bars)),
        "ema_macd_rsi": EMAMACDRSIStrategy(bars),
        "breakout": MultiLevelBreakoutStrategy(bars),
        "session_momentum": SessionMomentumStrategy(bars),
        "macd_histogram": SignalSeriesStrategy(macd_baseline(bars)),
        "rsi_mean_reversion": SignalSeriesStrategy(rsi_mean_reversion(bars)),
    }


def _discrete_signal_actions(
    name: str, bars: pd.DataFrame, *, start_index: int
) -> pd.Series | None:
    """Build exit-capable actions for the precomputed signal-series arms."""
    if name == "macd_histogram":
        targets = macd_baseline(bars)
    elif name == "rsi_mean_reversion":
        targets = rsi_mean_reversion(bars)
    else:
        return None
    if not 0 <= start_index <= len(bars):
        raise ValueError("start_index must be within the bar series")
    actions = pd.Series(0, index=bars.index, dtype=int)
    actions.iloc[start_index:] = discrete_actions_for_position_targets(targets.iloc[start_index:])
    return actions


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars-csv", required=True, help="OHLCV CSV with DatetimeIndex")
    parser.add_argument("--features-csv", help="Feature CSV; defaults to numeric bars columns")
    parser.add_argument("--train-end", default="2025-12-31", help="Last development date")
    parser.add_argument(
        "--test-start",
        default="2026-01-01",
        help="First report date (the default 2026 period is already exposed)",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=["always_flat", "buy_and_hold", "ema_macd_rsi", "breakout"],
        choices=[
            "always_flat",
            "buy_and_hold",
            "ema_macd_rsi",
            "breakout",
            "session_momentum",
            "macd_histogram",
            "rsi_mean_reversion",
        ],
    )
    parser.add_argument("--out-dir", default="outputs/rl_runs", help="Base directory for reports")
    return parser.parse_args()


def main() -> None:
    """Evaluate baselines on a configured report split and persist metrics."""
    args = parse_args()
    bars = pd.read_csv(args.bars_csv, index_col=0, parse_dates=True)
    features = (
        pd.read_csv(args.features_csv, index_col=0, parse_dates=True)
        if args.features_csv
        else bars.select_dtypes(include=["number"])
    )
    swing_period = int(TIMEFRAME_CONFIG["M1"]["left"])
    features, generated_stop_features = ensure_baseline_stop_features(
        bars,
        features,
        swing_period=swing_period,
    )

    _, test_bars, _, test_features = split_train_test(
        bars, features, args.train_end, args.test_start
    )
    if test_bars.empty:
        raise SystemExit(f"empty test split with --test-start {args.test_start}")
    evaluation_index = test_bars.index
    if not isinstance(evaluation_index, pd.DatetimeIndex):
        raise TypeError("baseline evaluation requires a DatetimeIndex")
    evaluation_dates = (
        evaluation_index.tz_localize(None) if evaluation_index.tz is not None else evaluation_index
    )
    exposed_start = pd.Timestamp("2026-01-01")
    exposed_end = pd.Timestamp("2026-10-16 23:59:59.999999")
    exposed_overlap = bool(
        ((evaluation_dates >= exposed_start) & (evaluation_dates <= exposed_end)).any()
    )
    period_role = "exposed_report_only" if exposed_overlap else "configured_period_unverified"
    print(f"configured report split: {len(test_bars)} bars (≥{args.test_start})")

    strategies = build_strategies(test_bars)
    for name in args.strategies:
        strategy = strategies[name]
        observation_window = 60
        discrete_actions = _discrete_signal_actions(name, test_bars, start_index=observation_window)

        env = TradingEnv(
            bars=test_bars,
            features=test_features,
            obs_window=observation_window,
            continuous_actions=discrete_actions is None,
            max_risk_frac=0.01,
            risk_frac_range=(0.005, 0.01),
            rr_ratio_range=(1.0, 3.0),
            # Eval mode: a breach blocks trading for the rest of the session
            # instead of truncating the episode (mirrors run_backtest).
            episodic=False,
        )

        def action_fn(
            obs: Any,
            _strategy: BaseStrategy = strategy,
            _discrete_actions: pd.Series | None = discrete_actions,
        ) -> Any:
            del obs
            if _discrete_actions is not None:
                return int(_discrete_actions.iloc[env.step_idx])
            # Environment stepping skips overnight rows; use its actual data
            # index instead of advancing once per action.
            return np.array([_strategy.act_at(env.step_idx)], dtype=np.float32)

        metrics = run_episode(env, action_fn=action_fn)
        report: dict[str, Any] = {
            "run_name": f"baseline_{name}",
            "split": {
                "train_end": args.train_end,
                "test_start": args.test_start,
                "test_bars": int(len(test_bars)),
                "period_role": period_role,
            },
            "evaluation_contract": {
                "scope": "baseline arms share TradingEnv; not matched to an RL campaign action schema",
                "action_schema": "discrete-trading-v1" if discrete_actions is not None else None,
                "action_mode": "discrete_exit_capable"
                if discrete_actions is not None
                else "continuous_signal",
                "risk_frac_range": [0.005, 0.01],
                "max_risk_frac": 0.01,
                "rr_ratio_range": [1.0, 3.0],
                "stop_features": list(STOP_FEATURES),
                "generated_stop_features": list(generated_stop_features),
                "swing_period": swing_period,
                "structure_atr_reversal_multiplier": 0.0,
            },
            "out_of_sample": build_run_report(metrics, env.trade_log),
        }

        out_dir = Path(args.out_dir) / f"baseline_{name}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "metrics.json").write_text(json.dumps(report, indent=2))

        oos = report["out_of_sample"]
        print(
            f"{name:16} sharpe={oos['sharpe']:7.3f}  mdd={oos['max_drawdown']:7.4f}  "
            f"pnl={oos['total_pnl']:10.2f}  completed_positions={oos['n_trades']}  -> {out_dir / 'metrics.json'}"
        )


if __name__ == "__main__":
    main()
