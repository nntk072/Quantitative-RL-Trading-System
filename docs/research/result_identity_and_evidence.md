# Research result identity and evidence

Use the versioned research result manifest to bind a finding to its question,
run identities, exposure roles, claims, and content-hashed evidence. The v1
schema remains available for existing records. New empirical findings should
use `qrl.research_result_manifest.v2` and
[`research_result_manifest_v2.schema.json`](../../schemas/research_result_manifest_v2.schema.json).

Every v2 run identity contains the fields required by the research plan. A
known value is stored directly. An unavailable value must be represented as
`{"status": "unknown", "reason": "..."}`; `null`, an omitted field, or an
invented default is invalid. Draft and descriptive results may retain reasoned
unknowns. A frozen result rejects all unknown identity values and requires a
freeze timestamp.

The verifier checks schema shape, run/comparison/claim references, artifact
paths within the repository, and SHA-256 values. It does not rehash raw data
that is referenced only by an identity digest, and it does not claim that a
historical result can be independently regenerated from a Git checkout.
For artifacts moved out of the checkout, v2 permits `storage_scope` to name
the project research archive. The verifier resolves those relative paths only
inside the sibling `Quantitative-RL-Trading-System-research-archive` root;
absolute paths and arbitrary external targets remain invalid.

Run the verifier with automatic schema selection:

```bash
python scripts/research/analysis/evidence/verify_result_manifest.py \
  evidence/research/releases/negative-evidence-readiness/selected_pair_viability_manifest.json
```

The selected seed-50 pair record is intentionally draft and descriptive. It
preserves both failed training risk-survival outcomes, the historical gross
negative-close daily-loss semantics, exposed-period limitations, and explicit
unknowns. It is not a promotion or confirmation record.
