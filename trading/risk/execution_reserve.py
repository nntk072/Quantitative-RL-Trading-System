"""Execution-cost reserve used by risk-aware position sizing."""

from __future__ import annotations


def modeled_execution_reserve_usd(
    *, lots: float, slippage_points: float, commission_per_lot: float, contract_size: float
) -> float:
    """Estimate execution costs reserved before sizing a trade.

    Args:
        lots: Proposed position size in lots.
        slippage_points: Adverse slippage estimate in points per fill.
        commission_per_lot: Commission charged per lot per side.
        contract_size: Units represented by one lot.

    Returns:
        Dollar reserve for adverse stop slippage and round-trip commission.
    """
    lots_f = max(0.0, float(lots))
    adverse_stop_slippage = float(slippage_points) * lots_f * float(contract_size)
    round_trip_commission = 2.0 * float(commission_per_lot) * lots_f
    return max(0.0, adverse_stop_slippage + round_trip_commission)
