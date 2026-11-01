# Order-block feature definition

The code uses a reproducible operational definition: a bullish block is the
last bearish candle in the configured lookback before an ATR-sized bullish
displacement closes above a previously confirmed swing high. The bearish
definition mirrors the rule. The zone becomes visible at the displacement
bar's close; later bars may mark retest, age, and ATR-normalized distance.
Close-through of the distal edge or maximum-age expiry deactivates the zone.

This feature is independent of PO3: its detector does not require a PO3 phase,
sweep, or IFVG confirmation. The zone is a contextual measurement, not proof
that a price level will hold or reverse the market.

See [`features/context/order_blocks.py`](../../features/context/order_blocks.py),
[feature catalog](../reference/feature_catalog.md), and
[`test_order_blocks.py`](../../tests/unit/features/test_order_blocks.py).
