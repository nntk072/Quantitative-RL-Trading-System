# Daily regime feature normalization: comparison result

## Research question

Does normalizing selected daily-market features on their own daily timeline,
before aligning them to minute decisions, improve an otherwise matched PPO
policy?

## Comparison

The control normalized the assembled feature stream after higher-timeframe
values had been repeated across minute rows. The treatment normalized selected
daily features on the daily source timeline before causal alignment. Both
policies used the same PPO setup, market data, account rules, trading actions,
execution assumptions, seed, and training budget.

## Observed outcomes

The prior one-seed 2M screen and its exposed report-only replay are withdrawn
from current performance comparison. The result table is removed because the
screen used a superseded study setup; it must not be used to select a policy or
as evidence for the registered forthcoming 18-arm benchmark. No performance
conclusion is drawn here.

## Interpretation

The withdrawn result does not support a current conclusion about this
normalization change.

## Limits

This is a one-seed comparison. The report-only interval had already been
inspected and is not confirmatory evidence. The comparison tests one feature
normalization change; it does not show that daily regime context is generally
useful or harmful. Detailed position-level regime tables are retained in the
external research archive.
