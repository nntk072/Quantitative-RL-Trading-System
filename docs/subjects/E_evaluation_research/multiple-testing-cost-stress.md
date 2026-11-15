# Multiple testing and cost stress

**Status:** draft
**Use this when:** You need to account for a search over several alternatives or interpret sensitivity to execution assumptions.

## Summary and use this when

A search history defines the multiplicity problem. An execution scenario
defines the economic assumptions behind each scenario result. Keep both with
the trial records to make a finalist's reported sensitivity interpretable.

- Freeze the primary contrast and the role of secondary tests before outcomes.
- Record rejected, interrupted and incomplete trials beside completed trials.
- Stress a frozen finalist under declared assumptions on matched inputs.
- Reconcile modeled fills and their charges before comparing sensitivity.

## Key terms

- [Primary contrast and multiplicity](../../research/validation_protocol.md)
- [Spread, slippage and cost provenance](../C_trading_risk_execution/execution-fills-costs.md)
- [Reproducibility levels](../../reproduce/result_registry.md)

## Explanation

### The rule

The prospective protocol defines one primary treatment versus always-no-trade
contrast. Other architectures, rewards, thresholds and subgroups remain
exploratory unless the correction and selection procedure was frozen in
advance. A trial ledger preserves the search history required to interpret
the family of comparisons.

`analyze_paired_seed_metrics` applies Holm adjustment to the supplied
metric family in the general paired-seed path. The single-primary selection
path records one contrast without a Holm-adjusted p-value. Keep the chosen
family and reporting mode with the payload.

The deflated Sharpe helpers describe selection over trial Sharpe estimates.
Use a per-observation, non-annualized Sharpe and compatible cross-trial Sharpe
dispersion. The probability function uses skew, non-excess kurtosis, and the
number of returns feeding the track record. The helper cannot reconstruct
which alternatives the researcher explored.

### Why replay matters for cost stress

Spread, slippage, commissions and quote availability can change orders,
fills, subsequent positions and whether a path breaches. Replay the declared
scenario through the same execution and account rules when those changes can
affect the path. A per-fill decomposition accounts for what happened in a
particular replay.

`decompose_fill_costs` aggregates completed positions, allocates entry
charges over realized close sizes, and checks net PnL against midpoint gross
PnL less spread, slippage and commission. Missing quote or cost evidence
returns a status explaining unavailability.

### Failure modes

- A shortlist of successful configurations undercounts the search.
- Feeding an annualized Sharpe into the deflation formula changes its scale.
- Testing several costs and publishing only the favorable scenario changes
  the interpretation of the stress test.
- Missing quote data can alter fill opportunities as well as liquidity costs.
- A ledger with a missing position ID cannot prove a cost reconciliation.

## Worked example

The Tier A notebook applies Holm adjustment to three fixed p-values and
reconciles one synthetic cost identity under two declared charge schedules.
The example arithmetic uses fixed fills and does not simulate market execution.

```{toctree}
:hidden:

examples/multiple-testing-cost-stress
```

## Tasks

- State the primary contrast and any corrected family under the [validation protocol](../../research/validation_protocol.md).
- Review assumptions against the [execution costs guide](../C_trading_risk_execution/execution-fills-costs.md).
- Use the [multiplicity and cost contract](../../reference/subjects/multiple-testing-cost-stress.md) when interpreting outputs.
- Look for current measured sensitivity in the [findings register](../../research/findings_register.md).

## Contract

| Item | Meaning | Source |
|---|---|---|
| Holm adjustment | Ordered raw p-values weighted by remaining family size, then running maximum capped at one | `scripts/research/analysis/evidence/analyze_paired_seed_results.py::_holm_adjust` |
| Deflation benchmark | Cross-trial Sharpe dispersion and recorded number of compared configurations | `evaluation/metrics/deflated_sharpe.py::expected_maximum_sharpe` |
| Deflation probability | Per-observation Sharpe, benchmark, observation count, skew and non-excess kurtosis | `evaluation/metrics/deflated_sharpe.py::deflated_sharpe_probability` |
| Cost reconciliation | Completed positions with identity, fill costs and explicit closure | `evaluation/reporting/cost_decomposition.py::decompose_fill_costs` |
| Finalist stress | Declared cost stress and missing-quote stress requirements | `config/research/prospective_research_protocol.yaml::robustness` |

## Verify

- `tests/unit/evaluation/test_deflated_sharpe.py` covers the benchmark and
  probability calculations.
- `tests/unit/research/test_paired_seed_statistics.py` covers paired
  inference and adjustment output.
- `tests/unit/evaluation/test_cost_decomposition.py` covers cost lineage
  and reconciliation.
- Cost and missing-quote robustness on refreshed research data are
  **not measured**.

## Limits and common mistakes

- Adjustment covers the specified family. It cannot repair prior exposure
  or an incomplete record of decisions made after seeing results.
- Deflated Sharpe summarizes a track record against a specified benchmark.
  Dependence between alternative trials and serial dependence in returns
  remain relevant to interpretation.
- A cost scenario applies to the specified fill and account model. State
  changes must be traced through the replay.
- A reconciliation result reflects the completed-position realized ledger.
  Open exposures and their economic effects remain in the account path.

## Change checklist

- Freeze the contrast, trial family, scenarios and reporting rules.
- Preserve attempts and outcome statuses in trial order.
- Check Sharpe units and report the underlying return count and moments.
- Hold other evaluation settings fixed when stressing one cost dimension.
- Preserve quote source and charge provenance for every used fill.
- Record unsupported scenarios and report the same safety outcomes for each.

## Review procedure

1. List configurations and outcomes inspected before the finalist freeze.
   Include interrupted attempts and variants changed after viewing metrics.
2. Identify the planned primary contrast and the exact secondary family.
   Match the corrected report to that family and the recorded settings.
3. For a deflation result, recover the per-observation source returns and
   cross-trial dispersion inputs. Record their cadence and the trial count.
4. Record each stress scenario's quote source, charge assumptions and period.
   Confirm that unchanged dimensions match the reference scenario.
5. Compare entry and exit fills, missing quotes, risk gates and terminal
   states before comparing net returns.
6. Reconcile the completed-position cost ledger. Explain remainders and
   unavailable fields using the corresponding account or fill record.
7. Preserve each scenario and its hashes even when an arm stops early or
   produces no trades.
8. Check the finalist selection date against the report period's exposure
   record. Keep stress outcomes in their declared role.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `evidence_reporting_engineer`
