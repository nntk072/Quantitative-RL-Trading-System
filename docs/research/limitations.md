# Research limitations

Quantitative trading results are conditional on the supplied data, feature
availability, action interpretation, risk rules, execution assumptions, and
evaluation procedure. Reports should state these conditions and avoid claims
that extend beyond the recorded evidence.

## Data and timing

The current research scope uses only files already present in the checkout.
Provider identity, license terms, and redistribution rights are not assessed;
no rights claim is made and raw data are not included in the evidence release.
Missing quotes, timestamp ties, session-calendar differences, and feed gaps can
change feature values or executable fills. Row counts alone do not identify
whether a short session was scheduled or whether data are missing.

The current research program has prior exposure to its 2026 reporting interval.
Its outcomes are exploratory/report-only, as recorded in the
[research execution plan](workflow.md). No rerun
on those dates can make them a fresh final holdout.

## Simulation and execution

Historical replay depends on the configured spread, fees, latency, fill source,
quote availability, and risk controls. A modeled tick fill does not establish
broker queue position, market impact, live latency, or live profitability.
Bar-only execution cannot reconstruct the exact order of events within a bar.
The learning environment and event-driven backtest have different purposes;
their metrics require an explicit comparison before they can be combined.

## Statistical interpretation

Multiple experiments and repeated decisions on the same outcomes create
selection risk. A strong seed or period is not evidence of robustness by
itself. State the number and role of attempted comparisons, include matched
controls and uncertainty where appropriate, and preserve null, failed, and
inactive results. Explanations for performance changes remain hypotheses
unless an experiment isolates the proposed cause.
