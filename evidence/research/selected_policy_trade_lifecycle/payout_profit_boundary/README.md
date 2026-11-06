# Payout profit-boundary verification

## Result

The selected-policy lifecycle summarizer now reports an explicit invariant for
every recorded payout: the amount must be positive and the pre-reset balance
must exceed the operating balance. It separately verifies that the payout
equals the excess over the operating balance. This encodes the user's rule
that losses and principal cannot be withdrawn.

The current-source report was rebuilt from the four hash-linked selected A4
training and report-period partitions. The packet verifier matched all four
input/report manifests, and all four cashflow/equity reports are `matched`.
Each partition has zero payout events, so their payout status is
`not_applicable`; these historical ledgers provide no observed payout cycle.

Synthetic lifecycle tests cover a positive realized-profit payout and reject
negative, zero, or below-operating-balance withdrawals. The summary and packet
tests pass 20/20, and touched-source Ruff format/lint checks pass.

## Scope limits

This verifies the payout accounting invariant and the preserved ledgers. It
does not create an empirical payout result, reconstruct current-risk
counterfactuals, or close the broader Stage E account/report reconciliation.
The selected historical policy remains a failed survival result.

## Reproduction

From the repository root on ARM64/GH200, rebuild each partition from the
archive paths in its existing source manifest with
`scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py`,
writing reports to the corresponding directory here. Then run:

```bash
.venv/bin/python scripts/research/analysis/evaluation/build_policy_trade_lifecycle_packet.py --packet-dir evidence/research/selected_policy_trade_lifecycle/payout_profit_boundary
.venv/bin/python -m pytest tests/unit/research/test_policy_trade_lifecycle_summary.py tests/unit/research/test_policy_trade_lifecycle_packet.py -q
```

Exact test output and source hashes are included in this packet.
