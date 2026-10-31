# Multi-timeframe market context and entry ideas

This note explains the structural context represented by the system. It is a
definition of inputs and plotting behavior, not evidence that any pattern has
predictive value.

## Timeframe context

The configured dataset contains M1, M3, M5, M10, M15, M30, H1, H4, and D1
observations. Technical indicators are calculated from the bars for their own
timeframe. A higher-timeframe value becomes available on the decision timeline
only after its source candle has closed.

The feature set can carry EMA 9/21/50/200, RSI, MACD, session context, swings,
FVG, IFVG, Order Block, and PO3 state. A feature can describe context without
being an entry rule; the model decides how eligible information contributes to
its action.

## Entry-idea contexts

Four distinct context families can be present at once:

1. **PO3 and sweep:** session manipulation/distribution context and the
   relevant liquidity sweep. The plot should show only the PO3 and gap zones
   associated with that trade.
2. **Order Block reaction:** price revisits an active block formed by a
   displacement from a confirmed structural level. This idea does not require
   PO3 or an FVG/IFVG signal.
3. **FVG/IFVG reaction:** the model distinguishes a fair-value gap from an
   inverse fair-value gap. For an unretested reaction, the confirmation body
   must close through the zone with the configured area-relative buffer. A
   retest is a separate form of evidence, not the same signal.
4. **Swing retracement:** a Fibonacci-like retracement of a confirmed swing
   leg. “Standard deviation” is the historical project label for this idea;
   it is not a statistical standard deviation. Level 1 and level 0 depend on
   the selected swing direction. The retracement uses that swing’s own
   timeframe.

These contexts can correlate. A policy configured for thesis-conditioned
decisions selects one primary idea, setup timeframe, and direction for an
entry. Other timeframes may provide corroborating context. A recorded active
context does not by itself prove that it caused the trade.

## Order Block definition

The operational detector uses confirmed local structure. A bullish block is
the last bearish candle in the configured search window before a later candle
closes above a confirmed swing high with the configured minimum displacement.
A bearish block is defined in the opposite direction. The source candle’s
high-low interval is the zone. The block becomes available after the
displacement candle closes, can be revisited only on a later candle, and is
invalidated by a close beyond its distal boundary or by its configured age
limit.

This is a causal, mechanical definition of a discretionary chart concept; it
does not encode every trader’s interpretation. Public descriptions of Order
Blocks do not validate this detector or establish a trading edge.

## Stops, targets, and charts

- When an entry uses a structural setup timeframe, structural stop candidates
  must come from that timeframe or a higher timeframe. The model may select
  which eligible reference to use; the code must not silently force the
  highest available timeframe.
- A valid target may come from any timeframe and from any configured
  opposite-side target family.
- A sweep-based stop is anchored beyond the swept wick with its configured
  buffer. A sweep alone is not sufficient confirmation for an entry.
- Structural partial targets execute before an EMA runner. EMA management is
  available only for the reserved runner after at least one partial target has
  filled.
- Charts show the entry idea and selected references. Indicator and structure
  overlays are independently switchable; plot visibility does not change
  training behavior.

## Interpretation limits

The system’s detector is one explicit operational definition. It can be
implemented consistently and still fail to predict returns. Causal
availability, correct invalidation, valid fills, and trade outcomes must be
checked separately. Plots support inspection; they are not proof of an edge.

For how contexts enter policy inputs, see [Features](../modules/features.md).
For how a primary idea becomes an action, see [Decisioning](../modules/decisioning.md).
