# Local quality engineering

This opt-in infrastructure extends, but does not replace, the repository's
existing required gates. New measurements are advisory by default. It never
automatically runs training, uploads source or findings, promotes coverage
baselines, modifies the primary lock, or installs an optional analyzer.

Use the existing matched architecture Python environment. For example:

```bash
QRL_PYTHON=.venv-x86/bin/python ./tools/check local-quality doctor
./tools/check local-quality --help
./tools/check local-quality inventory
./tools/check local-quality repo-audit
./tools/check local-quality debt
./tools/check local-quality coverage --test tests/unit/decisioning
./tools/check local-quality --timeout 900 coverage --full --workers 4 --base main
./tools/check local-quality coverage-diff /path/to/coverage.json --base main
./tools/check local-quality baseline-candidate /path/to/full/manifest.json --ref main
./tools/check local-quality impacted /path/to/full/manifest.json --base main
./tools/check local-quality exclusions --base main
./tools/check local-quality static --profile fast
./tools/check local-quality static --profile deep
./tools/check local-quality static --profile security
./tools/check local-quality static --profile infrastructure
./tools/check local-quality --timeout 1800 coverity
./tools/check local-quality --timeout 1800 codeql
./tools/check local-quality import-findings codeql /path/to/results.sarif
./tools/check local-quality --timeout 600 mutation --scope risk --test tests/unit/trading
./tools/check local-quality properties --target risk --profile dev
./tools/check local-quality fuzz --target ticks --seconds 10
./tools/check local-quality semantic
./tools/check local-quality semantic --run --domain trading
./tools/check local-quality semantic --manifest /path/to/semantic/manifest.json
./tools/check local-quality product-parity frame-bundle
./tools/check local-quality product-parity ppo-math
./tools/check local-quality differential reference.json candidate.json --fields tolerances.json
./tools/check local-quality test-inventory --path tests/unit/decisioning
./tools/check local-quality test-shards --path tests/unit/decisioning --count 4 --workers 2
./tools/check local-quality native
./tools/check local-quality environment analyzers plan
./tools/check local-quality --timeout 1200 environment analyzers resolve
./tools/check local-quality --timeout 1200 environment analyzers sync
./tools/check local-quality environment cpu plan
./tools/check local-quality cache --profile gpu
./tools/check local-quality dashboard
./tools/check local-quality dashboard --parquet
./tools/check local-quality verify /path/to/manifest.json
```

The new command defaults to no package sync. Set QRL_PYTHON to a suitable
environment or use the existing uv environment. On Triton follow the canonical
resource and Slurm rules; do not run heavyweight checks on login nodes.

Policy: `policy.json` controls new actions (off/advisory/blocking). Existing
coverage floors and all required CI commands stay untouched. Exit 0 means
successful execution, advisory findings, disabled or not applicable; exit 1
means blocking findings; a scope-limited audit returns zero only in advisory
mode and retains its unassessed inventory. Exit 2 means incomplete, unavailable, invalid or
failed execution. Read the explicit manifest status. A timed-out analyzer is
not a clean scan. `--timeout` bounds each external process, not the sum.

Evidence: every command writes an isolated run directory under
`outputs/quality-local/`, with SHA-256 manifests, source/lock identity, raw logs,
JSON, SARIF where supported and test receipts. Keep raw reports local;
third-party analyzers may query external services. The dashboard renders
actual results, not zeros for missing metrics. Optional DuckDB/Parquet requires
the selected Python environment to have DuckDB. The analyzer venv may be
selected via QRL_ANALYZER_BIN for executable tools. Atheris needs to be
installed into a compatible product Python environment; do not silently mix
incompatible ABI/site-packages.

Coverage: selected tests never establish a complete product baseline. Full
collection combines raw coverage from the existing unit and integration
profiles, reconciles test inventories and per-phase receipts, and validates
executable product source inventory. Changed branch arcs are not MC/DC.
Baseline candidates require a clean complete measurement at an explicitly
trusted local Git ref; they never promote the baseline. Local hash integrity
is not remote authenticity. Impact selection combines historical test
contexts and static reverse imports. Dynamic imports, unknown paths, stale
evidence and shared fixtures require full validation. Impacted tests never
replace the required full gate. Exclusion changes require explicit review.

Static: Coverity needs a licensed installed kit (coverity, cov-analyze,
cov-format-errors, cov-manage-emit), and CodeQL needs an eligible installed
CLI and query packs. Neither adapter uploads or submits reports. Tool versions
and native report schemas differ; unsupported formats produce explicit
errors. Coverity capture lists are retained; check installed version and
language capabilities. Security tooling may need local vulnerability databases.
No credentials are stored. Domain Semgrep rules are review leads, not proof
of causal leakage or invalid finance.

Mutation: clean committed tree required. The adapter creates a detached
worktree inside ignored output storage; it never mutates the active checkout.
Configured scope reuses existing mutmut settings; named expanded scopes
require explicit test selectors. Raw stats and mutant details remain visible.
Timeouts and untested mutants are not kills. Remove retained worktrees
explicitly after reviewing evidence.

Scientific: the semantic registry covers the current product families and
actual test paths. Mapping does not mean execution. CPU fakes are not CUDA
hardware evidence. Native/GPU/ROCm and future-language checks activate only
on applicable components or explicit targets. Product parity uses the
existing authoritative frame/bundle, Gym/transition, backtest, rollout and
PPO math tests. Hypothesis and Atheris exercise independent product oracles
on bounded synthetic inputs. Expensive campaigns, historical debt remediation
and training benchmarks are outside this infrastructure campaign.

Dependencies: analyzer, CPU and GPU profiles resolve in ignored directories.
The GPU profile copies the original lock; the CPU profile switches to the
existing CPU index and checks accelerator and non-accelerator drift. Resolve
and sync are explicit network-capable operations; the primary runtime
environment and lock remain unchanged. Optional native tools require an
existing build configuration, actual instrumentation and local toolchain.

## Hosted advisory groups

Every push and pull-request opening, update or reopening runs the independent
groups in `.github/workflows/advisory-quality.yml`. Matrix fail-fast is disabled;
a failed group does not cancel other groups. The existing CI also runs a
separate advisory coverage job reusing the required coverage artifact instead
of repeating all tests. Neither advisory workflow nor the advisory coverage
job is a dependency of the required `ci-success` gate. Do not add these
advisory check names to required branch-protection rules.

Hosted groups: infrastructure, static analysis, technical debt, security,
scientific parity, property/fuzz, bounded mutation, native/environment,
Coverity and CodeQL. CodeQL runs on the hosted runner using the official
action without uploading to Code Scanning. Coverity is attempted only when
the licensed kit is installed; missing tools and unsupported hardware are
not successful analyses. Native/environment checks inventory and plan;
actual native/GPU tests require applicable targets and runners. Benchmark
comparison remains explicit because comparable benchmark evidence cannot be
invented on an ordinary CI runner.

Findings remain advisory. Tool or test execution failures are visible
separately from the existing mandatory CI. Fuzzing and mutation budgets are
bounded; a timed-out campaign is incomplete, not a pass. Push and PR events
both trigger runs, including when a push updates an open PR. Runs are not
cancelled on new commits. Public CI artifacts retain status-only summaries
for seven days; raw analyzer reports and captured source are not uploaded.
The consolidated advisory report includes per-check exit statuses, analyzer
skip counts, and mutation stage status. An incomplete scan preserves findings
from assessed inputs without implying that skipped inputs passed. The bounded
PR mutation campaign targets account-loss floor arithmetic; wider mutation
scopes are available through the local command. OSV updates its offline
vulnerability database in hosted CI and scans the authoritative uv lock.


The PyPI audit explicitly distinguishes the installed editable project and
the exact locked CUDA PyTorch wheel from PyPI-indexed dependencies. If the
PyPI service skips one of those exact locked versions, the tool reports
`scope_limited` and records the unassessed package and version. Any unknown
or mismatched skip remains incomplete. This is not evidence that the
non-PyPI wheel is vulnerability-free; OSV and Trivy provide complementary
checks, not a guarantee of complete vulnerability coverage.
