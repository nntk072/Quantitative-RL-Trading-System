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
.venv-x86/bin/python scripts/research/analysis/evidence/build_research_provenance_dag.py
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
.venv-x86/bin/python scripts/research/analysis/market_data/scan_local_market_data_quality.py \
  --out evidence/research/releases/negative-evidence-readiness/local_market_data_quality.json
```

The command refuses to overwrite existing evidence. The report covers the 39
campaign manifest inputs and preserves explicit limits on timezone, session
calendar, and minute-level execution interpretation. Provider/license
retrieval is outside the requested local-data scope; raw input is not packaged.

Build the monthly quote-side table, figure, and profile-linked provenance from
that stable profile:

```bash
.venv-x86/bin/python scripts/research/analysis/market_data/plot_market_data_quality_profile.py \
  --profile evidence/research/releases/negative-evidence-readiness/local_market_data_quality.json \
  --csv-out evidence/research/releases/negative-evidence-readiness/local_monthly_tick_quote_quality.csv \
  --figure-out evidence/research/releases/negative-evidence-readiness/local_monthly_tick_quote_quality.png
```

The plotter writes new files only. Verify or preserve existing outputs before
rerunning; it refuses to overwrite the CSV, figure, or provenance JSON.

The completed all-row flag/quote-side pass is in
`tick_quote_side_flag_cross_tab.json`. It scanned 8,162,529,858 input bytes in
job 21343231 (2 CPUs, 8 GB requested, 13:58 elapsed); all 39 file hashes
matched and every tick row was accounted for. It is a local pattern audit, not
an authority for vendor flag semantics.

## Complete local data checksum inventory

The release checksum manifest covers every entry in the semantic local data
inventory at `/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/local_market_data_inventory.json`
and records both declared paths and resolved targets. Recheck the files from a
suitable CPU-node allocation:

```bash
.venv-x86/bin/python scripts/research/analysis/market_data/hash_local_data_inventory.py --check
```

The check rehashes each unique resolved target, confirms inventory sizes and
stable file metadata, and compares all entries with
[`RAW_DATA_SHA256_MANIFEST.json`](RAW_DATA_SHA256_MANIFEST.json). To create a
new manifest, `--write` is accepted only when the output path does not exist;
it never overwrites an existing evidence file. This records local byte
identity only and does not establish provider rights, timezone correctness,
or the authoritative session calendar. The final 140-path inventory check
completed in job 21347604 with zero file differences.

## Configured native and derived timeframe parity

The local-source audit reads both configured splits and compares every
configured native M3–D1 file with the same timeframe derived from its M1
source. It also reports the first configured M1 timestamp at or after each
higher-timeframe bar's availability. Run it in a suitable CPU-node allocation
through a named persistent login tmux session:

```bash
.venv-x86/bin/python scripts/research/analysis/market_data/compare_configured_timeframe_bars.py \
  --out evidence/research/releases/negative-evidence-readiness/configured_timeframe_parity.json
```

The report preserves source paths and hashes, separates timestamp/OHLCV parity
from native spread comparisons against M1 mean and last, and identifies
intentionally M1-derived views. It measures the first M1 at or after each
higher-timeframe close but does not classify observed gaps as missing market
bars because the authoritative instrument calendar remains unresolved.

## Real-market feature prefix invariance

This reusable feature-domain analysis groups registered variants by their
effective feature configuration, rebuilds each profile on the configured
training and exposed-report M1 inputs for both symbols, and compares full
features against prefixes at the chosen cutoffs. Its report includes source
hashes, configuration identities, feature counts, and individual comparisons.
On an ARM GH200 allocation, run four independent profile-group shards inside
that allocation, then merge only after all four exit successfully. Keep shard
outputs outside the repository until the merger accepts complete coverage:

```bash
OUT=/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/real-market-prefix-rerun
mkdir -p "$OUT"
pids=()
for i in 0 1 2 3; do
  .venv/bin/python scripts/research/analysis/features/verify_real_market_feature_prefix_invariance.py \
    --profile-inventory evidence/research/feature_causality/feature_configuration_inventory.json \
    --profile-group-shard "$i/4" --out "$OUT/shard_$i.json" \
    > "$OUT/shard_$i.log" 2>&1 &
  pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done
test "$status" -eq 0 || exit "$status"
.venv/bin/python scripts/research/analysis/features/merge_real_market_feature_prefix_shards.py \
  --shards "$OUT/shard_0.json" "$OUT/shard_1.json" "$OUT/shard_2.json" "$OUT/shard_3.json" \
  --out evidence/research/feature_causality/real_market_feature_prefix_invariance_all_profiles.json
```

Passing means only that later rows did not change the selected configured
features at the tested cutoffs. It does not establish source-event publication
times, an authoritative calendar, or behavior under untested configurations.

The earlier per-column/tie diagnostic and flag cross-tab were generated from
legacy source that is not fully recoverable. Do not describe those old reports
as reproducible from the current profiler. The current reusable profiler above
regenerates its own hash-linked file and period quality counts; it does not
infer sub-timestamp chronology. The selected fill-event alignment has its own
regeneration command in the [fill quote packet](../../../fill_quote_source_alignment/README.md).
Launch a full scan only inside a suitable CPU-node allocation from a named
persistent login tmux session; never create one `srun` per file or run it on
the login host.

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
  tests/unit/research/test_current_market_inputs.py -q
```

The three commands reported 12, 22, and 2 passed, respectively. The market
input audit tests now live at
`tests/unit/research/test_current_market_inputs.py`.

## Historical paired-trade row recomputation

```bash
.venv-x86/bin/python -m jupyter execute --timeout=120 --inplace \
  docs/reproduce/entry_and_exit_attribution.ipynb
```

This notebook recomputes the tracked paired-row analysis and writes the
versioned monthly figure into the semantic evidence packet. It does not replay
checkpoints or fills from raw ticks and does not upgrade the result to R3/R4.
Notebook outputs are stored in the notebook; use a disposable copy if you want
to preserve its current rendered state.

## Recovered train-only entry-action funnel

```bash
.venv-x86/bin/python scripts/research/analysis/evidence/analyze_entry_action_funnel.py
```

This report reads the recovered campaign manifest and each arm's training
`training_log.json` through the preserved `outputs/` symlink. It validates the
campaign fingerprint, seed, training-bar count, and internal funnel totals;
the exposed report split is not read. Rejections while unarmed and downstream
rejections are kept separate. The report diagnoses action-funnel attrition;
it does not explain economic losses or authorize a successor run.

The semantic entry/exit packet's source checksum contract is covered by:

```bash
.venv-x86/bin/python -m pytest tests/research/test_entry_and_exit_attribution_evidence.py -q
```

## Run observation and decision-trace inventory

```bash
.venv-x86/bin/python -m scripts.research.analysis.models.inspect_observation_action_artifacts \
  --root outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1 \
  --root outputs/gpu_experiment_runs/core_mtf_reasoning_seed42_train2025_2m_n8_20261031 \
  --output evidence/research/model_observation_and_action_semantics/run_artifact_shape_inventory.json
```

The command hashes recognized manifests/logs and explicitly named traces in
those roots. It does not load checkpoints. A missing trace means no matching
record was found in the named roots; it does not prove absence elsewhere.

## Release limitations

There is no regeneration command here for the scratch-only full historical replay,
because a frozen checkpoint replay was not run. Do not run training or inspect
an unregistered future period as a substitute for the open data and protocol
gates.
