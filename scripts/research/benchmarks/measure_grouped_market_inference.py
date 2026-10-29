"""Bounded full-policy A/B for repeated, exactly identical MTF market rows.

This is an inference-only measurement over observations reset from the pinned
training bundle. It does not train, alter checkpoints, or modify the simulator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from omegaconf import OmegaConf
from stable_baselines3.common.utils import obs_as_tensor

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.research.benchmarks.measure_ppo_throughput import (  # noqa: E402
    _prepare_bundle,
    _scale_profile_config,
)

from learning.rl.agent import build_agent  # noqa: E402
from models.encoders.mtf_shared_tcn_reasoning import SharedTCNMTFReasoningEncoder  # noqa: E402
from simulation.environment.spec import EnvSpec  # noqa: E402
from simulation.environment.worker import make_bundle_env  # noqa: E402
from training.runner.seed import _setup_rngs  # noqa: E402


class _EncoderForward(torch.nn.Module):
    """Route policy feature extraction through a selected inference path."""

    def __init__(
        self,
        encoder: SharedTCNMTFReasoningEncoder,
        feature_forward: Callable[[dict[str, torch.Tensor]], torch.Tensor],
    ) -> None:
        super().__init__()
        self.encoder = encoder
        self.features_dim = encoder.features_dim
        self.feature_forward = feature_forward

    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        return self.feature_forward(observations)


def _market_row_groups(
    observations: dict[str, np.ndarray[Any, Any]],
    encoder: SharedTCNMTFReasoningEncoder,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], str]:
    """Group rows by exact bytes for every market sequence and mask."""
    representatives: list[int] = []
    inverse: list[int] = []
    buckets: dict[bytes, list[int]] = {}
    digest = hashlib.sha256()
    market_keys = tuple(
        key for seq_key, mask_key, _, _ in encoder.streams for key in (seq_key, mask_key)
    )
    batch_size = len(observations["account"])
    for row in range(batch_size):
        row_digest = hashlib.sha256()
        for key in market_keys:
            value = np.ascontiguousarray(observations[key][row])
            row_digest.update(key.encode("utf-8"))
            row_digest.update(value.dtype.str.encode("ascii"))
            row_digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
            row_digest.update(value.tobytes())
        fingerprint = row_digest.digest()
        group = None
        for candidate_group in buckets.get(fingerprint, []):
            candidate = representatives[candidate_group]
            if all(
                np.array_equal(observations[key][row], observations[key][candidate])
                for key in market_keys
            ):
                group = candidate_group
                break
        if group is None:
            group = len(representatives)
            representatives.append(row)
            buckets.setdefault(fingerprint, []).append(group)
        inverse.append(group)
        for key in market_keys:
            digest.update(np.ascontiguousarray(observations[key][row]).tobytes())
    return (
        np.asarray(representatives, dtype=np.int64),
        np.asarray(inverse, dtype=np.int64),
        digest.hexdigest(),
    )


def _max_abs(left: torch.Tensor, right: torch.Tensor) -> float:
    if left.numel() == 0:
        return 0.0
    return float((left.detach() - right.detach()).abs().max().cpu())


def _max_relative(left: torch.Tensor, right: torch.Tensor) -> float:
    if left.numel() == 0:
        return 0.0
    difference = (left.detach() - right.detach()).abs()
    denominator = torch.maximum(left.detach().abs(), right.detach().abs()).clamp_min(1e-12)
    return float((difference / denominator).max().cpu())


def _observations_sha256(observations: dict[str, np.ndarray[Any, Any]]) -> str:
    digest = hashlib.sha256()
    for key in sorted(observations):
        value = np.ascontiguousarray(observations[key])
        digest.update(key.encode("utf-8"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def _policy_sha256(policy: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for key, tensor in sorted(policy.state_dict().items()):
        value = np.ascontiguousarray(tensor.detach().cpu().numpy())
        digest.update(key.encode("utf-8"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def _capture_policy(
    policy: Any,
    observation_tensor: dict[str, torch.Tensor],
    feature_forward: Callable[[dict[str, torch.Tensor]], torch.Tensor],
    sample_actions: torch.Tensor,
) -> dict[str, torch.Tensor]:
    original_extractor = policy.features_extractor
    policy.features_extractor = _EncoderForward(original_extractor, feature_forward)
    try:
        extractor = policy.features_extractor
        features = extractor(observation_tensor)
        policy_latent, value_latent = policy.mlp_extractor(features)
        policy._set_distribution_mask(observation_tensor)
        distribution = policy._get_action_dist_from_latent(policy_latent)
        thesis_logits = distribution.thesis.logits
        thesis_probs = distribution.thesis.probs
        policy._distribution_masks = None
        deterministic, predicted_value, forward_log_prob = policy(
            observation_tensor, deterministic=True
        )
        evaluated = policy.evaluate_actions(observation_tensor, sample_actions)
        return {
            "features": features,
            "thesis_logits": thesis_logits,
            "thesis_probs": thesis_probs,
            "deterministic_action": deterministic,
            "value": predicted_value,
            "forward_log_prob": forward_log_prob,
            "log_prob": evaluated[1],
            "entropy": evaluated[2] if evaluated[2] is not None else torch.empty(0),
        }
    finally:
        policy._distribution_masks = None
        policy.features_extractor = original_extractor


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("this A/B requires CUDA")
    if args.iterations < 20:
        raise ValueError("iterations must be at least 20")
    if args.rollout_steps < 1:
        raise ValueError("rollout_steps must be positive")

    cfg, bundle_path, algo, arch = _prepare_bundle(
        args.bundle_dir,
        variant=None,
        config_path=args.config,
        overrides=[],
    )
    cfg.env.data_source = "bundle"
    cfg.env.n_envs = args.n_envs
    cfg.env.vector_backend = "subproc"
    cfg.env.vector_shards = args.n_envs
    cfg.quality_execution.exact_n_envs = True
    # This is policy inference only. Keep construction-time PPO storage small;
    # do not allocate the 16,384-step training rollout buffer.
    cfg.ppo.n_steps = args.n_envs * 2
    cfg.ppo.batch_size = args.n_envs
    cfg.ppo.n_epochs = 1
    _scale_profile_config(cfg, torch.device("cuda"), arch)
    if int(cfg.env.n_envs) != args.n_envs:
        raise RuntimeError(f"expected {args.n_envs} environments, got {cfg.env.n_envs}")

    spec = EnvSpec.from_cfg(
        cfg,
        algo=algo,
        reward=str(cfg.env.get("reward_mode", "dsr")),
        arch=arch,
        bundle_dir=str(bundle_path),
    )
    torch.set_num_threads(1)
    _setup_rngs(args.seed)
    parent_env = make_bundle_env(spec)
    from gymnasium import spaces

    if not isinstance(parent_env.observation_space, spaces.Dict):
        raise TypeError("market inference benchmark requires Dict observations")
    env_fn = partial(make_bundle_env, spec)
    model = build_agent(
        parent_env,
        cfg,
        arch=arch,
        algo=algo,
        device="cuda",
        env_fn=env_fn,
        seed=args.seed,
    )
    vec_env = model.get_env()
    try:
        vec_env.seed(args.seed)
        observations = vec_env.reset()
        encoder = model.policy.features_extractor
        if not isinstance(encoder, SharedTCNMTFReasoningEncoder):
            raise TypeError(f"unexpected extractor: {type(encoder).__name__}")
        encoder.eval()
        model.policy.eval()

        tolerances = {
            "features": 3e-4,
            "thesis_logits": 1e-5,
            "thesis_probs": 1e-5,
            "deterministic_action": 1e-5,
            "value": 1.5e-4,
            "forward_log_prob": 1e-5,
            "log_prob": 1e-5,
            "entropy": 1e-5,
        }

        initial_observations = {key: value.copy() for key, value in observations.items()}
        observations_sha = _observations_sha256(initial_observations)
        representatives, inverse, market_sha = _market_row_groups(initial_observations, encoder)
        rollout_digest = hashlib.sha256()
        market_reuse_by_step: list[float] = []
        market_unique_by_step: list[int] = []
        account_unique_by_step: list[int] = []
        snapshot_indices = sorted({0, args.rollout_steps // 2, max(0, args.rollout_steps - 1)})
        snapshots: dict[int, dict[str, np.ndarray[Any, Any]]] = {0: initial_observations}
        for step_index in range(args.rollout_steps):
            market_reps, _, _ = _market_row_groups(observations, encoder)
            market_unique = int(len(market_reps))
            market_unique_by_step.append(market_unique)
            market_reuse_by_step.append(float(args.n_envs / market_unique))
            account_unique_by_step.append(int(np.unique(observations["account"], axis=0).shape[0]))
            rollout_digest.update(_observations_sha256(observations).encode("ascii"))
            if step_index in snapshot_indices and step_index > 0:
                snapshots[step_index] = {key: value.copy() for key, value in observations.items()}
            with torch.inference_mode():
                actions, _ = model.predict(observations, deterministic=False)
            observations, _, _, _ = vec_env.step(actions)
        rollout_digest.update(_observations_sha256(observations).encode("ascii"))
        snapshots[args.rollout_steps] = {key: value.copy() for key, value in observations.items()}

        errors: dict[str, float] = {}
        relative_errors: dict[str, float] = {}
        parity_checks: dict[str, bool] = {}
        latency_ms: list[float] = []

        def timed_policy(
            feature_forward: Callable[[dict[str, torch.Tensor]], torch.Tensor],
            observation_tensor: dict[str, torch.Tensor],
        ) -> list[float]:
            original_extractor = model.policy.features_extractor
            model.policy.features_extractor = _EncoderForward(encoder, feature_forward)
            values: list[float] = []
            try:
                with torch.inference_mode():
                    for _ in range(args.warmup):
                        model.policy(observation_tensor, deterministic=True)
                    torch.cuda.synchronize()
                    for _ in range(args.iterations):
                        started = time.perf_counter()
                        model.policy(observation_tensor, deterministic=True)
                        torch.cuda.synchronize()
                        values.append((time.perf_counter() - started) * 1000.0)
            finally:
                model.policy.features_extractor = original_extractor
            return values

        for snapshot_index in sorted(snapshots):
            snapshot = snapshots[snapshot_index]
            snapshot_reps, snapshot_inverse, _ = _market_row_groups(snapshot, encoder)
            if len(snapshot_reps) < 1 or len(snapshot_inverse) != args.n_envs:
                raise RuntimeError("invalid market row grouping")
            observation_tensor = cast(
                dict[str, torch.Tensor], obs_as_tensor(snapshot, model.device)
            )
            representatives_t = torch.as_tensor(snapshot_reps, device=model.device)
            inverse_t = torch.as_tensor(snapshot_inverse, device=model.device)

            def full_forward(obs: dict[str, torch.Tensor]) -> torch.Tensor:
                return encoder.__class__.forward(encoder, obs)

            def grouped_forward(obs: dict[str, torch.Tensor]) -> torch.Tensor:
                return encoder.forward_with_market_groups(obs, representatives_t, inverse_t)

            with torch.inference_mode():
                sample_actions = model.policy(observation_tensor, deterministic=True)[0]
                expected = _capture_policy(
                    model.policy, observation_tensor, full_forward, sample_actions
                )
                actual = _capture_policy(
                    model.policy, observation_tensor, grouped_forward, sample_actions
                )
            for key in expected:
                error = _max_abs(expected[key], actual[key])
                errors[key] = max(errors.get(key, 0.0), error)
                relative_errors[key] = max(
                    relative_errors.get(key, 0.0),
                    _max_relative(expected[key], actual[key]),
                )
                parity_checks[key] = parity_checks.get(key, True) and torch.allclose(
                    expected[key],
                    actual[key],
                    rtol=1e-5,
                    atol=tolerances[key],
                )
            measured_forward = full_forward if args.mode == "full" else grouped_forward
            latency_ms.extend(timed_policy(measured_forward, observation_tensor))

        relative_tolerance = 1e-5
        parity = all(passed for passed in parity_checks.values())
        market_reuse_summary = {
            "sampled_vector_steps": len(market_reuse_by_step),
            "market_unique_rows_p50": float(np.percentile(market_unique_by_step, 50)),
            "market_unique_rows_p95": float(np.percentile(market_unique_by_step, 95)),
            "market_reuse_factor_p50": float(np.percentile(market_reuse_by_step, 50)),
            "market_reuse_factor_p95": float(np.percentile(market_reuse_by_step, 95)),
            "account_unique_rows_p50": float(np.percentile(account_unique_by_step, 50)),
            "account_unique_rows_p95": float(np.percentile(account_unique_by_step, 95)),
        }
        report = {
            "mode": args.mode,
            "job_id": args.job_id,
            "host": socket.gethostname(),
            "seed": args.seed,
            "n_envs": args.n_envs,
            "rollout_steps": args.rollout_steps,
            "iterations": args.iterations,
            "warmup": args.warmup,
            "bundle_manifest_sha256": hashlib.sha256(
                (bundle_path / "manifest.json").read_bytes()
            ).hexdigest(),
            "config_path": str(args.config),
            "resolved_config_sha256": hashlib.sha256(
                OmegaConf.to_yaml(cfg, resolve=True).encode("utf-8")
            ).hexdigest(),
            "policy_state_sha256": _policy_sha256(model.policy),
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "observations_sha256": observations_sha,
            "market_sha256": market_sha,
            "market_unique_rows": int(len(representatives)),
            "market_reuse_factor": float(args.n_envs / len(representatives)),
            "account_rows": int(len(initial_observations["account"])),
            "account_unique_rows": int(np.unique(initial_observations["account"], axis=0).shape[0]),
            "rollout_observations_sha256": rollout_digest.hexdigest(),
            "market_reuse_summary": market_reuse_summary,
            "snapshot_market_reuse": {
                str(index): float(args.n_envs / len(_market_row_groups(batch, encoder)[0]))
                for index, batch in snapshots.items()
            },
            "parity_passed": parity,
            "max_abs_errors": errors,
            "max_relative_errors": relative_errors,
            "parity_relative_tolerance": relative_tolerance,
            "parity_tolerances": tolerances,
            "latency_ms": {
                "p50": float(np.percentile(latency_ms, 50)),
                "p95": float(np.percentile(latency_ms, 95)),
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        if not parity:
            raise RuntimeError(f"policy parity failed: {errors}")
        return report
    finally:
        vec_env.close()
        parent_env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("full", "grouped"), required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-envs", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--rollout-steps", type=int, default=128)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
