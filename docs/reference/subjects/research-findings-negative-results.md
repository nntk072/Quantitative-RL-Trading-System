# Research findings and negative results contract

**Status:** draft
**Scope:** Research-report dispositions and the evidence needed to interpret them.

| Disposition in research prose | Meaning | Required record |
|---|---|---|
| Not measured | Current evidence is missing or the method has yet to run | Method, unavailable evidence path and specific missing provenance |
| Invalid | An attempted outcome violates its design, data or execution validity contract | Run identity, failed invariant and available diagnostics |
| Incomplete or censored | A planned path has limited or unobserved follow-up | Planned window and outcome, observed coverage and stopping or censoring reason |
| Valid breach | A hard account floor was crossed under the declared rules | Breach reason, time, retained account path and terminal disposition |
| Valid no-trade | A complete valid path has zero trades | Coverage, eligibility or policy evidence, account outcome and counts |
| Bounded negative result | Recorded evidence fails a prespecified criterion under a valid design | Comparison, methods, affected seeds and paths, limitations and artifact references |

These prose dispositions describe outcomes. Use the actual schema fields
and the producing system's statuses when writing manifests. In v2, each
run has its own role, status, identity and artifacts. A finding record also
includes its ID, hypothesis, comparisons, claims and supporting artifacts.

Assign R1 for inspectable saved evidence, R2 for regeneration from retained
machine-readable evidence, R3 for a supported frozen-policy replay and R4
for a supported training rerun. Record the verified scope for each level.
When evidence is absent, leave the level unassigned.

Sources are `schemas/research_result_manifest_v2.schema.json`,
`scripts/research/analysis/evidence/verify_result_manifest.py` and
`config/research/prospective_research_protocol.yaml`.
See the [findings register](../../research/findings_register.md)
and [subject guide](../../subjects/E_evaluation_research/research-findings-negative-results.md).
