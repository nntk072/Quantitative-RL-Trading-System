# Multi-timeframe trading context and chart controls

This note defines the added context features and how to inspect them on trade
charts. It is a reproducible engineering definition, not a claim that these
patterns predict returns.

## Timeframe coverage

The feature ladder is M1, M3, M5, M10, M15, M30, H1, H4, and D1. Technical
indicators are computed on each timeframe's own bars and then aligned to the
M1 decision timeline only when the source bar is complete. The dataset carries
EMA 9/21/50/200, RSI, and MACD per timeframe. VWAP remains implemented as an
optional feature, but the new normal-data benchmark disables it because this
input cache does not provide the intended VWAP activity data.

FVG, IFVG, Order Block, swing, and PO3 state can be enabled across the same
ladder. The policy receives four separate, directional, multi-hot entry
contexts: PO3/sweep, Order Block reaction, Fair Value Gap retest, and the
user-named "standard deviation" idea. The last is a Fibonacci-like pullback
from the latest confirmed swing leg: a long context is active inside the
0.5-0.786 retracement after an up leg; a short context mirrors it after a down
leg. It is not a statistical standard-deviation calculation. Every timeframe
uses its own confirmed pivots, and an HTF context appears only after its source
candle closes. Each timeframe exposes one latest confirmed, non-invalidated
swing leg, not a second mirrored ladder. The signed
`standard_deviation_leg_direction` feature is `+1` for an up leg, `-1` for a
down leg, and `0` when that leg is unavailable or invalidated. For an up/long
leg, level 1 anchors at the swing low and level 0 at the swing high; for a
down/short leg, level 1 anchors at the swing high and level 0 at the swing low.
This keeps the 0.5-0.786 band as pullback depth in either direction. The ideas
may overlap; none requires another idea or acts as a hard entry gate. The
experiment records which contexts and timeframes were active at the entry
signal, but this attribution does not prove which input caused the policy's
action.

The H1 example selected for visual review is available as the [swing/Fib-SD
chart](figures/entry_ideas/h1_swing_fib_sd_20261027.png) and [Order Block
chart](figures/entry_ideas/h1_order_block_20261027.png). Its anchors and data
identity are recorded in the [preview metadata](figures/entry_ideas/h1_preview_metadata_20261027.json).
The directional-feature cache validation is recorded in
[`directional_swing_cache_validation_20261027_v30.json`](directional_swing_cache_validation_20261027_v30.json).

Raw price boundaries remain metadata for plotting and order geometry; policy
inputs use directional flags and the retracement fraction. Per-trade overlays
are controlled independently by entry idea in `evaluation.trade_idea_plots` in
`config/base/default.yaml`. Each block has an `enabled` switch and its own
timeframe list. PO3 also has separate manipulation, distribution, FVG, and IFVG
switches; Order Block has a zone switch; FVG retest has separate FVG and IFVG
switches; and the retracement block selects its level ladder and chart-range
tolerance. If several ideas were active at one entry, their enabled overlays
are combined on that trade's chart. The FVG-retest idea records active FVG and
IFVG zones at its source timeframe so either can be shown or hidden separately.

The PO3 chart uses its saved source timeframes for manipulation/distribution
and the exact FVG-to-IFVG zone metadata attached to the entry. It does not
search the chart for unrelated gaps. The swing-retracement ladder is drawn only
when that idea was recorded at entry, using the saved source timeframes and the
configured values `1, 0.786, 0.707, 0.5, 0, -0.5, -1, -1.5, -2, -2.5, -3,
-4, -8`; levels outside the configured chart-range tolerance are omitted.
When two swing levels overlap within the chart's price tolerance, the lower
timeframe label is retained to reduce duplicate context. Plot settings affect
report/replot overlays only; they do not change training observations or policy
behavior.

## Operational Order Block definition

For each timeframe, the implementation uses a confirmed local swing as the
structure reference. A bullish block is the last bearish candle among the
configured search window before a later candle closes above the confirmed
swing high with a body at least the configured ATR multiple. A bearish block is
the mirrored case. The originating candle's full low/high interval defines the
zone. The zone becomes available only after the displacement candle closes;
retest is recorded only on a later candle. A close beyond the distal boundary
invalidates the block, and a configured age limit expires it. Higher-timeframe
features become visible on M1 only after that higher-timeframe candle is
complete.

This is a compact causal operationalization inspired by ICT's public Order
Block descriptions, rather than an attempt to encode every discretionary
interpretation. Order Block detection and reaction context are independent of
PO3: a trade does not need a PO3 manipulation/distribution phase, sweep, or
IFVG confirmation to use an Order Block. PO3/IFVG columns remain separate,
optional context. See [ICT Episode 3](https://www.youtube.com/watch?v=nQfHZ2DEJ8c)
and [ICT Episode 22](https://www.youtube.com/watch?v=QKc_i90chVg). Those sources
describe the trading concept; they do not validate this detector or establish
an edge.

## Order use and chart review

For a position opened by a sweep, the stop reference is the actual swept wick
with the configured buffer. The target remains any valid opposite-side target
selected by the policy; it is not forced to the swept wick or to an Order
Block. An active opposing Order Block boundary can be an additional stop or
target candidate when it is geometrically valid. Non-sweep stops retain
structure-based choices.

The EMA-21 exit is a runner mode. Structural targets chosen at entry execute
their partials first; only after those selected levels are exhausted can the
reserved fraction exit on EMA-21. A zero runner fraction preserves the prior
immediate EMA behavior. This benchmark uses a 25% runner reserve in both arms.

Regenerate charts with `evaluation.plotting.replot_orders`; it reads each
run's saved config and per-trade idea/timeframe attribution. The CLI timeframe
options remain available for legacy overlays. Plotly legends also allow
individual rendered traces to be hidden or restored.

## Benchmark identity and limits

`regime_tcn_context_r2_seed50_train2025_2m_normal_mtf_context_20261026.yaml`
defines the matched 2M control/regime pair. Both arms share the same features,
execution, risk settings, training budget, seed, and split; the existing
control/regime architecture distinction remains. The 2026 segment is already
exposed and is report-only. Results are exploratory, single-seed screening and
cannot establish out-of-sample superiority.

The entry-idea follow-up adds the four multi-timeframe idea contexts and signed
direction action to both arms. The first campaign identity failed before PPO
step 0 while resolving duplicate-labelled input columns; that fingerprint is
preserved as a pre-training failure. A positional column-selection fix was
added and its focused regression passed.

The next identity,
`regime_tcn_context_r2_seed50_train2025_2m_normal_entry_ideas_20261026_fix1`,
fingerprint `f4af92310d9f717676077a48ae18dd9972716e313a7efdc47363902e632eb946`,
also failed before PPO step 0. Both arms reached feature serialization and
PyArrow rejected the frame because it contained duplicate columns. The raw bar
caches had unique columns; the feature assembler had appended an aligned frame
twice in the Order Block and swing-retracement paths. Those paths now replace
the frame with the aligned result, the builder rejects duplicate output labels
before serialization, and a regression test writes and rereads the Parquet
cache. The feature-cache version is `v28-entry-idea-unique-columns`.

Do not launch training until the full-tree Ruff/Mypy gate and relevant pytest
set pass, then build and validate the feature Parquet cache as a separate
pre-training step. Put that cache path in the next campaign spec as
`data.prebuilt_feature_cache`; training must hash-validate and reuse it. The
next attempt needs a new campaign identity and fingerprint. No PPO training or
benchmark result is available yet.
