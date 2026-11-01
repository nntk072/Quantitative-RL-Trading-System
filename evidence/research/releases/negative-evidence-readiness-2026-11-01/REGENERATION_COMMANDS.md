# Regeneration and verification commands

Run from the repository root and use the architecture-matched environment.
On this x86_64 host, the `pytest` console script had a stale shebang, so invoke
pytest through the active interpreter.

## Tracked evidence audit

```bash
.venv-x86/bin/python -m tools.documentation.evidence_audit --check
```

## Manifest-declared provenance DAG

```bash
.venv-x86/bin/python scripts/research/audits/build_research_provenance_dag.py
```

This indexes all discovered `experiment_run.json` and `campaign.json`
manifests. It records their declared hashes and relationships without
re-reading large market-data files or checkpoints.

## Release manifest file hashes

Refresh and then verify the manifest's curated release-content and source-file
hashes after changing any listed file:

```bash
.venv-x86/bin/python scripts/research/audits/update_release_manifest_hashes.py --write
.venv-x86/bin/python scripts/research/audits/update_release_manifest_hashes.py --check
```

The manifest intentionally does not hash itself. Large raw inputs and
checkpoints are outside these maps; their identities remain in the campaign
manifest and the separate bounded audit reports.

## Selected campaign input audit

The full byte-hash and streaming quality scan reads the campaign's large
training/testing exports. Run it in a suitable CPU-node allocation, using the
repository's persistent login-tmux launch procedure; do not run it on the
login host.

```bash
.venv-x86/bin/python scripts/research/audits/audit_current_p6_market_inputs.py \
  --out evidence/research/releases/negative-evidence-readiness-2026-11-01/current_source_market_input_audit.json
```

The command refuses to overwrite existing evidence. The report covers the 39
campaign manifest inputs and preserves explicit limits on timezone, session
calendar, and minute-level execution interpretation. Provider/license
retrieval is outside the requested local-data scope; raw input is not packaged.

## Complete local data checksum inventory

The release checksum manifest covers every entry in the existing local
inventory and records both declared paths and resolved targets. Recheck the
files from a suitable CPU-node allocation:

```bash
.venv-x86/bin/python scripts/research/audits/hash_local_data_inventory.py --check
```

The check rehashes each unique resolved target, confirms inventory sizes and
stable file metadata, and compares all entries with
[`RAW_DATA_SHA256_MANIFEST.json`](RAW_DATA_SHA256_MANIFEST.json). To create a
new manifest, `--write` is accepted only when the output path does not exist;
it never overwrites an existing evidence file. This records local byte
identity only and does not establish provider rights, timezone correctness,
or the authoritative session calendar.

The detailed per-column/tie report was generated with the same script and
identical 39 files, from the named persistent login tmux session using the
bounded CPU-node wrapper:

```bash
bash /scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/launch_p6_tick_detail_audit_20261101.sh
```

This wrapper writes
`current_source_market_input_diagnostic_20261101.json`; do not invoke a new
allocation directly from a transient Codex/SSH terminal.

## Focused current-source test group recorded in this snapshot

```bash
.venv-x86/bin/python -m pytest \
  tests/unit/features/test_causal_features.py \
  tests/unit/features/test_htf_alignment.py \
  tests/unit/trading/test_risk_properties.py \
  tests/unit/simulation/test_environment/test_trading_env_golden_traces.py \
  tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py \
  tests/integration/backtest/test_broker_fill_accounting.py \
  tests/integration/backtest/test_broker_quote_parity.py -q
```

The recorded run completed with 54 passed and two transformer warnings.

## Final release quality and documentation gate

On an x86_64 checkout, run from the repository root in a bounded CPU-node
allocation. The command performs full-tree Ruff format/lint and Mypy, the
scoped current-source suite (including hybrid actor and tick-loader contracts),
and a strict rendered documentation build. It does not run `pytest tests/` or
the repository-wide CI phase.

```bash
QRL_PYTHON=.venv-x86/bin/python \
QRL_RUFF=.venv-x86/bin/ruff \
QRL_SPHINX_OUT=/tmp/qrl-release-docs-20261101 \
bash scripts/research/audits/verify_release_quality.sh
```

The accelerator-only hybrid actor test is skipped on a CPU-only node. This
does not authorize a short GPU diagnostic job.

The following isolated setup and audit checks also passed:

```bash
.venv-x86/bin/python -m pytest \
  tests/unit/decisioning/test_trade_setup_contract.py \
  tests/unit/decisioning/test_trade_setup_properties.py -q

.venv-x86/bin/python -m pytest \
  tests/unit/models/test_trade_setup_observation_schema.py \
  tests/unit/simulation/test_environment/test_trade_setup_observation.py \
  tests/integration/test_trade_setup.py -q

.venv-x86/bin/python -m pytest \
  tests/unit/research/test_current_p6_market_inputs.py -q
```

The three commands reported 12, 22, and 2 passed, respectively.

## Bounded P6 row recomputation

```bash
.venv-x86/bin/python -m jupyter nbconvert --to notebook --execute \
  --inplace docs/reproduce/p6_monthly_exit_decomposition.ipynb
```

This notebook recomputes the tracked paired-row analysis only. It does not
replay checkpoints or fills from raw ticks and does not upgrade the result to
R3/R4. Run in a disposable copy if the notebook execution would rewrite a
tracked artifact.

## Release limitations

There is no regeneration command here for the scratch-only full P6 replay,
because a frozen checkpoint replay was not run. Do not run training or inspect
an unregistered future period as a substitute for the open data and protocol
gates.
