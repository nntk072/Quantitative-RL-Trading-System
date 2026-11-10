# Observation validity across runtime profiles

This packet measures configured model-facing training observations for all 141 runtime profiles in the feature inventory (`feature_configuration_inventory_141` is maintained in the sibling prefix-invariance packet). The profiles resolve to 28 observation-contract groups. All groups completed with no errors; the source hashes matched at run start and finish. The packet contains 19,350 feature/timeframe rows.

The audit ran with four direct worker processes inside existing Slurm allocation `21492849` on `gpuarm2`. No additional Slurm job or step was created. The summary covers finite/non-finite, leading/interior missingness, and finite-zero counts. It is feature-contract evidence, not learned-policy or economic evidence, and it does not attribute every missing value to a producer cause.

`RAW_RUN_SHA256SUMS.txt` preserves the file hashes emitted by the original scratch run. For clone portability, generated output-root paths were rewritten from the agent scratch directory to this tracked packet and cache paths were changed to `/tmp/qrl-observation-warmup-cache`; `audit_launcher.log` and `audit_launcher.exit` preserve the launcher output and status. `SHA256SUMS` verifies the archived packet.

Regenerate from the repository root with:

```bash
.venv/bin/python scripts/research/analysis/features/audit_observation_warmup_validity_profiles.py \
  --inventory evidence/research/feature_causality/feature_configuration_inventory.json \
  --output-dir evidence/research/feature_causality/observation_validity_current_source_141 \
  --cache-dir /tmp/qrl-observation-warmup-cache \
  --workers 4
```
