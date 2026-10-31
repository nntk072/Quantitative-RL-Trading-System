# Market structure

Market-structure features summarize causal price relationships such as local
swings, session levels, fair-value gaps, inverted gaps, order blocks, and
deviation levels. They are explanatory inputs and candidate references; they
do not guarantee that price will react as expected.

## Causality and validity

A level is usable only after its required source candles have completed. A
feature must not use a future candle to confirm a swing or gap and then expose
that information at an earlier decision point. Higher-timeframe values are
aligned from completed bars. When a configured invalidation rule is met, the
level should no longer be offered as a live candidate.

Session extrema and swing levels have different meanings. Session highs/lows
refer to a defined prior or current session boundary; a local swing is a
confirmed extremum in a timeframe-specific sequence. Reports should preserve
the source timeframe and event time so a reader can tell which structure was
used.

## Feature families

| Family | What it represents | Important qualification |
|---|---|---|
| Swing | Confirmed local high or low | Confirmation delay is part of causal visibility. |
| FVG / IFVG | Price imbalance and its directionally inverted form | Creation, retest, and invalidation rules depend on the configured feature definition. |
| Order block | A candle region associated with a later directional move | Must be sourced from the configured timeframe and remain valid under its invalidation rule. |
| Standard deviation | Levels measured from a selected swing range | The chosen swing, direction, timeframe, and level must be explicit. |
| Session liquidity | Session high/low reference levels | Must be anchored to the session definition, not arbitrary chart lines. |

## Reading plots and datasets

The data matrix may contain encoded values and validity flags; chart renderers
may display only selected structures for readability. A plotted line is not
evidence that the policy observed or selected it. Per-trade records should
identify the actual setup and references separately from optional chart
context.

## Limitations

These labels are algorithmic definitions used by this repository. They should
not be treated as universal market terminology or as validated predictive
signals without empirical evidence.
