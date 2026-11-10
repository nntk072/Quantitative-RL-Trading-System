#!/usr/bin/env python3
"""Exercise the survival policy runtime on a small synthetic market path.

This checks wiring and artifact round trips only. It does not measure or report
economic performance and its output cannot authorize model selection.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from omegaconf import OmegaConf

from configuration import load_config
from configuration.paths import repository_root
from decisioning.observations import OBSERVATION_SCHEMA_V2
from decisioning.trade_setup import NO_TRADE_ID, trade_setup_center
from evaluation.rollout.trained_policy_rollout import evaluate_model
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from learning.rl.agent import build_agent, validate_model_trade_setup_observation_schema
from learning.rl.checkpoint import load_sb3_training_checkpoint
from market_data.loading.ticks import TickBook
from market_data.transforms.sessions import add_session_id, add_session_labels
from simulation.environment import make_env

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/survival_trade_setup_mtf_conditioned.yaml"


def _synthetic_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create two development-calendar sessions with no market outcome claim."""
    indexes = [
        pd.date_range(
            f"2025-01-{day:02d} 15:00",
            periods=120,
            freq="1min",
            tz="Etc/GMT-3",
        )
        for day in (6, 7)
    ]
    index = pd.DatetimeIndex(indexes[0].append(indexes[1]))
    close = 20_000.0 + np.arange(len(index), dtype=np.float64) * 0.01
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "tickvol": 50,
            "volume": 2_000,
            "vol": 0,
            "spread": 0.6,
            "gap_flag": False,
        },
        index=index,
    )
    bars.index.name = "datetime"
    bars = add_session_id(add_session_labels(bars))

    setup_columns = [column for _, column in trade_setup_candidate_feature_columns()]
    features = pd.DataFrame(0.0, index=index, columns=setup_columns)
    features["reachable_r"] = np.nan
    # The fixture has no genuine market structure. Supply causal, bar-local
    # envelope values so configured strategy wiring receives its full schema;
    # phase flags stay inactive and the smoke policy takes no trades.
    for column in (
        "asian_high",
        "sweep_high",
        "po3_manipulation_high",
        "ifvg_bull_high",
        "ifvg_bear_high",
    ):
        features[column] = bars["high"]
    for column in (
        "asian_low",
        "sweep_low",
        "po3_manipulation_low",
        "ifvg_bull_low",
        "ifvg_bear_low",
    ):
        features[column] = bars["low"]
    features["po3_manipulation_end"] = 0.0
    features["po3_distribution"] = 0.0
    for timeframe in ("M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"):
        features[f"{timeframe}_smoke_context"] = 0.0
    return bars, features


def _build_environment(bars: pd.DataFrame, features: pd.DataFrame, cfg: Any) -> Any:
    mid = bars["close"].to_numpy(dtype=np.float64)
    half_spread = bars["spread"].to_numpy(dtype=np.float64) / 2.0
    tickbook = TickBook(
        pd.DatetimeIndex(bars.index).astype("int64").to_numpy(copy=True),
        mid - half_spread,
        mid + half_spread,
    )
    return make_env(
        bars,
        features,
        cfg,
        algo="ppo",
        reward="survival",
        episodic=False,
        tickbook=tickbook,
        arch=str(cfg.agent.arch),
    )


def _assert_finite_observation(observation: dict[str, np.ndarray[Any, Any]]) -> None:
    for key, value in observation.items():
        if not np.isfinite(np.asarray(value, dtype=np.float64)).all():
            raise RuntimeError(f"smoke observation contains nonfinite values in {key}")


def _validate_replay_action_mask(replay: dict[str, Any]) -> int:
    """Require every replay choice to be eligible under its observed mask."""
    decisions = replay.get("trade_setup_decisions")
    if not isinstance(decisions, pd.DataFrame) or decisions.empty:
        raise RuntimeError("evaluator did not return trade-setup mask decisions")
    required = {"trade_setup_candidate_id", "selection_valid", "eligible_trade_setup_ids"}
    if not required.issubset(decisions.columns):
        raise RuntimeError("evaluator trade-setup decisions omit mask-validation fields")
    for row in decisions.to_dict(orient="records"):
        selected_id = row["trade_setup_candidate_id"]
        eligible_ids = row["eligible_trade_setup_ids"]
        if (
            not bool(row["selection_valid"])
            or not isinstance(eligible_ids, list)
            or selected_id not in eligible_ids
            or NO_TRADE_ID not in eligible_ids
        ):
            raise RuntimeError("evaluator selected an ineligible setup or masked NO_TRADE")
    if len(decisions) != int(replay.get("n_steps", -1)):
        raise RuntimeError("evaluator omitted one or more trade-setup mask decisions")
    return len(decisions)


def _terminal_reward_check(bars: pd.DataFrame, features: pd.DataFrame, cfg: Any) -> float:
    env = _build_environment(bars, features, cfg)
    observation, _ = env.reset(seed=42)
    if not env.observation_space.contains(observation):
        raise RuntimeError("synthetic observation is outside the configured observation space")
    _assert_finite_observation(observation)
    action = np.zeros(env.action_space.shape, dtype=np.float32)
    action[env.action_schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
    total_reward = 0.0
    terminated = truncated = False
    final_info: dict[str, Any] = {}
    while not (terminated or truncated):
        observation, reward, terminated, truncated, final_info = env.step(action)
        _assert_finite_observation(observation)
        if not np.isfinite(reward):
            raise RuntimeError("smoke environment emitted a nonfinite reward")
        total_reward += float(reward)
    if terminated is not True or truncated is not False:
        raise RuntimeError("survival smoke did not terminate at the completed data split")
    if total_reward != 1.0 or final_info.get("reward_parts", {}).get("survival") != 1.0:
        raise RuntimeError("breach-free synthetic split did not emit the terminal survival reward")
    return total_reward


def run_smoke(config_path: Path, output_dir: Path) -> dict[str, Any]:
    """Run bounded policy learning, checkpoint reload, and evaluator replay."""
    if output_dir.exists():
        raise FileExistsError(f"smoke output directory must be fresh: {output_dir}")
    cfg = load_config(config_path=config_path)
    if str(cfg.env.reward_mode).lower() != "survival":
        raise ValueError("correctness smoke requires a survival-objective config")
    if str(cfg.env.observation_schema_version) != OBSERVATION_SCHEMA_V2:
        raise ValueError("correctness smoke requires the account-state-v2 observation contract")

    # These bounded values make the smoke practical while leaving the saved
    # research config and all scientific training parameters untouched.
    cfg.env.n_envs = 1
    cfg.env.obs_window = 16
    cfg.ppo.n_steps = 64
    cfg.ppo.batch_size = 32
    cfg.ppo.n_epochs = 1

    bars, features = _synthetic_inputs()
    env = _build_environment(bars, features, cfg)
    observation, _ = env.reset(seed=42)
    if not env.observation_space.contains(observation):
        raise RuntimeError("policy observation does not satisfy the configured schema")
    _assert_finite_observation(observation)
    schema = getattr(env, "trade_setup_observation_schema", None)
    if not isinstance(schema, dict):
        raise RuntimeError("full trade-setup observation schema was not constructed")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_agent(env, cfg, arch=str(cfg.agent.arch), device=device, seed=42)
    model.learn(total_timesteps=256, progress_bar=False)
    losses = model.logger.name_to_value
    policy_loss = float(losses["train/policy_gradient_loss"])
    if not np.isfinite(policy_loss):
        raise RuntimeError("bounded PPO smoke produced a nonfinite policy gradient loss")

    output_dir.mkdir(parents=True)
    checkpoint = output_dir / "policy_checkpoint.zip"
    model.save(checkpoint)
    loaded = load_sb3_training_checkpoint(checkpoint, env=env, device=device, algo="ppo")
    validate_model_trade_setup_observation_schema(loaded, schema)
    # Compare the same checkpoint weights on CPU so accelerator kernel
    # roundoff does not obscure save/load inference parity.
    device = "cpu"
    model.policy.to(device)
    loaded.policy.to(device)
    model.device = torch.device(device)
    loaded.device = torch.device(device)
    before, _ = model.predict(observation, deterministic=True)
    after, _ = loaded.predict(observation, deterministic=True)
    max_action_delta = float(np.max(np.abs(np.asarray(before) - np.asarray(after))))
    if not np.array_equal(before, after):
        raise RuntimeError(
            "deterministic policy output changed after checkpoint reload: "
            f"before={np.asarray(before).tolist()}, after={np.asarray(after).tolist()}, "
            f"max_delta={max_action_delta:.9g}"
        )

    evaluation_env = _build_environment(bars, features, cfg)
    replay = evaluate_model(
        loaded,
        bars,
        features,
        env=evaluation_env,
        deterministic=True,
        strategy_actions=bool(cfg.env.strategy_actions),
        trade_setup_actions=bool(cfg.env.trade_setup_actions),
    )
    legal_action_decisions = _validate_replay_action_mask(replay)
    equity = np.asarray(replay["equity"], dtype=np.float64)
    if equity.size == 0 or not np.isfinite(equity).all():
        raise RuntimeError("evaluator returned empty or nonfinite account equity")
    if replay.get("completed_data_split") is not True:
        raise RuntimeError("evaluator did not complete the synthetic data split")
    terminal_reward = _terminal_reward_check(bars, features, cfg)

    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    output = {
        "schema_version": "survival-correctness-smoke-v1",
        "source_commit": source_sha,
        "config_path": str(config_path.resolve()),
        "config_sha256": _sha256(config_path),
        "claim_scope": "synthetic implementation correctness only",
        "economic_result": False,
        "selection_allowed": False,
        "scientific_training_authorized": False,
        "synthetic_sessions": int(bars["session_id"].nunique()),
        "synthetic_bars": int(len(bars)),
        "architecture_exercised": str(cfg.agent.arch),
        "observation_keys": sorted(observation),
        "observation_shapes": {
            key: list(np.asarray(value).shape) for key, value in observation.items()
        },
        "action_shape": list(env.action_space.shape),
        "trade_setup_schema": schema,
        "bounded_ppo_steps": 256,
        "finite_policy_gradient_loss": policy_loss,
        "checkpoint_sha256": _sha256(checkpoint),
        "checkpoint_reload_action_parity": True,
        "evaluator_completed_split": True,
        "evaluator_steps": int(replay["n_steps"]),
        "evaluator_equity_finite": True,
        "evaluator_action_mask_legal": True,
        "evaluator_action_mask_decisions": legal_action_decisions,
        "terminal_breach_free_reward": terminal_reward,
        "runtime_overrides": {
            "env.n_envs": 1,
            "env.obs_window": 16,
            "ppo.n_steps": 64,
            "ppo.batch_size": 32,
            "ppo.n_epochs": 1,
        },
    }
    summary_path = output_dir / "smoke_summary.json"
    summary_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "resolved_smoke_config.yaml").write_text(
        OmegaConf.to_yaml(cfg, resolve=True), encoding="utf-8"
    )
    return output


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    output = run_smoke(config_path.resolve(), args.output_dir.expanduser().resolve())
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
