# Security hardening status

**Updated:** 2026-10-23
**Scope:** Current `main` checkout and the Linux runtime-plus-dev dependency set.

## Current state

- The locked dependency audit now reports zero finding records, zero unique package/advisory pairs, and zero affected packages. The fail-closed gate has no active reviewed exceptions.
- The audit skips the exact CUDA build `torch==2.14.0+cu130`, which is not available from PyPI. Its security status remains unverified by this audit; do not describe the full environment as vulnerability-free.
- The reviewed dependency changes are recorded in `pyproject.toml`, `uv.lock`, `requirements.txt`, and `requirements-dev.txt`. `uv lock --check` and `make deps-check` pass.
- The secret scanner passes with only its configured Base64 and Hex entropy detectors disabled. The audit scripts, exception file, and tests are wired into required CI jobs.
- Full-tree Ruff format, Ruff lint, and Mypy pass (739 files). The scoped compatibility and evidence suite passes (110 tests), including checkpoint migration, experiment run artifacts, numerical reports, and VAE loading.
- `load_vae_from_checkpoint` uses `weights_only=True` for tensor state dictionaries.

## Historical baseline

The frozen Linux audit in the historical baseline found 121 finding records, 78 unique package/advisory pairs across 14 packages. Its original report is [`evidence/pip_audit_locked_linux_dev_20261021.json`](evidence/pip_audit_locked_linux_dev_20261021.json). That report is retained as the pre-remediation snapshot and does not describe the current lock.

The historical agent implementation plan was moved outside the repository to
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/docs/security/`.
The current audit state and limitations are recorded above.
