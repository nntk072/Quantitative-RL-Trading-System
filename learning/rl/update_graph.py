"""CUDA-graph replay of one PPO minibatch (forward, loss, backward, clip) for the trade-setup policy.

The optimizer step stays eager, so Adam state and step counts are untouched by capture. The
update loop follows SB3's ``PPO.train`` order and logging, without early stopping.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import chain
from typing import Any

import torch
from stable_baselines3.common.utils import explained_variance
from torch.nn import functional as F

from learning.rl.hybrid import distribution_validation_off, masks_prevalidated

_WARMUP_ITERATIONS = 3


class _StepGraph:
    """Static buffers and the captured minibatch step for one minibatch shape."""

    def __init__(
        self, model: Any, sample: Any
    ) -> None:  # pragma: no cover - needs CUDA graph capture
        """Allocate static buffers from one minibatch and capture the step.

        Args:
            model: PPO model whose policy is stepped.
            sample: Minibatch whose shapes the captured step is fixed to.
        """
        self.model = model
        device = model.policy.device
        self.obs = {key: value.clone() for key, value in sample.observations.items()}
        self.actions = sample.actions.clone()
        self.old_log_prob = sample.old_log_prob.clone()
        self.advantages = sample.advantages.clone()
        self.returns = sample.returns.clone()
        self.clip = torch.zeros((), device=device)
        self.stats = torch.zeros(4, device=device)
        self.kl = torch.zeros((), device=device)
        self.loss = torch.zeros((), device=device)
        self.bad = torch.zeros((), dtype=torch.bool, device=device)
        for parameter in model.policy.parameters():
            if parameter.grad is None:
                parameter.grad = torch.zeros_like(parameter)
        side = torch.cuda.Stream()  # type: ignore[no-untyped-call]
        side.wait_stream(torch.cuda.current_stream())
        with distribution_validation_off(), masks_prevalidated():
            with torch.cuda.stream(side):
                for _ in range(_WARMUP_ITERATIONS):
                    self._step()
            torch.cuda.current_stream().wait_stream(side)
            self.graph = torch.cuda.CUDAGraph()
            # Warm-up autograd nodes still point at the side stream; redirect them to the capture stream.
            # Present in the CUDA torch build; absent in the ROCm build used on MI210.
            _set_stale_capture = getattr(
                torch.autograd.graph, "set_override_stale_capture_stream", None
            )
            if _set_stale_capture is not None:
                _set_stale_capture(True)
            try:
                with torch.cuda.graph(self.graph, capture_error_mode="thread_local"):
                    self._step()
            finally:
                if _set_stale_capture is not None:
                    _set_stale_capture(False)
        torch.cuda.synchronize()
        # Warm-up and capture ran the Python side effects once; undo them.
        model.policy.reset_mode_prior_stats()
        self.bad.zero_()

    def _step(self) -> None:  # pragma: no cover - runs only inside CUDA graph capture
        """Forward, loss, backward, and gradient clip into the static buffers."""
        model = self.model
        policy = model.policy
        values, log_prob, entropy = policy.evaluate_actions(self.obs, self.actions)
        values = values.flatten()
        advantages = self.advantages
        if model.normalize_advantage and advantages.shape[0] > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        ratio = torch.exp(log_prob - self.old_log_prob)
        clip = self.clip
        policy_loss_1 = advantages * ratio
        policy_loss_2 = advantages * torch.clamp(ratio, 1 - clip, 1 + clip)
        policy_loss = -torch.min(policy_loss_1, policy_loss_2).mean()
        clip_fraction = torch.mean((torch.abs(ratio - 1) > clip).float())
        value_loss = F.mse_loss(self.returns, values)
        entropy_loss = -torch.mean(-log_prob) if entropy is None else -torch.mean(entropy)
        loss = policy_loss + model.ent_coef * entropy_loss + model.vf_coef * value_loss
        with torch.no_grad():
            log_ratio = log_prob - self.old_log_prob
            approx_kl = torch.mean((torch.exp(log_ratio) - 1) - log_ratio)
        policy.optimizer.zero_grad(set_to_none=False)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), model.max_grad_norm)
        self.stats.copy_(
            torch.stack(
                (
                    policy_loss.detach(),
                    value_loss.detach(),
                    entropy_loss.detach(),
                    clip_fraction.detach(),
                )
            )
        )
        self.kl.copy_(approx_kl.detach())
        self.loss.copy_(loss.detach())
        self.bad.logical_or_(~torch.isfinite(loss.detach()))

    def run(self, sample: Any, stats_total: torch.Tensor, kl_epoch: torch.Tensor) -> None:
        """Copy one minibatch in, replay the captured step, then step the optimizer eagerly.

        Args:
            sample: Minibatch from the rollout buffer.
            stats_total: Device accumulator for the four logged minibatch statistics.
            kl_epoch: Device accumulator for approximate KL over the current epoch.
        """
        for key, value in sample.observations.items():
            self.obs[key].copy_(value)
        self.actions.copy_(sample.actions)
        self.old_log_prob.copy_(sample.old_log_prob)
        self.advantages.copy_(sample.advantages)
        self.returns.copy_(sample.returns)
        self.graph.replay()
        self.model.policy.optimizer.step()
        stats_total.add_(self.stats)
        kl_epoch.add_(self.kl)


def _graph_supported(model: Any) -> bool:
    """Return whether the captured update applies to this model.

    Args:
        model: PPO model about to train.

    Returns:
        True for the trade-setup policy on CUDA with no value clipping or early stopping.
    """
    policy = model.policy
    return (
        getattr(model, "target_kl", None) is None
        and getattr(model, "clip_range_vf", None) is None
        and hasattr(policy, "validate_rollout_masks")
        and policy.device.type == "cuda"
    )


def _graphed_train(model: Any, original_train: Callable[[], None], state: dict[str, Any]) -> None:
    """Train one PPO update with the minibatch step captured in a CUDA graph.

    Args:
        model: PPO model whose rollout buffer is full.
        original_train: SB3 train method, used when the update is not supported.
        state: Per-model cache holding the captured step.
    """
    buffer = model.rollout_buffer
    batch_size = int(model.batch_size)
    sample_count = int(buffer.buffer_size * buffer.n_envs)
    if not _graph_supported(model) or sample_count % batch_size != 0:
        original_train()
        return
    policy = model.policy
    policy.set_training_mode(True)
    model._update_learning_rate(policy.optimizer)
    clip_range = model.clip_range(model._current_progress_remaining)

    # Epoch 0 draws its permutation on the first next(); the first sample also stages the rollout.
    minibatches = buffer.get(batch_size)
    first = next(minibatches)
    mask_key = policy.trade_setup_mask_key
    policy.validate_rollout_masks({mask_key: buffer._device_rollout[f"observation:{mask_key}"]})
    if "graph" not in state:
        state["graph"] = _StepGraph(model, first)
    graph: _StepGraph = state["graph"]
    graph.clip.fill_(float(clip_range))

    stats_total = torch.zeros(4, device=policy.device)
    kl_last_epoch = torch.zeros((), device=policy.device)
    batches_per_epoch = sample_count // batch_size
    for epoch in range(model.n_epochs):
        kl_last_epoch.zero_()
        epoch_samples = chain([first], minibatches) if epoch == 0 else buffer.get(batch_size)
        for sample in epoch_samples:
            graph.run(sample, stats_total, kl_last_epoch)
        model._n_updates += 1

    if bool(graph.bad.item()):
        raise ValueError("non-finite PPO loss during graphed update")
    means = (stats_total / float(model.n_epochs * batches_per_epoch)).tolist()
    logger = model.logger
    logger.record("train/entropy_loss", means[2])
    logger.record("train/policy_gradient_loss", means[0])
    logger.record("train/value_loss", means[1])
    logger.record("train/approx_kl", float(kl_last_epoch.item()) / batches_per_epoch)
    logger.record("train/clip_fraction", means[3])
    logger.record("train/loss", float(graph.loss.item()))
    explained_var = explained_variance(buffer.values.flatten(), buffer.returns.flatten())
    logger.record("train/explained_variance", explained_var)
    if hasattr(policy, "log_std"):
        logger.record("train/std", float(torch.exp(policy.log_std).mean().item()))
    logger.record("train/n_updates", model._n_updates, exclude="tensorboard")
    logger.record("train/clip_range", clip_range)


def install_graphed_update(model: Any) -> None:
    """Route ``model.train`` through the captured minibatch step when the model supports it.

    Args:
        model: PPO model to patch in place.
    """
    original_train = model.train
    state: dict[str, Any] = {}

    def _train() -> None:
        """Run the captured update, or the original SB3 update when unsupported."""
        _graphed_train(model, original_train, state)

    model.train = _train


__all__ = ["install_graphed_update"]
