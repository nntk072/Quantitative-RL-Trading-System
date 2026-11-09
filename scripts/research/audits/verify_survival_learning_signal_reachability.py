#!/usr/bin/env python3
"""Verify that the survival terminal signal can reach PPO policy gradients.

This is a correctness preflight, not a performance pilot. It proves the
gamma=1/lambda=1 terminal-reward propagation and a finite non-zero clipped PPO
policy gradient on synthetic success and breach trajectories.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from omegaconf import OmegaConf

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)


def terminal_gae(
    rewards: NDArray[np.float64],
    *,
    gamma: float = 1.0,
    gae_lambda: float = 1.0,
) -> NDArray[np.float64]:
    """Compute zero-value GAE for one terminal synthetic trajectory."""
    if rewards.ndim != 1 or rewards.size < 2:
        raise ValueError("synthetic trajectory requires at least two rewards")
    if not np.isfinite(rewards).all():
        raise ValueError("synthetic rewards must be finite")
    advantages = np.zeros_like(rewards, dtype=np.float64)
    running = 0.0
    for index in range(len(rewards) - 1, -1, -1):
        running = float(rewards[index]) + gamma * gae_lambda * running
        advantages[index] = running
    return advantages


def clipped_policy_gradient(advantage: float) -> float:
    """Return one synthetic PPO clipped-loss gradient magnitude."""
    if not math.isfinite(advantage) or advantage == 0.0:
        raise ValueError("advantage must be finite and non-zero")
    logit = torch.tensor(0.0, dtype=torch.float64, requires_grad=True)
    distribution = torch.distributions.Categorical(
        logits=torch.stack((torch.tensor(0.0, dtype=torch.float64), logit))
    )
    action = torch.tensor(1)
    new_log_prob = distribution.log_prob(action)  # type: ignore[no-untyped-call]
    old_log_prob = new_log_prob.detach()
    ratio = torch.exp(new_log_prob - old_log_prob)
    clipped = torch.clamp(ratio, 0.8, 1.2)
    adv = torch.tensor(float(advantage), dtype=torch.float64)
    loss = -torch.minimum(ratio * adv, clipped * adv)
    loss.backward()  # type: ignore[no-untyped-call]
    if logit.grad is None:
        raise ValueError("synthetic PPO gradient is unavailable")
    gradient = float(logit.grad.item())
    if not math.isfinite(gradient):
        raise ValueError("synthetic PPO gradient is non-finite")
    return abs(gradient)


def build_report(config_path: Path, *, path_length: int = 8) -> dict[str, Any]:
    """Validate current survival config and synthetic signal propagation."""
    if path_length < 2:
        raise ValueError("path_length must be at least two")
    cfg = OmegaConf.load(config_path)
    reward_mode = str(OmegaConf.select(cfg, "env.reward_mode", default="")).strip().lower()
    gamma = float(OmegaConf.select(cfg, "ppo.gamma", default=0.99))
    gae_lambda = float(OmegaConf.select(cfg, "ppo.gae_lambda", default=0.95))
    if reward_mode != "survival":
        raise ValueError("reachability preflight requires env.reward_mode=survival")
    if gamma != 1.0 or gae_lambda != 1.0:
        raise ValueError("survival reachability requires PPO gamma=1 and gae_lambda=1")

    success_rewards = np.zeros(path_length, dtype=np.float64)
    success_rewards[-1] = 1.0
    breach_rewards = np.zeros(path_length, dtype=np.float64)
    breach_rewards[-1] = -1.0
    success_advantages = terminal_gae(success_rewards, gamma=gamma, gae_lambda=gae_lambda)
    breach_advantages = terminal_gae(breach_rewards, gamma=gamma, gae_lambda=gae_lambda)
    success_gradient = clipped_policy_gradient(float(success_advantages[0]))
    breach_gradient = clipped_policy_gradient(float(breach_advantages[0]))

    status = (
        "pass"
        if (
            np.all(success_advantages > 0.0)
            and np.all(breach_advantages < 0.0)
            and success_gradient > 0.0
            and breach_gradient > 0.0
        )
        else "fail"
    )
    return {
        "schema_version": "survival-learning-signal-reachability-v1",
        "status": status,
        "config": str(config_path.resolve()),
        "reward_mode": reward_mode,
        "gamma": gamma,
        "gae_lambda": gae_lambda,
        "path_length": path_length,
        "success_terminal_reward": 1.0,
        "breach_terminal_reward": -1.0,
        "success_advantages": success_advantages.tolist(),
        "breach_advantages": breach_advantages.tolist(),
        "success_policy_gradient_magnitude": success_gradient,
        "breach_policy_gradient_magnitude": breach_gradient,
        "interpretation": (
            "Synthetic correctness proof only. Production terminal exposure remains "
            "separately gated by the current full-path compute contract."
        ),
    }


def main() -> int:
    """Run the synthetic PPO terminal-signal reachability preflight."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config/research/survival_trade_setup_mtf_conditioned.yaml",
    )
    parser.add_argument("--path-length", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = args.config if args.config.is_absolute() else ROOT / args.config
    report = build_report(config.resolve(), path_length=args.path_length)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
