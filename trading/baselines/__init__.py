"""Baseline strategies for fair comparison against RL agents."""

from .breakout import MultiLevelBreakoutStrategy
from .cash_hold import fit_hold_lots, simulate_hold, swap_usd_per_lot
from .classical import BuyAndHoldStrategy, EMAMACDRSIStrategy, SessionMomentumStrategy
from .lstm_classifier import LSTMStrategy, LSTMSweepClassifier, build_sweep_dataset
from .rule_based import (
    ema_crossover,
    macd_baseline,
    macd_ema50_baseline,
    rsi_mean_reversion,
)
from .step_indexed_strategy import BaseStrategy

__all__ = [
    "BaseStrategy",
    "BuyAndHoldStrategy",
    "EMAMACDRSIStrategy",
    "SessionMomentumStrategy",
    "LSTMSweepClassifier",
    "LSTMStrategy",
    "MultiLevelBreakoutStrategy",
    "fit_hold_lots",
    "simulate_hold",
    "swap_usd_per_lot",
    "build_sweep_dataset",
    "ema_crossover",
    "macd_baseline",
    "macd_ema50_baseline",
    "rsi_mean_reversion",
]
