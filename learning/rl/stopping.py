"""RL training stop criteria derived from completed environment episodes."""

from __future__ import annotations

from typing import Any


def decide_early_abort(
    episodes: list[dict[str, Any]],
    *,
    num_timesteps: int,
    min_timesteps: int,
    window: int,
    nonfinite: bool,
    stop_on_nonfinite: bool = True,
    stop_on_no_trades: bool = False,
    stop_on_equity_gate: bool = True,
) -> str | None:
    """Return a stop reason, or ``None`` to keep training.

    Non-finite metrics stop immediately. Optional no-trade stops and hard-risk
    stops wait until ``min_timesteps`` and require every episode in the last
    ``window`` to fail. A peak-drawdown policy miss never stops optimization.

    Args:
        episodes: Items supplied for the episodes, in input order.
        num_timesteps: Numeric value used for the num timesteps.
        min_timesteps: Numeric value used for the min timesteps.
        window: Numeric value used for the window.
        nonfinite: Whether to enable or require the nonfinite.
        stop_on_nonfinite: Whether to enable or require the stop on nonfinite.
        stop_on_no_trades: Whether to enable or require the stop on no trades.
        stop_on_equity_gate: Whether to enable or require the stop on equity gate.

    Returns:
        Result of return a stop reason, or ``None`` to keep training.
    """
    if stop_on_nonfinite and nonfinite:
        return "nonfinite"
    if int(num_timesteps) < int(min_timesteps) or int(window) < 1:
        return None
    if len(episodes) < int(window):
        return None
    recent = episodes[-int(window) :]
    if stop_on_no_trades and all(int(ep.get("n_trades", 0)) == 0 for ep in recent):
        return "no_trades"
    if stop_on_equity_gate and all(_episode_has_hard_breach(ep) for ep in recent):
        return "equity_gate:max_loss_stopped_trading"
    return None


def _episode_has_hard_breach(ep: dict[str, Any]) -> bool:
    """Detect hard account breaches without using peak-DD fit as a stop.

    Args:
        ep: Key-value data used for the ep.

    Returns:
        Whether episode has hard breach meets the requested condition.
    """
    return bool(ep.get("breach_reason") or ep.get("breached"))


__all__ = ["decide_early_abort"]
