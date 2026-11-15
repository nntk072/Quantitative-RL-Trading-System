# Research findings and negative results

**Status:** draft
**Use this when:** You need to interpret a registered finding, report a bounded negative result, or document missing evidence.

## Summary and use this when

A research finding answers a declared question using a measured outcome and
traceable evidence. When the measurement is absent, record what is missing.
Keep valid unfavorable paths in the report so the scope of the finding is
visible.

- Check the [findings register](../../research/findings_register.md) for current status.
- Record method, period role, outcome and evidence path for each finding.
- Assign a reproduction level supported by the retained evidence.
- Preserve invalid, breached, no-trade, censored and incomplete runs.

## Key terms

- [Reproduction levels R1–R4](../../reproduce/result_registry.md)
- [Research result manifest](../../research/result_identity_and_evidence.md)
- [Development and report-only periods](../../research/validation_protocol.md)

## Explanation

### The rule

The research result manifest v2 connects a finding to run identities,
comparisons, claim text and supporting artifacts. Keep each run's original
status and period role in that record. Preserve the ledgers or diagnostics
used to decide whether an outcome was valid.

A valid breach is relevant to the survival question and makes the candidate
infeasible for prospective selection. A valid no-trade path contributes its
observed account outcome and exposure. A genuinely unavailable run leaves a
gap in replication. Each case affects the claim in a different way.

When no candidate qualifies under the prespecified survival gate, the
protocol supports a bounded negative result for the tested candidates and
paths once the complete evidence is retained. If the safety gate passes but
the full paired inference rule fails, the protocol supports the bounded
conclusion that no candidate demonstrated superiority under that design.

### Why the provenance is part of the result

An inspectable report, recomputable numbers, replayable checkpoint and
rerunnable training depend on different retained artifacts. The project's
R1–R4 scale identifies which of these review paths is supported. An available
procedure in source describes how to collect evidence.

The clean restart removed the historical result bundles. The retained
raw-data manifest records file identity. The refreshed evidence status,
measurement methods and missing records are collected in the findings
register.

### Failure modes

- Recording an outcome from a removed figure leaves the result unauditable.
- Turning a missing metric into zero makes a gap look like an observation.
- Dropping breached paths makes the survival denominator wrong.
- Renaming an exposed interval can make an old exploratory comparison appear
  confirmatory.
- Describing a deterministic synthetic check as a scientific measurement
  changes the stated evidence scope.

## Worked example

The Tier A notebook reviews a synthetic planned set of paths with one valid
breach, one valid no-trade path and one missing path. It retains all three
records and demonstrates why full survival and coverage fail in this example.

```{toctree}
:hidden:

examples/research-findings-negative-results
```

## Tasks

- Check the [findings register](../../research/findings_register.md) before citing a result.
- Use [result identity](../../research/result_identity_and_evidence.md) to bind claims to evidence.
- Consult [validation and stopping rules](../../research/validation_protocol.md) for permitted conclusions.
- Review the [findings contract](../../reference/subjects/research-findings-negative-results.md) for distinctions among outcome records.

## Contract

| Item | Meaning | Source |
|---|---|---|
| Finding record | Finding ID, question, status, evidence grade and limitations | `schemas/research_result_manifest_v2.schema.json` |
| Run record | Required role, status, identity and artifact list per run | `schemas/research_result_manifest_v2.schema.json::$defs.run` |
| Frozen identity | Explicit unknowns disallowed and freeze timestamp required | `scripts/research/analysis/evidence/verify_result_manifest.py::validate_result_manifest` |
| Bounded negative result | Preserve outcome when the configured qualification or paired selection rule fails | `config/research/prospective_research_protocol.yaml::stopping` and [validation protocol](../../research/validation_protocol.md) |
| Source and artifact integrity | Verify referenced artifacts against recorded hashes | `scripts/research/analysis/evidence/verify_result_manifest.py::validate_result_manifest` |

## Verify

- `tests/unit/research/test_result_manifest_v2.py` covers required identity,
  frozen-manifest validation and artifact linkage.
- `tests/unit/research/test_experiment_trial_ledger.py` covers the
  preservation and reconciliation of run and attempt records.
- `tests/unit/research/test_paired_seed_statistics.py` covers seed pairing
  and the reported inference.
- The current evidence tree and [research evidence report](../../research/research_evidence_report.md)
  establish which refreshed records are available.

## Limits and common mistakes

- Report invalid runs with their specific violated contract and any retained
  diagnostics. Preserve planned and actually observed denominators.
- Keep partial follow-up distinct from a full path with no trades.
- A bounded negative result applies to the tested conditions, observations,
  simulator and stopping criteria.
- A reproducibility level describes a review route. It does not quantify
  the evidential strength of a reported effect.
- Keep untouched and exposed periods identified by the actual selection history.

## Change checklist

- Check the required source, input, config and run identity.
- Record status, scope, method and raw evidence paths.
- Preserve invalid and incomplete entries and their reason codes.
- Record both planned and observed replicate counts for each comparison.
- Verify that each claim's wording follows the gate and inference decision.
- Assign only a reproduction level supported by retained artifacts.
- Describe absent outcomes as **not measured** and name the missing provenance.

## Review procedure

1. Read the registered hypothesis and identify the comparison population the
   study planned before outcomes.
2. Look for the source revision, resolved configuration, period role, run
   identity and artifact digests on every reported path.
3. Reconcile planned, attempted, valid and complete runs with the trial
   ledger. Record each path's status and the basis for that status.
4. Check the safety decision before interpreting profitability. Preserve
   latched breaches and report data/contract failures separately.
5. Check the comparison and inference prerequisites. If the analysis never
   ran or its provenance is missing, enter **not measured** for that question.
6. For a valid negative finding, record the specific failed criterion and
   the scope of the tested alternatives and paths.
7. Match the reproduction level to the retained artifacts and verification
   method. Describe evidence gaps so the finding's limits can be reviewed.
8. Confirm that the declared period role is supported by actual use of the
   data. Keep the wording within the supported evidence.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `evidence_reporting_engineer`
