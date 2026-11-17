"""Retired direct-train encoder comparison command.

The old command trained reward-optimizing policies outside the survival
qualification workflow and evaluated a previously exposed report period.
Use ``evaluate_split`` only with an already-qualified model and a preregistered
evaluation protocol. New training must go through the canonical runner.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import pandas as pd

from evaluation import build_run_report, run_episode  # noqa: E402
from evaluation.rollout.trained_policy_rollout import make_action_fn  # noqa: E402
from simulation.environment.env import TradingEnv  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars-csv", required=True, help="OHLCV CSV with DatetimeIndex")
    parser.add_argument("--features-csv", help="Feature CSV; defaults to numeric bars columns")
    parser.add_argument("--config", default="config/base/default.yaml", help="Env config YAML")
    parser.add_argument("--steps", type=int, default=50_000, help="Training steps per arch")
    parser.add_argument(
        "--archs",
        nargs="+",
        default=["gru", "transformer"],
        choices=["tcn", "lite_tcn", "gru", "transformer"],
    )
    parser.add_argument("--algo", default="ppo", choices=["ppo", "sac"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-end", default="2025-12-31", help="Last in-sample date")
    parser.add_argument("--test-start", default="2026-01-01", help="First out-of-sample date")
    parser.add_argument("--out", default="outputs/benchmarks/encoder_comparison.json")
    return parser.parse_args()


def evaluate_split(
    model: Any, algo: str, bars: pd.DataFrame, features: pd.DataFrame
) -> dict[str, Any]:
    """Run one deterministic episode of *model* over *bars* and score it."""
    env = TradingEnv(
        bars=bars,
        features=features,
        continuous_actions=algo == "sac",
        # Eval mode: a breach blocks trading for the rest of the session
        # instead of truncating the episode (mirrors run_backtest).
        episodic=False,
    )
    metrics = run_episode(env, action_fn=make_action_fn(model, continuous_actions=algo == "sac"))
    return build_run_report(metrics, env.trade_log)


def main() -> None:
    """Reject direct architecture training outside the survival-gated workflow."""
    if sys.argv[1:] in (["-h"], ["--help"]):
        parse_args()
    raise SystemExit(
        "direct encoder-comparison training bypasses survival-first qualification and is "
        "disabled; use the canonical training workflow and a preregistered evaluation "
        "after the survival gate passes"
    )


if __name__ == "__main__":
    main()
