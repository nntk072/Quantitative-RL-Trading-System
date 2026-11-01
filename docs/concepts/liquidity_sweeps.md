# Liquidity sweeps

The feature code defines a sweep as a bounded take of a previously confirmed
swing level. It is a descriptive event label, not proof of hidden orders or a
forecast.

For the basic detector, the currently known swing level is shifted by one bar
before comparison. A high-side sweep requires price to take above a fresh
known high by no more than a configured ATR distance; a deeper move is treated
as a breakout rather than a sweep. The mirrored low-side rule applies below a
known swing low. Reclaim is recorded when the close returns through the level.
The output preserves event, level, wick, age, and reclaim fields.

The retained-level detector can represent multiple unswept swing levels rather
than only the most recent one. Downstream features may use a sweep as PO3
context or as a candidate setup, but detection alone does not create an entry.

Implementation: [`features/context/liquidity.py`](../../features/context/liquidity.py),
[feature catalog](../reference/feature_catalog.md), and
[`test_liquidity.py`](../../tests/unit/features/test_liquidity.py).
