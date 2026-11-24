"""Legacy policy marker and compatibility semantics."""

from __future__ import annotations

LEGACY_POLICY_MODE = "legacy"


def uses_fixed_risk_budget(risk_mode: str, repeated_payout: bool) -> bool:
    """Return whether legacy settings require fixed risk sizing.

    Args:
        risk_mode: Configured risk-sizing mode.
        repeated_payout: Whether repeated payouts are enabled.

    Returns:
        True when the fixed-risk budget path is required.
    """
    return str(risk_mode) == "fixed" and not bool(repeated_payout)
