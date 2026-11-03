"""Run backtester with a random / placeholder policy.

Usage
-----
    cd Quantitative-RL-Trading-System
    python -m training.runner.backtest
    python -m training.runner.backtest env.obs_window=30 --seed=42
    python -m training.runner.backtest --no-save
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import argparse
import logging
import random
from typing import Any, cast

import numpy as np
import pandas as pd

from configuration import load_config
from evaluation import PerformanceMetrics, calculate_metrics
from evaluation.reporting.run_artifact_writer import save_run
from features import FEATURE_CACHE_VERSION, build_features
from market_data.loading import build_tick_books, run_pipeline
from market_data.splits.definitions import get_split_config, split_bars, split_train_test
from simulation.backtest import run_backtest
from simulation.environment.trading_environment_factory import eval_guardrail_kwargs
from trading.policy import TradingPolicyConfig, resolve_trading_policy
from trading.risk import RiskDailyPnlBasis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _random_policy(obs: np.ndarray[Any, Any]) -> int:
    """Process policy.

    Args:
        obs: Obs used by the operation described above.

    Returns:
        Numeric result returned by ``_random_policy``.
    """
    return random.choice([-1, 0, 1])


def _configured_backtest_policy(cfg: Any) -> TradingPolicyConfig:
    """Resolve and validate account lifecycle semantics for a backtest run."""
    policy = resolve_trading_policy(cfg)
    if policy.daily_pnl_basis is None:
        raise ValueError("resolved trading policy must define a daily PnL basis")
    return policy


def main() -> None:
    """Run a configured policy backtest and write evaluation artifacts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("overrides", nargs="*")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-save", action="store_true", help="Skip saving artifacts")
    parser.add_argument("--out", default="outputs", help="Base output directory")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    cfg = load_config(args.overrides)
    trading_policy = _configured_backtest_policy(cfg)
    daily_pnl_basis = cast(RiskDailyPnlBasis, trading_policy.daily_pnl_basis)
    data = run_pipeline(cfg, force=args.force)

    primary_sym = cfg.data.primary
    secondary_sym = cfg.data.secondary
    primary_m1 = data[primary_sym]["M1"]
    secondary_m1 = data.get(secondary_sym, {}).get("M1")

    cache_dir = Path(cfg.data.cache_dir)
    feat_cache = cache_dir / f"{primary_sym}_features_{FEATURE_CACHE_VERSION}.parquet"
    features = build_features(primary_m1, secondary=secondary_m1, cfg=cfg, cache_path=feat_cache)

    # Date-based train / test split
    train_end, test_start = get_split_config(cfg)
    train_bars, test_bars, train_feat, test_feat = split_train_test(
        primary_m1, features, train_end, test_start
    )
    train_sec = test_sec = None
    if secondary_m1 is not None and not secondary_m1.empty:
        train_sec, test_sec = split_bars(secondary_m1, train_end, test_start)
    log.info(
        "Split: train=%d bars (≤%s)  test=%d bars (≥%s)",
        len(train_bars),
        train_end,
        len(test_bars),
        test_start,
    )

    # Tick books for bid/ask fill execution (sliced per split)
    tick_books = build_tick_books(cfg, force=args.force)
    primary_ticks = tick_books.get(cfg.data.primary)
    train_ticks = (
        primary_ticks.slice(
            pd.Timestamp("2000-01-01", tz=cfg.data.tz),
            pd.Timestamp(train_end + " 23:59:59", tz=cfg.data.tz),
        )
        if primary_ticks is not None
        else None
    )
    test_ticks = (
        primary_ticks.slice(
            pd.Timestamp(test_start + " 00:00:00", tz=cfg.data.tz),
            pd.Timestamp("2099-01-01", tz=cfg.data.tz),
        )
        if primary_ticks is not None
        else None
    )

    max_loss_per_trade = None
    take_profit_per_trade = None
    try:
        max_loss_per_trade = cfg.backtest.validation.max_loss_per_trade_usd
        take_profit_per_trade = cfg.backtest.validation.take_profit_per_trade_usd
    except Exception:
        pass
    if trading_policy.repeated_payout:
        policy_risk_cap = trading_policy.operating_balance * trading_policy.max_agent_risk_frac
        max_loss_per_trade = (
            policy_risk_cap
            if max_loss_per_trade is None
            else min(float(max_loss_per_trade), policy_risk_cap)
        )
        take_profit_per_trade = None

    def _run(
        bars: pd.DataFrame,
        feats: pd.DataFrame,
        ticks: Any,
        label: str,
    ) -> tuple[dict[str, Any], PerformanceMetrics]:
        """Run the requested value.

        Args:
            bars: Market bars to process.
            feats: Tabular data used for the feats.
            ticks: Ticks used by the operation described above.
            label: Text or path value identifying the label.

        Returns:
            Mapping from ``str`` keys to ``Any], PerformanceMetrics`` values.
        """
        log.info("Running backtest [%s] seed=%d …", label, args.seed)
        result = run_backtest(
            bars=bars,
            features=feats,
            policy=_random_policy,
            obs_window=cfg.env.obs_window,
            initial_balance=cfg.account.initial_balance,
            guardrail_kwargs=eval_guardrail_kwargs(cfg),
            max_loss_per_trade_usd=max_loss_per_trade,
            take_profit_per_trade_usd=take_profit_per_trade,
            eod_risk=dict(cfg.env.get("eod_risk", {})),
            sl_mode=str(cfg.risk.get("sl_mode", "fixed")),
            daily_pnl_basis=daily_pnl_basis,
            trading_policy=trading_policy,
            use_structure_sl_tp=trading_policy.repeated_payout,
            risk_frac=(
                trading_policy.max_agent_risk_frac
                if trading_policy.repeated_payout
                else float(cfg.risk.default_risk_frac)
            ),
            rr_ratio=float(cfg.risk.rr_ratio_default),
            swing_buffer_pts=float(cfg.risk.swing_buffer_pts),
            sl_buffer_pts=float(cfg.env.get("sl_buffer_pts", 0.0)),
            min_lot=float(cfg.risk.min_lot),
            max_lot=float(cfg.risk.max_lot),
            contract_size=float(cfg.account.contract_size),
            tickbook=ticks,
            tick_execution_required=bool(cfg.costs.use_tick_execution),
            fill_latency_bars=cfg.execution.get("fill_latency_bars", 0),
            randomized_fill_latency_ms=cfg.execution.randomized_fill_latency_ms,
            max_tick_quote_wait_ms=cfg.execution.max_tick_quote_wait_ms,
            execution_seed=args.seed,
        )
        result["initial_balance"] = cfg.account.initial_balance
        metric_equity = (
            result["total_economic_value_curve"]
            if trading_policy.repeated_payout
            else result["equity"]
        )
        m = calculate_metrics(
            metric_equity,
            trades=result["trades"],
            n_sessions=result.get("n_sessions", 1),
            n_breach_sessions=result.get("n_breach_sessions", 0),
            initial_balance=float(cfg.account.initial_balance),
        )
        log.info(
            "[%s] Sharpe=%.3f  MaxDD=%.2f%%  Trades=%d  Breaches=%d/%d  Return=%.2f%%",
            label,
            m.sharpe,
            m.max_drawdown * 100,
            m.n_trades,
            result.get("n_breach_sessions", 0),
            result.get("n_sessions", 1),
            m.total_return_pct,
        )
        return result, m

    train_result, train_m = _run(train_bars, train_feat, train_ticks, "training")
    test_result, test_m = _run(test_bars, test_feat, test_ticks, "testing")

    if not args.no_save:
        run_dir = save_run(
            out_dir=args.out,
            name=f"random_seed{args.seed}",
            train_result=train_result,
            train_metrics=train_m,
            train_bars=train_bars,
            test_result=test_result,
            test_metrics=test_m,
            test_bars=test_bars,
            train_secondary=train_sec,
            test_secondary=test_sec,
            cfg=cfg,
        )
        log.info("Artifacts saved to %s", run_dir)


if __name__ == "__main__":
    main()
