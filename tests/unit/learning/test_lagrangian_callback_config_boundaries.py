"""Configuration rejection contracts for constrained PPO callbacks."""

from __future__ import annotations

from typing import Any, cast

import pytest

from learning.rl.callbacks import LagrangianRiskCallback


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"episode_cost_budget": -0.1}, "episode_cost_budget must be nonnegative"),
        ({"dual_learning_rate": 0.0}, "dual_learning_rate must be positive"),
        ({"gamma": 0.0}, "gamma and cost_discount_gamma must be in"),
        ({"cost_discount_gamma": 1.01}, "gamma and cost_discount_gamma must be in"),
        ({"daily_loss_limit_usd": -1.0}, "loss limits must be nonnegative"),
        ({"max_loss_limit_usd": 0.0}, "loss limits must be nonnegative"),
        ({"trailing_dd_limit_usd": -1.0}, "trailing limit must be nonnegative"),
        ({"lambda_initial": -0.1}, "multiplier bounds are invalid"),
        ({"lambda_max": 0.0}, "multiplier bounds are invalid"),
        ({"lambda_initial": 2.0, "lambda_max": 1.0}, "multiplier bounds are invalid"),
        ({"episode_cost_budget": float("nan")}, "settings must all be finite"),
    ],
)
def test_lagrangian_callback_rejects_invalid_risk_configuration(
    override: dict[str, float], message: str
) -> None:
    configuration = {
        "episode_cost_budget": 1.0,
        "dual_learning_rate": 0.1,
        "lambda_initial": 0.0,
        "lambda_max": 10.0,
        "gamma": 0.99,
        "daily_loss_limit_usd": 5_000.0,
        "max_loss_limit_usd": 10_000.0,
        "trailing_dd_limit_usd": 0.0,
    }
    configuration.update(override)

    with pytest.raises(ValueError, match=message):
        cast(Any, LagrangianRiskCallback)(**configuration)


def test_lagrangian_callback_accepts_zero_daily_and_trailing_budgets() -> None:
    callback = LagrangianRiskCallback(
        daily_loss_limit_usd=0.0,
        trailing_dd_limit_usd=0.0,
        max_loss_limit_usd=1.0,
    )

    assert callback.daily_loss_limit_usd == 0.0
    assert callback.trailing_dd_limit_usd == 0.0
