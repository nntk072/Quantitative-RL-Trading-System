"""Model initialization, resume validation, and provenance helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import torch

log = logging.getLogger(__name__)


def _initialize_value_head(model: Any, *, resumed: bool) -> None:
    """Zero the critic head only for a new run, never for a loaded checkpoint."""
    if resumed:
        return
    value_net = getattr(model.policy, "value_net", None)
    if value_net is None:
        return
    with torch.no_grad():
        for param in value_net.parameters():
            param.zero_()


def _validate_q5_resume_state(cfg: Any, *, resume_checkpoint: str | Path | None) -> None:
    """Reject Q5 resume until PPO checkpoints also restore full-split env state.

    PPO checkpoints preserve the learned multiplier, but the training CLI builds
    fresh environments when resuming. That would combine a partial episode's
    saved risk cost with a new episode starting at the first training bar.
    """
    constrained = cfg.get("constrained_rl", {})
    if resume_checkpoint and bool(constrained.get("enabled", False)):
        raise ValueError(
            "Q5 constrained_rl cannot resume from a PPO-only checkpoint: the "
            "full-split training environment/account state is not restored"
        )


def _log_effective_ppo(model: Any, cfg: Any, *, algo: str = "ppo") -> None:
    """Log the effective optimizer settings without labeling SAC as PPO."""
    if algo == "sac":
        n_envs = int(model.n_envs)
        requested_n_envs = int(cfg.env.get("n_envs", 1))
        if n_envs != requested_n_envs:
            raise RuntimeError(
                f"effective SAC n_envs={n_envs} does not match resolved config "
                f"n_envs={requested_n_envs}"
            )
        log.info(
            "SAC effective: logical_n_envs=%d learning_rate=%s batch_size=%s "
            "buffer_size=%s learning_starts=%s train_freq=%s gradient_steps=%s "
            "gamma=%s tau=%s ent_coef=%s reward_mode=%s",
            n_envs,
            cfg.sac.learning_rate,
            cfg.sac.batch_size,
            cfg.sac.buffer_size,
            cfg.sac.learning_starts,
            cfg.sac.train_freq,
            cfg.sac.gradient_steps,
            cfg.sac.gamma,
            cfg.sac.tau,
            cfg.sac.ent_coef,
            cfg.env.get("reward_mode", "dsr"),
        )
        return

    n_steps = int(model.n_steps)
    n_envs = int(model.n_envs)
    aggregate_rollout_steps = n_steps * n_envs
    batch_size = int(cfg.ppo.batch_size)
    minibatches_per_epoch = (aggregate_rollout_steps + batch_size - 1) // batch_size
    requested_n_envs = int(cfg.env.get("n_envs", 1))
    if n_envs != requested_n_envs:
        raise RuntimeError(
            f"effective PPO n_envs={n_envs} does not match resolved config "
            f"n_envs={requested_n_envs}"
        )
    strategy_name = (
        str(cfg.strategy.get("name", "strategy"))
        if bool(cfg.env.get("strategy_actions", False))
        else "baseline"
    )
    log.info(
        "PPO effective: logical_n_envs=%d sb3_n_steps_per_env=%d "
        "aggregate_rollout_steps=%d batch_size=%d n_epochs=%s minibatches_per_epoch=%d "
        "updates_per_rollout=%d lr=%s "
        "gamma=%s clip=%s ent_coef=%s log_std=[%s,%s] reward_mode=%s strategy=%s",
        n_envs,
        n_steps,
        aggregate_rollout_steps,
        batch_size,
        cfg.ppo.n_epochs,
        minibatches_per_epoch,
        minibatches_per_epoch * int(cfg.ppo.n_epochs),
        cfg.ppo.learning_rate,
        cfg.ppo.gamma,
        cfg.ppo.clip_range,
        model.ent_coef,
        cfg.ppo.get("log_std_min", -0.7),
        cfg.ppo.get("log_std_max", 0.0),
        cfg.env.get("reward_mode", "dsr"),
        strategy_name,
    )


def _training_architecture_provenance(
    model: Any, cfg: Any, arch: str, *, algo: str = "ppo"
) -> dict[str, Any]:
    """Describe the actual encoder, policy heads, and vectorization used."""
    policy = model.policy
    extractor = getattr(policy, "features_extractor", None)
    if extractor is None:
        actor = getattr(policy, "actor", None)
        extractor = getattr(actor, "features_extractor", None)
    if extractor is None:
        raise RuntimeError(f"{algo} policy does not expose its encoder for provenance")
    env = model.get_env()
    remotes = getattr(env, "remotes", None)
    physical_workers = len(remotes) if remotes is not None else 1
    head_cfg = cfg.agent.get("head_arch", {})
    encoder_spec = {
        "arch": arch,
        "encoder_class": type(extractor).__name__,
        "encoder_parameter_count": sum(parameter.numel() for parameter in extractor.parameters()),
        "encoder_channels": getattr(extractor, "channels", None),
        "encoder_dilations": list(extractor.dilations) if hasattr(extractor, "dilations") else None,
        "encoder_kernel_size": getattr(extractor, "kernel_size", None),
        "encoder_latent_dim": int(getattr(extractor, "latent_dim", 128)),
        "encoder_parameters": {
            key: getattr(extractor, key)
            for key in ("hidden_size", "num_layers", "d_model", "nhead", "dim_feedforward")
            if hasattr(extractor, key)
        },
    }
    encoder_provenance = getattr(extractor, "encoder_provenance", None)
    if isinstance(encoder_provenance, dict):
        encoder_spec["encoder_specific"] = encoder_provenance
    result = {
        "algorithm": algo,
        **encoder_spec,
        "quality_variant_id": str(cfg.get("quality_variant_id", "")) or None,
        "policy_head_architecture": [int(width) for width in head_cfg.get(arch, [256, 128])],
        "policy_parameter_count": sum(parameter.numel() for parameter in policy.parameters()),
        "configured_vector_backend": str(cfg.env.get("vector_backend", "subproc")),
        "vector_backend": type(env).__name__,
        "logical_n_envs": int(model.n_envs),
        "physical_worker_count": int(physical_workers),
    }
    if algo == "ppo":
        n_steps = int(model.n_steps)
        batch_size = int(cfg.ppo.batch_size)
        minibatches = (int(model.n_envs) * n_steps + batch_size - 1) // batch_size
        result.update(
            {
                "actor_architecture": str(cfg.ppo.get("actor_arch", "shared")),
                "semantic_head_width": int(cfg.ppo.get("semantic_head_width", 64)),
                "sb3_n_steps_per_env": n_steps,
                "aggregate_rollout_steps": int(model.n_envs * n_steps),
                "batch_size": batch_size,
                "n_epochs": int(cfg.ppo.n_epochs),
                "minibatches_per_epoch": minibatches,
                "updates_per_rollout": int(minibatches * int(cfg.ppo.n_epochs)),
            }
        )
    elif algo == "sac":
        result["sac"] = {
            key: cfg.sac.get(key)
            for key in (
                "learning_rate",
                "buffer_size",
                "batch_size",
                "tau",
                "gamma",
                "train_freq",
                "gradient_steps",
                "learning_starts",
                "ent_coef",
            )
        }
    return result
