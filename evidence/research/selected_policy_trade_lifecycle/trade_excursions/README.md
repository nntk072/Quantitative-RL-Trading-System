# Selected policy trade excursion bounds

This packet derives per-position favorable and adverse price excursions for
the preserved A4A and A4B training ledgers. It joins each completed position
to its opening and final closing fill, then measures the configured TickBook's
liquidation-side quotes between those fills. It does not replay either policy.

The source ledgers contain 987 completed A4A trades and 825 completed A4B
trades. Using each trade's recorded entry fill and initial stop distance as
the R denominator:

| Arm | Completed trades | Median MFE (R) | Mean MFE (R) | Median MAE (R) | Mean MAE (R) | Observed paths reaching 1R MFE |
|---|---:|---:|---:|---:|---:|---:|
| A4A | 987 | 0.569 | 0.960 | 0.815 | 0.670 | 32.4% |
| A4B | 825 | 0.552 | 0.944 | 0.774 | 0.663 | 31.9% |

The arms have different trade cohorts. These summaries are descriptive and do
not establish a paired treatment effect, an economically feasible alternative
exit, or causal loss attribution. Excursions use bid liquidation quotes for
longs and ask liquidation quotes for shorts; commissions are not deducted. R
is price excursion divided by the recorded initial stop distance, not realized
net return divided by risk.

## Timestamp bounds and limits

Ticks tied at a recorded entry or exit timestamp have no established
sub-timestamp order. The lower path includes strictly interior tick rows and
the recorded endpoint liquidation-side quotes. The upper path includes every
source row at either endpoint timestamp. The bounds differ for 2 A4A positions
and 1 A4B position. Entry timestamp ties occur for 5 A4A and 3 A4B positions;
exit timestamp ties have the same counts.

The report uses each arm's resolved timezone (`Etc/GMT-3`) and 0.25 price grid.
It follows the current TickBook's missing-side carry-forward behavior. The
local quality report hash-matches the selected tick CSV; it does not establish
provider rights, an authoritative session calendar, or authoritative feed
chronology. The source is the 2025 development/training period, and the
associated 2026 holdout was already inspected. These measurements are not
untouched confirmation evidence.

## Reproduction

Run from the repository root with the x86 environment on an x86 host, or the
matching Python environment on the relevant architecture:

```bash
python scripts/research/analysis/evaluation/summarize_selected_policy_trade_excursions.py \
  --arm a4a=outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4a_entry_fsm_hidden_qgrid025/training/fills.csv \
  --arm a4b=outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4b_entry_fsm_qgrid025/training/fills.csv \
  --config a4a=outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4a_entry_fsm_hidden_qgrid025/config.yaml \
  --config a4b=outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/reanalysis_daily_stop_semantics_20261024/ladder_a4b_entry_fsm_qgrid025/config.yaml \
  --ticks-csv data/training/US100.cash_202412300105_202610162349.csv \
  --quality-report evidence/research/releases/negative-evidence-readiness/local_market_data_quality.json \
  --out-dir evidence/research/selected_policy_trade_lifecycle/trade_excursions
```

The command builds the full TickBook from the 2.6 GB local tick export, so run
it in a suitable compute allocation rather than on the login host. It refuses
to overwrite an existing evidence directory. Input and output checksums are
listed in [`evidence_manifest.json`](evidence_manifest.json); per-position
metrics are in [`a4a_trade_excursions.csv`](a4a_trade_excursions.csv) and
[`a4b_trade_excursions.csv`](a4b_trade_excursions.csv).
