#!/usr/bin/env bash
# Transactionally rebuild feature profiles used by the 18-variant research screen.
set -euo pipefail
cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
source scripts/compute/slurm/activate_venv.sh
python scripts/maintenance/experiment-runs-or-cache/rebuild_named_prebuilt_feature_caches.py \
    --backup-dir data/prebuilt_feature_cache/backups/pre-18-profile-rebuild_20261017_job21020179 \
    --report outputs/research_audits/replacement_data_20261017/named_feature_cache_rebuild_18variant_20261017_job21020179.json
