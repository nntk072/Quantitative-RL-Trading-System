from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

PUBLIC_PACKAGES = (
    "configuration",
    "artifacts",
    "market_data",
    "features",
    "trading",
    "simulation",
    "models",
    "decisioning",
    "learning",
    "training",
    "evaluation",
    "evaluation.plotting",
    "experiments",
    "live",
    "integrations",
    "compute",
    "orchestra",
    "simulation.backtest.cross_validation.backtrader_runner",
    "simulation.backtest.cross_validation.main",
)
PUBLIC_CLIS = (
    "market_data.cli",
    "training.cli",
    "evaluation.cli",
    "experiments.cli",
    "compute.cli",
)


def test_public_packages_import() -> None:
    for name in PUBLIC_PACKAGES:
        assert importlib.import_module(name) is not None


def test_mt5_package_exposes_lazy_integration_api() -> None:
    package = importlib.import_module("integrations.mt5")

    assert set(package.__all__) == {
        "MT5Data",
        "MT5Trader",
        "RiskManager",
        "ensure_mt5_logged_in",
    }


def test_trading_domain_public_apis_are_reexported() -> None:
    from trading import AccountState, TradingPolicyConfig, resolve_trading_policy
    from trading.execution import protective_level_fill_quote
    from trading.orders import (
        TIMEFRAME_ORDER,
        OrderGeometry,
        dynamic_tp,
        manipulation_state,
        place_strategy_order,
        reference_timeframe,
        resolve_strategy_entry,
        source_timeframe,
        stop_menu,
        target_menu,
    )
    from trading.risk import (
        FTMOGuardrails,
        RiskBudgetDecision,
        approve_dynamic_risk,
        compute_lots,
    )

    assert AccountState is not None
    assert TradingPolicyConfig is not None
    assert callable(resolve_trading_policy)
    assert OrderGeometry is not None
    assert all(
        callable(value)
        for value in (
            dynamic_tp,
            manipulation_state,
            place_strategy_order,
            resolve_strategy_entry,
            stop_menu,
            target_menu,
        )
    )
    assert callable(protective_level_fill_quote)
    assert callable(dynamic_tp)
    assert TIMEFRAME_ORDER[-2:] == ("D1", "W1")
    assert reference_timeframe("H2_swing_low") == "H2"
    assert reference_timeframe("london_low") == "D1"
    assert source_timeframe("london_low") == ""
    assert FTMOGuardrails is not None
    assert RiskBudgetDecision is not None
    assert callable(approve_dynamic_risk)
    assert callable(compute_lots)


def test_simulation_package_exports_are_stable() -> None:
    from simulation.backtest import run_backtest
    from simulation.environment import TradingEnv, build_eval_common, make_env

    assert callable(run_backtest)
    assert TradingEnv is not None
    assert callable(build_eval_common)
    assert callable(make_env)


def test_market_data_and_feature_package_exports_are_stable() -> None:
    from features import build_features
    from market_data import BAR_CACHE_VERSION, build_tick_books, run_pipeline, split_train_test

    assert callable(build_features)
    assert callable(build_tick_books)
    assert callable(run_pipeline)
    assert callable(split_train_test)
    assert BAR_CACHE_VERSION


def test_model_and_training_artifact_apis_are_public() -> None:
    from learning.rl.ppo import ClampedStdMultiInputPolicy
    from models.encoders import TCNEncoder
    from models.factory import ENCODER_TYPES, encoder_for
    from training.artifacts import (
        attach_run_log,
        build_training_log,
        entry_funnel_by_split,
        write_evaluation_artifacts,
        write_run_config_snapshot,
    )

    assert encoder_for("tcn") is TCNEncoder
    assert ENCODER_TYPES["tcn"] is TCNEncoder
    assert ClampedStdMultiInputPolicy.__module__ == "learning.rl.ppo"
    assert callable(attach_run_log)
    assert callable(build_training_log)
    assert callable(entry_funnel_by_split)
    assert callable(write_evaluation_artifacts)
    assert callable(write_run_config_snapshot)


def test_backtrader_compatibility_entrypoint_forwards_to_named_runner() -> None:
    from simulation.backtest.cross_validation.backtrader_runner import main as named_main
    from simulation.backtest.cross_validation.main import main as compatibility_main

    assert compatibility_main is named_main


def test_stable_cli_modules_import() -> None:
    for name in PUBLIC_CLIS:
        module = importlib.import_module(name)
        assert callable(module.main)


def test_top_level_packages_are_included_in_wheel() -> None:
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    wheel_packages = set(config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])
    public_roots = {name.split(".", maxsplit=1)[0] for name in PUBLIC_PACKAGES}

    assert public_roots <= wheel_packages
