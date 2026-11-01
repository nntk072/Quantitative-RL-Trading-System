# SMT divergence

In this repository, SMT compares confirmed swing behavior for the configured
primary and secondary instruments (commonly US100 and US500). The feature
aligns the secondary stream on the primary index, identifies confirmed pivots,
matches events within a tolerance based on the configured swing period, and
compares successive paired highs or lows. It also emits rolling close
correlation and normalized close spread.

A bearish divergence means one instrument makes a higher paired swing high
while the other does not; bullish divergence mirrors that comparison at swing
lows. Confirmation uses right-side bars, so the event is exposed at
confirmation time, not backdated as information available at the pivot.
Timestamp alignment and prefix tests are critical: an unmatched or stale
secondary observation must not be mistaken for contemporaneous evidence.

SMT is an input/context feature, not an automatic direction command or a
validated predictive signal. See [`features/context/smt.py`](../../features/context/smt.py),
[feature catalog](../reference/feature_catalog.md), and
[`test_smt.py`](../../tests/unit/features/test_smt.py).
