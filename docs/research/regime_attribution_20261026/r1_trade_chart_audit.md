# R1 trade-chart audit

**Date:** 2026-10-26
**Scope:** R1 saved trade ledgers and their regenerated training and
previously exposed 2026 report-only charts. This audit does not alter the R1
checkpoint, ledger, metrics, or historical result.

## Confirmed defects

1. **Order fills are obscured by unrelated imbalance zones.**
   `evaluation/plotting/orders.py` unconditionally overlays every FVG zone in
   the chart window. The colored rectangles are not all the position's SL/TP
   area. This makes the actual order band hard to distinguish and is the
   source of the apparent misplaced boxes in the examples. The order-level
   band itself is calculated from the logged open fill price and structural
   stop/target prices; for tick executions, the open row's `price` and
   `time` are the actual tick fill. The display must label that explicitly.

2. **Position PnL is undercounted on charts with partial exits.**
   `evaluation/metrics/trade_pairs.py` pairs an open only with its final close
   row and ignores `tp_partial_close` fills. For report-only testing trade 29,
   the first partial realized +$307.60 and the remaining stop close realized
   +$14.54; the saved open/final rows report total position net PnL of
   +$322.14. The chart currently titles the position +$14.54 and calculates
   PnL as if the entire initial size exited at the final fill. Its PnL and
   reconciliation line are therefore wrong for this position.

3. **Stop changes after partials are not drawn or logged.**
   Testing trade 29 entered short at the actual tick fill 25,824.0293, with an
   initial stop at 25,850.83 (26.80 index points; requested risk $900,
   modeled risk $758.49) and targets at 25,781.75 and 25,769.63. It partially
   closed 20.44 lots at 25,808.9805, then the remaining 7.8613 lots exited at
   25,822.1797. The configured post-partial break-even buffer is 2 points;
   the stop moved to 25,822.0293 before the final tick fill, but that automatic
   update was not emitted as an `sl_update` ledger event. The existing chart
   shows only the initial stop, so it hides the active stop path. This example
   is not an 80-point initial stop; its stop was 26.80 points. The visual
   confusion and missing stop-update record still need correction.

4. **EMA-21 is currently a whole-position exit choice.**
   Training trade 19 selected `exit_mode=ema_21`, had no executed target legs,
   and closed at its structural stop. The runtime checks EMA-21 against the
   whole position; it does not wait for a partial target before managing a
   runner. The chart's green EMA-exit band represents the realized move rather
   than a planned target and is misleading. The requested runner behavior is
   a policy change and must be tested as a new variant; the old R1 record stays
   unchanged.

5. **Reference labels omit timeframe and use an incomplete timeframe map.**
   `pretty_ref()` drops prefixes such as `M3_`, `M10_`, `M30_`, `H4_`, and
   `D1_` when explaining FVG/IFVG references. `reference_timeframe()` currently
   recognizes only M5, M15, and H1; other explicit source frames fall back to
   M1. In testing trade 29, `tp_ref=M30_fvg_bull_high` but the saved
   `tp_timeframe` is M1. Reports must take an explicit timeframe from the
   reference token and must distinguish session/day levels, which have no
   candle timeframe.

6. **“Distribution phase 1” is an unhelpful label.**
   `distribution_phase` is a 0/1 state, not a numbered phase taxonomy. A value
   of 1 means the PO3 distribution state is active after a sweep and a close
   beyond the manipulation-leg extreme. Reports should say “PO3 distribution
   active” and define PO3 once, not print “phase 1”.

7. **The plotted SMT count does not represent the usual cross-market swing
   divergence.** The current feature computes `primary pivot AND NOT secondary
   pivot on the same bar`, and the chart draws every such event. It does not
   compare corresponding successive highs/lows in the two instruments. This
   explains the repeated, crowded SMT lines on trade 24 and is not an adequate
   SMT definition. ICT's primary 2022 mentorship examples compare corresponding
   same-timeframe swing behavior in correlated markets such as NQ and ES:
   [Episode 22](https://www.youtube.com/watch?v=QKc_i90chVg) and
   [Episode 38](https://www.youtube.com/watch?v=36184dDAqtM). For positively
   correlated indices, the conventional bearish example is one market making
   a higher high while the other fails to confirm; the bullish example is one
   making a lower low while the other fails to confirm. This is a description
   of the source concept, not evidence that SMT predicts returns.

## Required corrections

- Redraw historical R1 charts from the preserved tick-fill ledger after the
  report-only replay finishes. Do not retrain to fix figures.
- Remove FVG/IFVG background zones from the default per-trade chart. Keep the
  selected TP level and price line, annotated with its direction and source
  timeframe.
- Aggregate all close fills by position ID for PnL, trade count, and chart
  annotations. Plot each tick entry and each partial/final tick exit at its
  recorded timestamp and fill price; report the full-position net PnL.
- Record and plot every SL adjustment, including the automatic break-even move
  after a partial. Keep the initial stop, active stop path, and eventual stop
  fill distinct.
- Use consistent spellings: “stop loss (SL)”, “take profit (TP)”, “Fair Value
  Gap (FVG)”, “Inverse Fair Value Gap (IFVG)”, and “Smart Money Technique
  divergence (SMT)”; use timeframe suffixes such as “Bearish FVG (M15)”.
- Replace the current SMT event rule with causal, paired swing-high/swing-low
  divergence across the two correlated markets. Plot no repeated unmatched
  pivots. Validate on synthetic paired series before using it in new training.
- For future policy experiments, constrain EMA-21 management to a remaining
  runner after at least one structural partial has filled. Preserve hard
  account risk limits and compare against an otherwise matched control.
- Do not impose an arbitrary fixed point-distance cap from these charts alone.
  The audited testing trade 29 risked $758.49 against the $900 request; a
  different point cap would be a new risk-policy experiment.

## Chart corrections implemented

- Default per-trade charts no longer paint unrelated FVG/IFVG background zones.
  They show selected order levels and actual tick fills.
- Trade PnL combines partial and final fills by position ID, and captions
  reconcile signal, entry fill, exit fills, size, and net result in plain terms.
- Stop adjustments are logged for new runs and shown as a time-ordered active
  stop path. Where an old ledger omitted a post-partial adjustment, the chart
  labels a reconstruction from the saved config instead of presenting it as a
  directly logged event.
- Deviation/range-projection lines are drawn only when the trade's recorded
  stop or target reference selected a `dev_*` level. These are labeled as
  swing-range projections, not statistical standard deviations.
- Swing rays begin at the pivot wick and end on the first later candle whose
  wick reaches that level; they no longer extend across later, unrelated bars.
- SMT overlays now require paired confirmed highs or lows within the matching
  time tolerance and mark only a divergence between the paired swings.
- Reference captions include source timeframes; PO3 state and EMA-21 exit
  semantics use explanatory labels. Historical EMA-21 exits remain whole-
  position exits in R1 and are not retroactively changed.

## Current evidence limits

R1 is a one-seed development result. The 2026 report period was previously
exposed and is not a confirmatory holdout. The chart fixes affect
interpretability; changes to SMT inputs, exit semantics, or stop management
change policy behavior and require new matched training evidence.
