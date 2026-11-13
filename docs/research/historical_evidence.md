# Historical evidence

Historical evidence is presented using the current research taxonomy while the
original evidence directories remain immutable. The machine-readable catalog is
[`config/research/history.yaml`](../../config/research/history.yaml).

| Domain | Consolidated historical material |
|---|---|
| Data | market-input integrity, quality scans, pipeline denominators, tick/quote coverage |
| Features | feature causality, opportunity census, candidate identity/geometry, event ledgers |
| Policy | observation/action semantics, setup-conditioned replay, checkpoint recoverability, failure mechanisms, candidate outcomes |
| Portfolio | matched baselines and withdrawn historical performance/attribution records |
| Execution | simulator parity, fill/quote alignment, exit-action semantics |
| Validation | function/test coverage and model-input validity |
| Reporting | preserved source lineage and historical release packets |

Historical records may be rewritten **only at the index/synthesis layer**.
Descriptions may use current terminology, combine duplicated explanations, and
state the present disposition more clearly. Raw evidence, source snapshots,
checksums, run manifests, and archived result payloads are not edited to make
them look current.

Withdrawn performance evidence remains available for provenance but is not
restored as a current result. Superseded historical 2M screens do not become
inputs to current policy selection.

Generate the complete normalized index with:

```bash
uv run qrl-experiment research history
```
