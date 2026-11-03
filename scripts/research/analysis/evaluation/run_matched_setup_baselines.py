"""Build and evaluate matched setup controls on one declared local data split.

This command runs the Tier 0 always-no-trade and random-eligible-setup controls
through the shared configured ``TradingEnv`` path, then writes an immutable
content-addressed evidence bundle. It does not train a policy or choose a
candidate model. Use the development period for exploratory comparisons;
``exposed_report_only`` is available only for an explicitly labeled report.

Run on an appropriate compute allocation because feature and tick construction
can require substantial CPU and memory.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pandas as pd
from omegaconf import DictConfig

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from decisioning.trade_setup import (
    TRADE_SETUP_IDEAS,
    TRADE_SETUP_TIMEFRAMES,
    build_trade_setup_action_schema,
)
from evaluation.reporting.matched_setup_baseline_bundle import (
    write_matched_setup_baseline_bundle,
)
from evaluation.rollout.matched_setup_baselines import (
    RuleSetupBaselineArm,
    evaluate_tier0_setup_baselines,
)
from evaluation.rollout.structure_priority_setup import (
    StructurePrioritySetupPolicy,
    StructurePrioritySetupRolloutModel,
)
from features import build_features, feature_cache_path
from features.context.policy_market import attach_policy_market_context
from market_data.loading import build_tick_books, run_pipeline
from market_data.splits.definitions import (
    get_split_config,
    get_train_start_config,
    make_train_mask,
    split_train_test,
)

_DEFAULT_PROTOCOL = (
    "evidence/research/releases/negative-evidence-readiness/RESEARCH_QUESTIONS_AND_METHODS.md"
)
_DEFAULT_ARTIFACT_ROOT = "evidence/research/matched_setup_baselines"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the immutable input and evaluation choices."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Resolved config or overlay")
    parser.add_argument(
        "--period-role",
        choices=("development", "exposed_report_only"),
        required=True,
        help="Declare which configured chronological split is evaluated",
    )
    parser.add_argument("--dataset", default="training", help="Configured local dataset name")
    parser.add_argument("--execution-seed", type=int, required=True)
    parser.add_argument("--random-policy-seed", type=int, required=True)
    parser.add_argument("--absolute-risk-budget-usd", type=float, required=True)
    parser.add_argument("--normalized-risk", type=float, default=0.5)
    parser.add_argument("--trade-probability", type=float, default=1.0)
    parser.add_argument(
        "--include-structure-priority",
        action="store_true",
        help=(
            "also evaluate the fixed Tier 1 structure rule using canonical "
            "setup-family and timeframe order"
        ),
    )
    parser.add_argument("--tick-fill-slippage-points", type=float, default=0.0)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=42)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path(_DEFAULT_ARTIFACT_ROOT),
        help="Immutable bundle root inside the repository",
    )
    parser.add_argument(
        "--overrides",
        nargs="*",
        default=(),
        help="Validated config key=value overrides applied after the selected config",
    )
    return parser.parse_args(argv)


def _additional_policies(
    cfg: DictConfig,
    *,
    include_structure_priority: bool,
    normalized_risk: float,
) -> dict[str, RuleSetupBaselineArm]:
    """Build explicitly requested fixed rules against the configured action schema."""
    if not include_structure_priority:
        return {}
    action_schema = build_trade_setup_action_schema(
        has_sl_mode=bool(cfg.env.allow_agent_sl_mode),
        has_tp_mode=bool(cfg.env.allow_agent_tp_mode),
        has_multi_tp=bool(cfg.env.allow_multi_tp),
        has_simplex=bool(cfg.env.allow_multi_tp and cfg.env.allow_simplex),
    )
    structure_rule = StructurePrioritySetupPolicy(
        action_schema,
        idea_priority=TRADE_SETUP_IDEAS,
        timeframe_priority=TRADE_SETUP_TIMEFRAMES,
        normalized_risk=normalized_risk,
    )
    return {
        "structure_priority": RuleSetupBaselineArm(
            StructurePrioritySetupRolloutModel(structure_rule)
        )
    }


def select_period(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    cfg: Any,
    period_role: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select the configured development or exposed report split explicitly."""
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise TypeError("matched setup evaluation requires a DatetimeIndex")
    if len(bars) != len(features) or not bars.index.equals(features.index):
        raise ValueError("bars and features must have identical rows and ordered timestamps")
    train_end, test_start = get_split_config(cfg)
    train_start = get_train_start_config(cfg)
    train_bars, report_bars, train_features, report_features = split_train_test(
        bars, features, train_end, test_start, train_start
    )
    if period_role == "development":
        selected_bars, selected_features = train_bars, train_features
    elif period_role == "exposed_report_only":
        report_index = cast(pd.DatetimeIndex, report_bars.index)
        selected_dates = (
            report_index.tz_localize(None) if report_index.tz is not None else report_index
        )
        exposed_mask = (selected_dates >= pd.Timestamp("2026-01-01")) & (
            selected_dates < pd.Timestamp("2026-10-17")
        )
        selected_bars = report_bars.loc[exposed_mask]
        selected_features = report_features.loc[exposed_mask]
    else:
        raise ValueError("period_role must be development or exposed_report_only")
    if selected_bars.empty:
        raise ValueError(f"configured {period_role} split is empty")
    return selected_bars, selected_features


def _source_files(cfg: DictConfig, dataset_name: str, config_path: Path) -> dict[str, Path]:
    """Resolve and name local source inputs included in bundle provenance."""
    data_cfg = cfg.data
    datasets = data_cfg.get("datasets")
    if not isinstance(datasets, Mapping) or dataset_name not in datasets:
        raise ValueError(f"configured local dataset is missing: {dataset_name}")
    dataset = datasets[dataset_name]
    raw_root = Path(str(dataset.raw_dir)).expanduser()
    if not raw_root.is_absolute():
        raw_root = repository_root() / raw_root
    sources: dict[str, Path] = {"selected_config": config_path.resolve()}

    for symbol_value in data_cfg.symbols:
        symbol = str(symbol_value)
        m1_name = dataset.m1_files.get(symbol)
        if m1_name:
            sources[f"{dataset_name}_{symbol}_M1"] = raw_root / str(m1_name)
        for timeframe, by_symbol in dataset.get("timeframe_files", {}).items():
            filename = by_symbol.get(symbol)
            if filename:
                sources[f"{dataset_name}_{symbol}_{str(timeframe).upper()}"] = raw_root / str(
                    filename
                )
        tick_name = dataset.get("tick_files", {}).get(symbol)
        if tick_name:
            sources[f"{dataset_name}_{symbol}_ticks"] = raw_root / str(tick_name)

    schedule = Path(str(data_cfg.session_schedule_file)).expanduser()
    if not schedule.is_absolute():
        schedule = repository_root() / schedule
    sources["configured_session_schedule"] = schedule
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"local provenance inputs are missing: {missing}")
    return sources


def _prepare_inputs(
    cfg: DictConfig,
    *,
    dataset_name: str,
    period_role: str,
    config_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, Any, dict[str, Path]]:
    """Run the configured local data/features path with train-only fitting."""
    repository = repository_root()
    data = run_pipeline(cfg, datasets=[dataset_name])
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    if primary_symbol not in data or "M1" not in data[primary_symbol]:
        raise ValueError(f"configured dataset has no M1 bars for {primary_symbol}")
    primary = data[primary_symbol]["M1"]
    secondary = data.get(secondary_symbol, {}).get("M1")
    primary_timeframes = data[primary_symbol]
    secondary_timeframes = data.get(secondary_symbol, {})
    train_end, _ = get_split_config(cfg)
    train_start = get_train_start_config(cfg)
    train_mask = make_train_mask(cast(pd.DatetimeIndex, primary.index), train_end, train_start)

    cache_dir = Path(str(cfg.data.cache_dir)).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = repository / cache_dir
    cache_path = feature_cache_path(
        cache_dir,
        primary_symbol,
        cfg,
        primary,
        train_mask=train_mask,
        secondary=secondary,
        timeframe_bars=primary_timeframes,
        secondary_timeframe_bars=secondary_timeframes,
    )
    features = build_features(
        primary,
        secondary=secondary,
        cfg=cfg,
        train_mask=train_mask,
        cache_path=cache_path,
        timeframe_bars=primary_timeframes,
        secondary_timeframe_bars=secondary_timeframes,
    )
    tickbook = build_tick_books(
        cfg,
        symbols=[primary_symbol],
        datasets=[dataset_name],
    ).get(primary_symbol)
    if tickbook is None:
        raise ValueError("matched local-data setup baseline requires a configured TickBook")
    schedule_path = Path(str(cfg.data.session_schedule_file)).expanduser()
    if not schedule_path.is_absolute():
        schedule_path = repository / schedule_path
    features = attach_policy_market_context(
        primary,
        features,
        tickbook,
        schedule_path=schedule_path,
        session_start=str(cfg.session.start),
        session_end=str(cfg.session.end),
    )
    selected_bars, selected_features = select_period(primary, features, cfg, period_role)
    return (
        selected_bars,
        selected_features,
        tickbook,
        _source_files(cfg, dataset_name, config_path),
    )


def main(argv: Sequence[str] | None = None) -> Path:
    """Evaluate matched Tier 0 controls and persist their evidence bundle."""
    args = parse_args(argv)
    repo = repository_root()
    os.chdir(repo)
    config_path = args.config.expanduser()
    if not config_path.is_absolute():
        config_path = repo / config_path
    config_path = config_path.resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"selected config is missing: {config_path}")
    cfg = load_config(list(args.overrides), config_path=config_path)
    bars, features, tickbook, source_files = _prepare_inputs(
        cfg,
        dataset_name=args.dataset,
        period_role=args.period_role,
        config_path=config_path,
    )
    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        tickbook,
        execution_seed=args.execution_seed,
        random_policy_seed=args.random_policy_seed,
        period_role=args.period_role,
        absolute_risk_budget_usd=args.absolute_risk_budget_usd,
        normalized_risk=args.normalized_risk,
        trade_probability=args.trade_probability,
        tick_fill_slippage_points=args.tick_fill_slippage_points,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
        additional_policies=_additional_policies(
            cfg,
            include_structure_priority=args.include_structure_priority,
            normalized_risk=args.normalized_risk,
        ),
    )
    artifact_root = args.artifact_root.expanduser()
    if not artifact_root.is_absolute():
        artifact_root = repo / artifact_root
    artifact_root = artifact_root.resolve()
    try:
        artifact_root.relative_to(repo.resolve())
    except ValueError as exc:
        raise ValueError("artifact-root must remain inside the repository") from exc
    regeneration_command = f"cd {shlex.quote(str(repo.resolve()))} && " + shlex.join(
        [
            sys.executable,
            "-m",
            "scripts.research.analysis.evaluation.run_matched_setup_baselines",
            *(argv or sys.argv[1:]),
        ]
    )
    bundle = write_matched_setup_baseline_bundle(
        outputs,
        cfg,
        bars,
        features,
        tickbook,
        output_root=artifact_root,
        artifact_root=artifact_root,
        source_repository=repo,
        config_path=config_path,
        protocol_path=_DEFAULT_PROTOCOL,
        regeneration_command=regeneration_command,
        symbols=[str(cfg.data.primary)],
        timeframes=[str(timeframe) for timeframe in cfg.data.timeframes],
        source_files=source_files,
    )
    print(f"matched setup baseline bundle: {bundle}")
    return bundle


if __name__ == "__main__":
    main()
