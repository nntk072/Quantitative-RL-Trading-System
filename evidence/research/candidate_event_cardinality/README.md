# Candidate event cardinality register

This packet reconciles existing configured-profile producer ledgers, scalar
feature projections, candidate-scoped source-time identities, and the scoped
historical trace search. It deliberately preserves their different counting
units. It does **not** estimate one ground-truth logical-event count.

The selected profile supports 24 candidate tuples and disables 84. Across the
24 supported tuples, the identity census has 488,008 active candidate-row
occurrences and 109,391 candidate-scoped source-time IDs, with no missing
required source times. The new `candidate_identity_contract.csv` is generated
from the production v3 identity function and gives the ordered source-time
fields and unit scales for all 108 categories, plus support and episode counts.
Those IDs remain scoped to candidate category; the packet does not infer one
global market-event ontology or deduplicate objects across candidate families
and timeframes.

The register CSV now exposes identity episode starts and adjacent identity
changes alongside candidate rows and IDs. It also reports PO3 producer
sequences, standard-deviation source-leg projections, and IFVG per-zone
confirmations separately from their scalar projections. None is a count of
policy proposals, actions, orders, fills, or trades.

The refreshed artifact inventory recognizes the matched-baseline writer's
`decisions.csv` files as selected-setup traces. These current controlled
baselines record decision IDs, candidate IDs, and eligibility and are linked
to opened positions by the independent accounting packet. They do not recover
the earlier selected historical policy's per-decision actions. The historical
candidate-to-action search remains a bounded no-go within the scanned physical
roots; the scan does not follow directory symlinks and is not a global absence
claim. Candidate price-geometry traces remain unavailable.

## Files

- `cardinality_register.csv`: each measure, unit, overlap rule, interpretation,
  and source path.
- `candidate_identity_contract.csv`: production source-time key fields, scales,
  and selected-profile coverage for each of the 108 categories.
- `cardinality_register.json`: input hashes, packet checksum verification,
  scope totals, and explicit unresolved counts.
- `OUTPUT_SHA256SUMS`: hashes for this packet and its reusable generator.

## Reproduction

Run from the repository root on a compatible project environment:

```bash
.venv/bin/python scripts/research/analysis/evidence/build_candidate_event_cardinality_register.py
```

The generator verifies the source packets' `OUTPUT_SHA256SUMS` files before
reading their ledgers and refuses to produce the register if documented census
totals or the IFVG scalar/per-zone reconciliation do not match.
