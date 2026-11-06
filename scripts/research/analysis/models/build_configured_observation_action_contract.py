"""Build the current configured train-only model observation/action contract.

The command constructs the configured feature matrix and a fresh TradingEnv,
then records schemas and tensor shapes without taking a policy action or
stepping the simulator. It is an architecture/input contract report, not an
evaluation result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from argparse import Namespace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256
from configuration.paths import repository_root
from evaluation.reporting.run_manifest import array_sha256, dataset_record
from features import build_features, feature_cache_path
from features.context.policy_market import attach_policy_market_context
from market_data.loading import build_tick_books, run_pipeline
from market_data.loading.ticks import ticks_covering
from market_data.splits.definitions import (
    get_split_config,
    get_train_start_config,
    make_train_mask,
)
from simulation.environment import make_env
from training.artifacts.manifests import (
    action_schema_manifest,
    observation_schema_manifest,
    observation_space_shapes,
    sequence_feature_schema_manifest,
)
from training.configuration.cli import load_merged_config
from training.setup.environments import _training_episodic


def _through_train_end(frame: pd.DataFrame, train_end: str) -> pd.DataFrame:
    """Keep warm-up and training rows while excluding later report dates."""
    index = pd.DatetimeIndex(frame.index)
    return frame.loc[make_train_mask(index, train_end)]


def _source_files(cfg: Any, root: Path) -> list[dict[str, str]]:
    """Hash configured local training inputs and the session schedule."""
    spec = cfg.data.datasets.training
    raw_dir = Path(str(spec.raw_dir))
    if not raw_dir.is_absolute():
        raw_dir = root / raw_dir
    candidates: dict[str, Path] = {}
    for symbol, filename in spec.m1_files.items():
        candidates[f"M1:{symbol}"] = raw_dir / str(filename)
    for timeframe, symbol_files in spec.get("timeframe_files", {}).items():
        for symbol, filename in symbol_files.items():
            candidates[f"{timeframe}:{symbol}"] = raw_dir / str(filename)
    for symbol, filename in spec.get("tick_files", {}).items():
        candidates[f"ticks:{symbol}"] = raw_dir / str(filename)
    schedule = Path(str(cfg.data.session_schedule_file))
    if not schedule.is_absolute():
        schedule = root / schedule
    candidates["session_schedule"] = schedule
    records = []
    for role, path in sorted(candidates.items()):
        if not path.is_file():
            raise FileNotFoundError(f"configured local input is missing: {role}: {path}")
        records.append(
            {
                "role": role,
                "path": path.relative_to(root).as_posix()
                if path.is_relative_to(root)
                else str(path),
                "sha256": file_sha256(path),
            }
        )
    return records


def _implementation_sources(root: Path) -> list[dict[str, str]]:
    """Hash the code that resolves data and constructs the reported contract."""
    paths = (
        "scripts/research/analysis/models/build_configured_observation_action_contract.py",
        "configuration/configuration_loader.py",
        "training/configuration/cli.py",
        "training/runner/data_stage.py",
        "features/pipeline/feature_matrix_builder.py",
        "features/context/policy_market.py",
        "simulation/environment/trading_environment_factory.py",
        "simulation/environment/action_episode_initialization.py",
        "simulation/environment/env.py",
        "simulation/environment/observations.py",
        "simulation/environment/observation_arrays_initialization.py",
        "simulation/environment/observation_runtime.py",
        "learning/rl/hybrid.py",
        "learning/rl/agent.py",
        "decisioning/trade_setup.py",
        "training/artifacts/manifests.py",
    )
    return [{"path": path, "sha256": file_sha256(root / path)} for path in paths]


def build_report(config_path: Path, output_path: Path, cache_root: Path) -> dict[str, Any]:
    """Resolve and instantiate the configured environment without evaluation."""
    root = repository_root(__file__)
    resolved_config = config_path if config_path.is_absolute() else root / config_path
    if not resolved_config.is_file():
        raise FileNotFoundError(resolved_config)

    args = Namespace(
        config=str(resolved_config),
        overrides=[],
        strategy="baseline",
        variant=None,
        quality_variant=None,
        algo="ppo",
        arch=None,
        reward="dsr",
        use_vae=False,
        vae_path=None,
        vae_config="config/vae.yaml",
        force=False,
        mvp=False,
    )
    cfg = load_merged_config(args)
    args.arch = str(cfg.agent.get("arch", "tcn"))
    cache_root.mkdir(parents=True, exist_ok=True)
    cfg.data.cache_dir = str(cache_root / "market_data")

    # Restrict feature construction to local training inputs and the configured
    # training cutoff. Earlier bars remain available for causal warm-up.
    datasets = run_pipeline(cfg, datasets=["training"])
    primary_symbol = str(cfg.data.primary)
    secondary_symbol = str(cfg.data.secondary)
    train_end, _test_start = get_split_config(cfg)
    train_start = get_train_start_config(cfg)
    primary_timeframes = {
        str(tf): _through_train_end(frame, train_end)
        for tf, frame in datasets[primary_symbol].items()
    }
    secondary_timeframes = {
        str(tf): _through_train_end(frame, train_end)
        for tf, frame in datasets.get(secondary_symbol, {}).items()
    }
    primary_m1 = primary_timeframes["M1"]
    secondary_m1 = secondary_timeframes.get("M1")
    train_mask = make_train_mask(pd.DatetimeIndex(primary_m1.index), train_end, train_start)
    if not bool(train_mask.any()):
        raise ValueError("configured training window contains no primary M1 rows")

    feature_cache = feature_cache_path(
        cache_root / "features",
        primary_symbol,
        cfg,
        primary_m1,
        train_mask=train_mask,
        secondary=secondary_m1,
        timeframe_bars=primary_timeframes,
        secondary_timeframe_bars=secondary_timeframes,
    )
    feature_cache.parent.mkdir(parents=True, exist_ok=True)
    features = build_features(
        primary_m1,
        secondary=secondary_m1,
        cfg=cfg,
        train_mask=train_mask,
        cache_path=feature_cache,
        timeframe_bars=primary_timeframes,
        secondary_timeframe_bars=secondary_timeframes,
    )
    tickbook = build_tick_books(
        cfg,
        symbols=[primary_symbol],
        datasets=["training"],
    ).get(primary_symbol)
    if tickbook is None:
        raise ValueError("configured training tick book is unavailable")
    schedule = Path(str(cfg.data.session_schedule_file))
    if not schedule.is_absolute():
        schedule = root / schedule
    features = attach_policy_market_context(
        primary_m1,
        features,
        tickbook,
        schedule_path=schedule,
        session_start=str(cfg.session.start),
        session_end=str(cfg.session.end),
    )

    train_bars = primary_m1.loc[train_mask]
    train_features = features.loc[train_mask]
    if train_bars.empty or not train_bars.index.equals(train_features.index):
        raise ValueError("configured train bars and features are empty or misaligned")
    train_tickbook = ticks_covering(tickbook, train_bars)
    if train_tickbook is None:
        raise ValueError("configured train period has no primary tick data")
    env = make_env(
        train_bars,
        train_features,
        cfg,
        algo=args.algo,
        reward=args.reward,
        episodic=_training_episodic(cfg),
        tickbook=train_tickbook,
        arch=args.arch,
    )
    observation, _info = env.reset(seed=0)
    observed_shapes = (
        {str(key): list(np.asarray(value).shape) for key, value in observation.items()}
        if isinstance(observation, dict)
        else {"observation": list(np.asarray(observation).shape)}
    )
    source_files = _source_files(cfg, root)
    conditioned = str(cfg.ppo.get("policy_distribution", "")) == "trade_setup_conditioned_v1"
    conditioned_cfg = cfg.ppo.get("trade_setup_conditioned", {})
    report: dict[str, Any] = {
        "schema_version": "configured-observation-action-contract-v1",
        "scope": {
            "config": resolved_config.relative_to(root).as_posix(),
            "period_role": "training_only",
            "train_start": str(train_bars.index[0]),
            "train_end": str(train_bars.index[-1]),
            "warmup_start": str(primary_m1.index[0]),
            "primary_symbol": primary_symbol,
            "secondary_symbol": secondary_symbol,
            "algo": args.algo,
            "architecture": args.arch,
            "reward_selector": args.reward,
            "environment_steps": 0,
            "policy_actions": 0,
            "trades_or_economics": False,
            "report_period_rows_used": 0,
        },
        "identity": {
            "repository_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "repository_worktree_dirty": bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=root, text=True
                ).strip()
            ),
            "config_sha256": file_sha256(resolved_config),
            "resolved_config_sha256": hashlib.sha256(
                json.dumps(
                    OmegaConf.to_container(cfg, resolve=True), sort_keys=True, default=str
                ).encode()
            ).hexdigest(),
            "source_files": source_files,
            "implementation_sources": _implementation_sources(root),
            "dataset_records": {
                "train_bars": dataset_record(train_bars),
                "train_features": dataset_record(train_features),
                "primary_ticks_train_slice": {
                    "rows": int(len(train_tickbook._ts)),
                    "sha256": hashlib.sha256(
                        "".join(
                            array_sha256(array)
                            for array in (
                                train_tickbook._ts,
                                train_tickbook._bid,
                                train_tickbook._ask,
                            )
                        ).encode()
                    ).hexdigest(),
                },
            },
        },
        "observation": {
            "space_shapes": observation_space_shapes(env),
            "reset_output_shapes": observed_shapes,
            "schema": observation_schema_manifest(env),
            "sequence_feature_schema": sequence_feature_schema_manifest(env),
        },
        "action": {
            "space_shape": list(env.action_space.shape)
            if getattr(env.action_space, "shape", None)
            else None,
            "schema": action_schema_manifest(env),
        },
        "policy_configuration": {
            "distribution": str(cfg.ppo.get("policy_distribution", "default")),
            "actor_architecture": str(cfg.ppo.get("actor_arch", "default")),
            "trade_setup_actions": bool(cfg.env.get("trade_setup_actions", False)),
            "setup_conditioned_execution": conditioned,
            "setup_embedding_dim": (
                int(conditioned_cfg.get("embedding_dim", 32)) if conditioned else None
            ),
            "execution_hidden_dim": (
                int(conditioned_cfg.get("execution_hidden_dim", 128)) if conditioned else None
            ),
        },
        "interpretation": (
            "Resolved current configuration and local training-only inputs instantiated the "
            "environment contract. Reset was used only to confirm returned observation shapes; "
            "no action, environment step, policy inference, checkpoint, or economic result was used."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_path, report, default=str)
    return report


def main() -> None:
    """Run the configured contract builder."""
    root = repository_root(__file__)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/research/trade_setup_mtf_reasoning_2m.yaml"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "evidence/research/model_observation_and_action_semantics/"
            "configured_trade_setup_mtf_contract.json"
        ),
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path(
            "/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/"
            "model_observation_contract_cache"
        ),
    )
    options = parser.parse_args()
    report = build_report(
        options.config if options.config.is_absolute() else root / options.config,
        options.output if options.output.is_absolute() else root / options.output,
        options.cache_root,
    )
    print(
        "configured model contract: "
        f"train_rows={report['identity']['dataset_records']['train_bars']['rows']} "
        f"observation={report['observation']['space_shapes']} "
        f"action={report['action']['schema']} output={options.output}"
    )


if __name__ == "__main__":
    main()
