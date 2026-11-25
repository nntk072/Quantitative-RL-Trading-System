# Blocker inventory (main-native, 2026-11-26)

Every package is blocked. Each entry names the cause and the authorization or resource it needs. Full detail is in work_package_ledger.json.

## Needs an owner decision
- SEMANTIC-ORACLE: candidate defects C1 (invalid fill direction maps to bid) and C2 (slippage_points not applied) in trading/execution/costs.py. Decide: fix the source or the docstring.
- PRODUCTION gate (LIVE-CONTRACT, PRODUCTION-CONTROL-PLANE, OPERABILITY): approval to start production work. Mock and paper mode only.
- FINAL-PRODUCT-APPLICATION: product gate approval.
- SCIENTIFIC-RELEASE: authorization and frozen design for any 20M campaign.
- RESOURCE-RUNTIME R2: per-worker RAM field in the request contract (experiment runner).

## Needs an allocation
- NATIVE-TOOLCHAIN: aarch64 wheel on a GH200 node (Slurm, one srun).
- BASELINE-AUDIT: feature and learning mutation tests, integration subset (8-CPU run).
- PERFORMANCE-BASELINE, LEARNER-OPTIMIZATION, FEATURE-KERNELS, SHARED-DATA-ABI, INTEGRATED-BENCHMARK: benchmark allocations (GPU for learner work).
- RESOURCE-RUNTIME online items O1 to O3: GH200 interactive allocation.

## Missing input data
- SEMANTIC-ORACLE, DATA-SCHEMAS: captured broker events are not in the tree. Not fabricated.
- DATA-SCHEMAS: full source CSVs cover 2026 and were excluded by decision; the reconciliation needs an approved pre-2026 window.

## Implementation not yet written (no external blocker)
- NATIVE-DOMAIN: property tests, differential traces, serialization, account and risk state.
- CAUSAL-FEATURE-GRAPH, DATA-INGESTION, DATA-QUERY, NATIVE-EXECUTION, NATIVE-DECISIONING, NATIVE-ENVIRONMENT, BATCHED-ENVIRONMENT, ROLLOUT-BUFFERS, EXECUTION-DAG, EXPERIMENT-CATALOG, ARTIFACT-STORE, RESULT-REGISTRY, EVALUATION-ENGINE, RESEARCH-STATISTICS, EVIDENCE-GENERATION, LEARNER-CONTRACT, ENGINE-REUSE-TRIAL, PERFORMANCE-POLICY, QUALITY-AND-SECURITY.
