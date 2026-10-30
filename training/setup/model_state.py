"""Model initialization and constrained-risk checkpoint resume checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch


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
