# Current 109-choice model contract audit

This packet verifies the current matched MTF control and setup-conditioned
configuration contracts against their recorded implementation source hashes.
Both have the same six-coordinate action schema, 109-category setup mask, and
observation shapes. The control does not condition execution on setup ID; the
conditioned variant uses a 32-dimensional setup embedding for its 128-unit
execution head. The setup selector remains market-latent-driven. The contracts
use training data only and record zero environment steps, policy actions, and
report-period rows.

The support review covers all 108 catalog entries: 24 are enabled by the
selected configuration and 84 are unsupported there. Source-test references
cover use of earlier valid history and valid-candidate masking. The scoped
276-artifact scan found no qualifying historical per-decision setup or
candidate price-geometry trace; this is not global absence proof.

This audit distinguishes categorical setup-ID conditioning from candidate
price geometry. It does not verify every historical checkpoint's tensor
shapes, replay a policy, or establish economic performance. Declared processed
dataset-array hashes are not recomputed here; current source-file hash evidence
is maintained in the market-data quality packet.

Regenerate with:

```bash
PYTHONPATH=. .venv/bin/python scripts/research/analysis/models/verify_configured_observation_action_contracts.py
```
