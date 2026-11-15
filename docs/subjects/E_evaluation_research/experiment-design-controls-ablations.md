# Experiment design, controls and ablations

**Status:** draft
**Use this when:** You need to register a comparison, select a control, or verify what changed across treatment arms.

## Summary and use this when

Define the question, intervention, controls, period roles, and outcome
criteria before looking at results. The comparison contract decides which
differences support a paired analysis.

- Use always-no-trade as the prospective primary account-value comparator.
- Use random eligible actions and justified rules for secondary comparisons.
- Freeze one intended change per matched ablation.
- Treat hard account survival as the first feasibility condition.

## Key terms

- [Research questions and period roles](../../research/validation_protocol.md)
- [Trade setup eligibility](../B_market_structure_setups/trade-setups.md)
- [Walk-forward splits](../A_data_features/splits-and-walk-forward.md)

## Explanation

### The rule

Define the observational unit and align it with the intervention. A training
ablation can compare paired independent seeds trained with a change in
representation. A replay sensitivity analysis can compare two treatments on
aligned timestamps within an evaluation path. Both require an explicit
control and a record of the settings shared by its counterpart.

`compare_matched_returns` checks exact timestamp alignment and compares a
fixed set of provenance fields across both arms. A supported intervention
must have distinct, non-empty provenance. The other required fields must
match. For a feature intervention, record the feature hashes on both sides
plus the unchanged data, execution, random seed and budget.

`evaluate_tier0_setup_baselines` gives each arm a fresh environment using
the same bars, features, tickbook and common evaluation settings. It accepts
declared period roles and requires a positive explicit dollar risk ceiling
for non-synthetic evaluation. That ceiling bounds requested risk and
realized risk still depends on fills and sizing.

### Why control choice matters

Always-no-trade measures the alternative of retaining operating capital.
Random eligible actions test what the same candidate opportunity set yields
under the configured random policy. A deterministic rule control asks
whether learned selection improves over a specified rule using the same
decision information. Record each policy's action schema and randomness.

Choose the baseline that answers the question and keep the others as
declared. Full-path development survival precedes economic selection.
Report-only periods retain their exposure role across all comparisons.

### Failure modes

- Changing the budget and feature representation confounds attribution.
- Hiding a prerequisite failure by reporting only completed seed pairs
  changes the claimed population of trials.
- A rule control with a different eligibility timeline changes opportunities.
- Equal start/end dates can conceal intraperiod mismatches.
- An arm with high realized value and a hard breach fails survival selection.

## Worked example

The Tier A notebook uses matched synthetic timestamps and source fields for
a policy intervention. It computes the mean paired return difference and
checks that a change to the cost identity is rejected as a second change.

```{toctree}
:hidden:

examples/experiment-design-controls-ablations
```

## Tasks

- Freeze period roles and outcome criteria using the [validation protocol](../../research/validation_protocol.md).
- Review matched inputs with the [evaluation methodology](../../research/evaluation_methodology.md).
- Trace policy eligibility using the [setup catalog](../../reference/trade_setup_catalog.md).
- Check the [matching contract](../../reference/subjects/experiment-design-controls-ablations.md) before interpreting a study.

## Contract

| Item | Meaning | Source |
|---|---|---|
| Primary comparator | Always-no-trade after the treatment qualifies on survival | `config/research/prospective_research_protocol.yaml::primary_statistics` |
| Paired design | Match declared provenance and full ordered timestamp index | `evaluation/metrics/matched_comparison.py::compare_matched_returns` |
| Intervention | One supported field with distinct values across arms | `evaluation/metrics/matched_comparison.py::INTERVENTION_FIELDS` |
| Setup baseline replay | Same inputs and common settings, fresh environment per arm | `evaluation/rollout/matched_setup_baselines.py::evaluate_tier0_setup_baselines` |
| Absolute setup risk ceiling | Required explicitly for a non-synthetic role | `evaluation/rollout/matched_setup_baselines.py::evaluate_tier0_setup_baselines` |

## Verify

- `tests/integration/test_matched_comparison.py` directly tests
  `compare_matched_returns` provenance, timestamp matching and interventions.
- `tests/unit/evaluation/test_matched_comparison.py` covers paired equity
  intervals and their reporting records.
- `tests/integration/evaluation/test_matched_setup_baselines.py` covers
  matched setup rollout contracts.
- `tests/unit/research/test_paired_seed_statistics.py` exercises identified
  seed-pair payloads.
- A matched ablation outcome for the refreshed data is **not measured** in
  the [findings register](../../research/findings_register.md).

## Limits and common mistakes

- A common requested risk ceiling allows different realized losses.
- Equal evaluation execution seeds are one control. The training and
  action-sampling random streams need their own recorded identities.
- Use the full declared path for selection. Exposure and allowable use are
  properties of the period history.
- State whether the ablation changes information, action policy or execution
  using the actual per-arm resolved configuration.
- Report runs with incomplete follow-up in the trial ledger.

## Change checklist

- Freeze the question, comparator, intervention and replicates.
- Identify the shared source, dataset, split, observation and decision rows.
- Compare resolved configurations and identify the intended difference.
- Preserve cost, quote, sizing, account and seed settings across arms.
- Check outcome formulas and the hard-risk gate for every paired path.
- Keep unexpected implementation failures visible before interpreting effects.

## Review procedure

1. Read the registered question and identify the arm that supplies the
   counterfactual. Confirm the primary comparator and the declared role of
   every secondary arm.
2. Read the resolved configuration and ledger from each arm. Match data,
   timeframe, alignment, action semantics and costs before scoring.
3. Follow the intervention through the exact field on both sides and identify
   every additional difference visible in the resolved inputs.
4. Check that matched seed identities come from the executed runs. A seed
   in a planned configuration still needs runtime provenance.
5. Compare timestamp indexes and evaluation endpoints before computing a
   paired statistic. Record which paths completed the full contract.
6. Verify quote coverage and account-risk outcomes. Record feasibility for
   all required treatment paths before looking at the primary currency result.
7. Preserve the prespecified comparison family and independently identify
   any exploratory comparisons made after outcomes.
8. Record the final artifact links and the exact allowed interpretation
   for each reported period.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `evidence_reporting_engineer`
