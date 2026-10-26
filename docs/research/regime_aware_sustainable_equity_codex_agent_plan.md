> **Execution note for this repository (2026-10-26):** This document preserves the attached research plan. Its embedded agent permissions and historical job/config details are proposals/context, not standalone authorization or current state. Follow the repository `AGENTS.md`, `.agents/rules/triton-slurm.md`, and the user's current instructions when they differ. The matched R0/R1 development screen and reports are complete. R2 compares the existing TCN sequence pathway with the same pathway plus a compact, separate, completed-D1 context branch while holding source-normalized D1 inputs constant. Continue with this minimal matched experiment and defer speculative extensions.

### Verified preflight finding from the completed 2M run

The saved DSR training replay contains 1,110 completed entry positions. Its
legacy `trend_regime` is `flat` on every entry because it is derived from the
same-day Asia/London premium-discount composite, not a slow daily trend state.
The new report at `docs/research/regime_attribution_20261026.md` joins these
outcomes to causal completed-D1 return and volatility states. It shows negative
mean net R on both long and short positions in the bull state, and positive
mean net R for bear-state shorts; this is descriptive evidence from one
in-sample seed, not proof that regime context caused the loss.

The saved manifest lists 74 features per timeframe, including D1, and a TCN
with `obs_window=60`. However, cached D1 technical momentum/trend channels
(`ret_5`, `ret_30`, EMA distances, ADX, and realized volatility) were missing
at all 1,110 accepted entries. D1 swing-distance features were present at
990–1,028 entries, so the model did receive some daily structural information.
Source inspection and a direct reproduction found the defect: D1 values were
forward-filled across M1 rows and then z-scored on M1; after 252 repeated rows
their rolling standard deviation becomes zero and normalized values become
missing. The observation builder then maps those missing inputs to zero.

The trade ledger also records open/reject action vectors. Entry-intent counts
and action summaries are in the report, but it does not record no-op or
in-position action vectors. After the account loss floor was reached on
November 13, December has no opens; that is environment risk gating, not
evidence that PPO learned an always-flat policy.

The minimum justified treatment is now a separately configurable D1-only
technical normalization path: normalize completed D1 features on their source
index with train-only statistics, then causally align them to M1 and exclude
them from the second M1-level normalization. Keep the existing TCN, PPO,
actions, risk policy, data, and training settings matched. The implementation
is opt-in so the historical baseline remains available. Do not add another
indicator family or encoder unless this matched test justifies it. Available
input begins 2024-12-30, so early EMA200 values must remain explicit warmup
missing values rather than being treated as valid history.

---

# Codex Autonomous Agent Plan
## Regime-Aware Sustainable Equity PPO

### Target execution environment

You are running as an autonomous coding/research agent inside Codex with:

- full access to the repository;
- shell access;
- access to existing training outputs and evidence artifacts;
- access to the Python environment;
- access to GPU nodes / GH200 resources where available;
- access to Slurm and existing allocations/jobs;
- ability to run tests, analysis scripts, short training jobs, evaluation, profiling, and static checks;
- ability to modify repository code;
- ability to create experiment configurations and research artifacts;
- ability to commit completed work.

Repository:

`nntk072/Quantitative-RL-Trading-System`

Reference commit containing the current sustainable-growth work:

`906e1ab49839c24ddc428fa3f7223af4dcdaee09`

Do not assume this commit is still HEAD. Inspect the actual repository state first.

---

# 1. Mission

Find and address the most likely cause of the observed failure pattern:

> PPO performs well during some market conditions, especially earlier favorable regimes, but its realized trade expectancy deteriorates after higher-timeframe market behavior changes, causing equity to decline and sometimes reach the account-loss floor.

The primary hypothesis to test is:

> The existing PPO policy does not receive an adequate causal representation of slow market regime, so the statistical quality of its intraday decisions changes faster than the policy can recognize and adapt.

The secondary hypothesis is:

> The RL credit-assignment horizon is substantially shorter than the multi-session / multi-week equity behavior that the research is trying to optimize.

Do not assume either hypothesis is correct.

Investigate them empirically.

The intended outcome is not:

- more trades;
- higher training reward;
- one profitable quarter;
- a policy that stops trading permanently after earning money.

The desired outcome is:

> Better after-cost equity behavior across changing market regimes while respecting existing hard account-risk limits.

---

# 2. Operate autonomously

Do not ask the user for implementation details already discoverable from the repository.

Inspect the code, configs, tests, historical evidence, current git state, active Slurm state, and experiment artifacts yourself.

Make reasonable implementation decisions consistent with existing architecture.

Prefer:

- minimal changes;
- existing abstractions;
- repository conventions;
- matched experiments;
- reproducible artifacts.

Avoid speculative rewrites.

If an implementation detail differs from assumptions in this plan, follow the authoritative current repository behavior and document the discrepancy.

---

# 3. Preserve active work

Before modifying or launching anything:

Inspect:

```text
git status
git log
current branch
current HEAD
Slurm queue
active allocations
running workers
queued dependencies
tmux/supervisor state where relevant
```

The latest handoff reported:

```text
DSR benchmark job: 21206400
dependency/allocation: 21204379
```

but treat that as historical context.

Determine current state directly.

Do not:

- cancel active jobs;
- submit duplicate jobs;
- overwrite active campaign outputs;
- delete historical evidence;
- reset unrelated repository changes;
- reuse an incompatible checkpoint;
- alter campaign provenance after execution.

If an existing GPU allocation is safely reusable, reuse it instead of requesting unnecessary resources.

---

# 4. Read the current research handoff first

At minimum inspect:

```text
docs/research/sustainable_equity_growth_status_20261026.md
docs/research/sustainable_equity_growth_execution_plan.md
docs/research/sustainable_equity_growth.md
docs/thesis/manuscript_draft.md
```

Also inspect existing evidence concerning:

```text
P6 monthly dynamics
P6 entry/exit decomposition
fixed-entry exit shadow
MTF experiments
training coverage
full-split episode behavior
risk-floor discrepancy
DSR/log-growth screen
EOD peak drawdown experiments
```

Do not reconstruct conclusions already established by those artifacts unless verification is needed.

---

# 5. Known evidence to preserve

Treat the following as established development evidence unless current artifacts contradict it.

## Historical coverage problem

An earlier 2M run using 64 vector environments had approximately:

```text
31,360 training steps/environment
```

while a full 2025 chronological traversal required roughly:

```text
99,492 steps/environment
```

so actual learning only reached approximately late April 2025.

This created a major chronology confound.

Future experiments must automatically verify per-environment chronological coverage.

---

## Reward-only intervention failed

Existing matched 2M seed-50 screen:

```text
DSR PPO:
2025 return ≈ -10.15%
PF ≈ 0.965

Log-growth PPO:
2025 return ≈ -10.18%
PF ≈ 0.962
```

Both failed survival.

Therefore do not assume reward replacement alone solves the problem.

---

## Failure is not simply a short bias

Existing P6 trade evidence indicates that the hidden-state policy had approximately:

```text
long:
mean net R ≈ -0.070

short:
mean net R ≈ +0.041
```

Long trades themselves became poor in several later rising-market months.

Therefore:

> "Market went up while PPO kept shorting"

is insufficient as a causal explanation.

---

## Exit-only explanation is weak

The fixed-entry exit shadow produced approximately:

```text
mean structural-minus-EMA delta ≈ +0.007R
```

with uncertainty spanning zero.

Do not make exit redesign the primary intervention.

---

# 6. Inspect the actual observation horizon

Audit the effective observation seen by the current sustainable-growth variants.

Verify directly:

- architecture;
- M1 sequence length;
- whether the M1 sequence is session-clipped;
- which higher-timeframe columns are included;
- whether HTF values are repeated snapshots or independent temporal streams;
- actual encoder windows;
- actual feature schema;
- whether D1 is the largest supported explicit timeframe.

Current expected behavior is approximately:

```text
TCN:
60 M1 observations
current-session sequence

MTF:
M3 20
M5 24
M10 12
M15 16
M30 8
H1 12
H4 6
D1 5
```

Confirm from current source.

Generate a compact machine-readable audit.

---

# 7. Phase 1 — Diagnose regime dependence from existing artifacts

Do this before new RL training.

Use the existing 2025 trade/action/equity ledgers wherever possible.

Do not burn GPU hours to rediscover information already available in saved artifacts.

Implement a reusable causal regime-analysis package consistent with repository architecture.

Suggested location:

```text
analysis/regime/
```

or the nearest existing analysis package.

Avoid embedding all reusable logic in one research script.

---

# 8. Implement causal slow-regime features

Create a compact, continuous, causal slow-market state using completed higher-timeframe information.

Use D1 as the primary source.

Initial feature family should include approximately:

### Returns

```text
5-day log return
20-day log return
60-day log return
120-day log return
```

### Trend structure

```text
distance to EMA21
distance to EMA50
distance to EMA200

EMA21 slope
EMA50 slope
EMA200 slope

EMA50 minus EMA200 normalized spread
```

### Trend strength

```text
ADX14
+DI minus -DI
```

### Volatility

```text
20-day realized volatility
60-day realized volatility
```

### Slow range state

```text
drawdown from 63-day rolling high
63-day range position
```

Keep the first implementation compact.

Target roughly:

```text
12-18 regime features
```

Do not generate hundreds of redundant indicators.

Prefer dimensionless or normalized quantities.

---

# 9. Causality is a hard gate

Slow features must use only data available before the M1 decision.

At time `t`:

- current unfinished D1 candle must not leak;
- future D1 bars must not leak;
- future H4 bars must not leak;
- train/test normalization must not leak;
- rolling thresholds must be causal.

Implement direct mutation tests.

Example invariant:

```text
observation(t, original future data)
==
observation(t, arbitrarily modified future data)
```

for data unavailable at `t`.

If this fails:

Stop further RL work and fix it.

---

# 10. Audit warmup/prehistory

Determine how much historical data is available before the first tradable 2025 observation.

Explicitly determine whether valid history exists for:

```text
5 days
20 days
60 days
120 days
EMA200
63-day range
```

Do not silently replace missing history with apparently valid zeros.

Use either:

- valid pre-training warmup history; or
- explicit feature validity masks.

Record the warmup contract in the manifest.

---

# 11. Create diagnostic regime labels

These are for analysis, not necessarily direct policy input.

Use simple deterministic labels.

For example:

```text
bull:
ret20 > 0 and ret60 > 0

bear:
ret20 < 0 and ret60 < 0

mixed:
otherwise
```

Also classify:

```text
trend strength
volatility state
```

Thresholds must be causal and training-derived.

Do not tune them on 2026.

---

# 12. Attribute historical policy behavior by regime

Join each existing 2025 trade to the regime state at its decision timestamp.

For every relevant policy compute:

```text
trade count
mean net R
median net R
net PnL
gross PnL/R
cost drag
win rate
profit factor
requested risk
approved risk
```

Break down by:

```text
regime
side
month
trend state
volatility state
```

At minimum report:

```text
bull-long
bull-short
bear-long
bear-short
mixed-long
mixed-short
```

with sample size.

---

# 13. Attribute policy actions by regime

Where action logs allow, compare:

```text
direction
intensity
risk
SL selection
TP selection
SL mode
TP mode
exit mode
entry acceptance
entry rejection
```

across regime states.

The key diagnostic question is:

> Does policy behavior meaningfully change when the slow market regime changes?

Interpretation:

### Actions barely change, expectancy changes

Likely representation/conditioning problem.

### Actions change but expectancy remains poor

Likely opportunity generation / trade geometry / structural edge problem.

### Risk and selectivity adapt and expectancy improves

Evidence that regime conditioning may be useful.

---

# 14. Produce a diagnosis artifact before model changes

Create:

```text
docs/research/regime_attribution_20261026.md
```

plus machine-readable outputs.

The report must explicitly answer:

1. Is post-Q1 deterioration concentrated in specific regimes?
2. Are long trades or short trades responsible?
3. Does the policy alter direction with regime?
4. Does it alter risk with regime?
5. Does entry acceptance change?
6. Does cost drag explain the deterioration?
7. Does trade geometry explain more than direction?
8. Is there sufficient evidence to justify a slow-regime observation?

Do not train before this report exists unless an existing running campaign must be allowed to finish independently.

The existing R0/R1 artifacts answer this gate descriptively. R1 has large
trend-by-side expectancy differences, but the saved entry direction mix shifts
only modestly across regimes and omits no-op and in-position decisions. The
report supports a falsifiable representation screen, not a claim that regime
conditioning is the established cause of losses.

## Current implementation handoff

The first `tcn_regime` implementation uses seven already-built D1 channels:
5- and 30-day returns, 21/50/200 EMA distances, ADX, and realized volatility.
It reads the last completed D1 values already causally aligned to each M1 row,
preserves per-coordinate warmup masks, and requires source-index train-only D1
normalization. It fuses this small independent vector through a 16-unit MLP
with the existing TCN and account branch. The existing TCN, action schema,
execution, and risk behavior remain unchanged. The matched R2 screen pairs this
against the same source-normalized TCN control; it is prepared in
`config/campaigns/regime_tcn_context_r2_seed50_train2025_2m.yaml` and may run
only after correctness and quality gates pass and suitable allocation time is
available.

---

# 15. Phase 2 — Implement a compact slow-regime observation

If the attribution does not disprove the regime hypothesis, add an opt-in observation branch.

Conceptually:

```text
{
    seq,
    seq_mask,
    account,
    regime,
    regime_mask
}
```

Do not append the same slow vector to all 60 M1 rows.

Treat it as an independent context channel.

Existing observation behavior must remain unchanged when disabled.

---

# 16. Version the observation lineage

Introduce an explicit observation/schema lineage for the regime-aware model.

Record:

```text
schema version
regime feature version
regime feature order
feature hash
validity-mask semantics
normalization semantics
```

Checkpoint mismatch must fail loudly.

No silent feature-order adaptation.

---

# 17. Implement a new encoder, not a hidden modification

Create a new architecture:

```text
tcn_regime
```

Do not change the semantics of:

```text
tcn
mtf
gru
transformer
lite_tcn
```

Suggested architecture:

```text
M1 sequence
    ↓
existing causal TCN
    ↓
128-d latent
                    \
slow regime vector → small MLP → 16-32d latent
                      \
account state → existing AccountMLP
                         \
                          concat/fuse
                              ↓
                         PPO heads
```

Keep the regime network small.

No transformer is needed.

---

# 18. Preserve the action contract

The first regime experiment must not change:

```text
direction action
intensity
stop selection
risk action
TP selections
SL mode
TP mode
simplex fractions
exit action
entry FSM
risk limits
tick execution
cost model
```

Only representation should change.

---

# 19. Register architecture cleanly

Update the authoritative paths discovered in the repository.

Likely areas include:

```text
models/encoders/
learning/rl/agent.py
simulation/environment/
training/configuration/
evaluation/reporting/
config/
tests/
```

Do not edit files solely because this plan names them.

Use current package ownership.

---

# 20. Add full tests before GPU training

Required categories:

### Regime feature tests

- rising market;
- falling market;
- flat market;
- range position;
- drawdown;
- volatility;
- missing history;
- validity mask;
- finite output.

### Causality tests

- mutate future D1;
- mutate unfinished D1;
- mutate future session;
- mutate future H4;
- confirm old observation unchanged.

### Observation tests

- correct regime shape;
- correct dtype;
- baseline unchanged when disabled;
- observation-space/runtime parity.

### Encoder tests

- forward shape;
- gradients;
- regime branch affects latent;
- eval determinism;
- old TCN unchanged.

### Checkpoint tests

- old TCN checkpoint compatibility;
- regime checkpoint compatibility;
- mismatch fails loudly.

### Coverage tests

- per-env budget calculation;
- incomplete chronological coverage detected;
- completed full-split recognized.

Target robust behavioral tests, not merely branch coverage.

---

# 21. Phase 3 — Correct EOD peak-drawdown semantics/reporting

Audit current code around:

```text
_peak_eod_dd_locked
```

Current behavior appears to be:

```text
drawdown reaches threshold
→ close position
→ block entries
→ unlock only if equity exceeds previous peak
```

If no trading occurs while blocked, equity cannot normally recover to the previous peak.

Therefore treat this as effectively:

```text
capital stop for the remainder of the episode
```

unless the current implementation proves otherwise.

Do not silently rewrite historical runs.

Rename or report the semantics accurately.

Suggested conceptual label:

```text
peak_eod_capital_stop
```

Report:

```text
triggered
trigger timestamp
peak equity
equity at trigger
drawdown at trigger
number of remaining sessions
number of trades after trigger
```

If behavior is intentionally permanent, encode it explicitly rather than relying on impossible recovery logic.

If a recoverable controller is desired, that is a separate future experiment.

---

# 22. Do not reinterpret historical +28.57% as learned adaptation

Preserve the historical result.

But clearly distinguish:

```text
PPO trading policy
+
capital-preservation overlay
```

from:

```text
PPO learned regime adaptation
```

The overlay may still be useful.

It simply answers a different research question.

---

# 23. Phase 4 — Define a clean matched representation experiment

Create:

## R0

```text
regime_r0_ppo_dsr_tcn
```

Configuration:

```text
PPO
TCN
DSR
gamma=0.99
same action contract
same risk contract
same execution
same data
same seed
same n_envs
```

## R1

```text
regime_r1_ppo_dsr_tcn_regime
```

Identical to R0 except:

```text
tcn_regime
regime context enabled
```

No other intended difference.

Generate resolved configuration diffs automatically.

Fail the experiment definition if unexpected differences exist.

---

# 24. GPU pilot authorization

You have GPU access.

Use it intelligently.

You may run:

- feature generation;
- encoder smoke tests;
- GPU forward/backward tests;
- environment throughput profiling;
- small PPO smoke tests;
- short bounded diagnostic pilots.

Do not immediately launch a new 20M campaign.

A reasonable progression is:

```text
5k-20k steps:
plumbing smoke

100k-250k:
policy-learning sanity check if needed

2M:
matched development screen after all gates pass
```

Do not treat a smoke run as research evidence.

---

# 25. Training coverage must be automatically proven

For every actual RL run report:

```text
aggregate timesteps
effective n_envs
steps/environment
required steps/full split
completed full-split episodes
latest chronological training timestamp
```

The run must explicitly emit:

```text
COVERAGE_PASS
```

or:

```text
COVERAGE_FAIL
```

Never again infer full-year exposure from aggregate PPO timesteps.

---

# 26. Use approximately 8 environments for the 2M screen

The current sustainable-growth design uses approximately:

```text
n_envs=8
```

which should provide enough per-environment steps to traverse the full 2025 interval more than once.

Do not assume it survives hardware-aware resolution.

Verify:

```text
requested_n_envs
effective_n_envs
```

from the resolved runtime.

If the framework silently scales it upward enough to destroy chronological coverage, correct the experiment configuration before training.

---

# 27. 2M representation screen

Once implementation and gates pass, and no conflicting active campaign exists, run:

```text
R0
R1
seed 50
2M aggregate steps each
```

Use matched training/evaluation action semantics.

Preserve:

```text
2025 = development/training analysis
2026 = previously inspected report-only
```

Do not use 2026 for selection.

---

# 28. Evaluate more than total return

For R0 and R1 report:

### Overall

```text
net return
net PnL
log growth
max drawdown
hard-floor survival
Sharpe
Sortino
Calmar
PF
win rate
trades
mean net R
cost drag
```

### Monthly

```text
trades
mean R
PnL
PF
long expectancy
short expectancy
risk
```

### Regime

```text
trade count
long/short expectancy
risk
entry acceptance
direction distribution
PF
PnL
```

### PPO diagnostics

```text
entropy
action std
KL
explained variance
value loss
reward statistics
```

---

# 29. Representation decision gate

R1 does not need to be globally profitable to provide information, but do not advance it merely because one metric improves.

Strong evidence to advance:

```text
full-period survival improves
post-Q1 expectancy materially improves
PF improves
drawdown improves
bad-regime risk/selectivity improves
policy behavior demonstrably conditions on regime
```

Ideal development result:

```text
net return > 0
post-Q1 mean R > 0
PF > 1
hard-floor survival
```

A flat policy is not success.

---

# 30. Phase 5 — Objective-horizon experiment only after representation

Do not modify gamma during R0/R1.

After representation is understood, audit the PPO horizon.

Current:

```text
gamma=0.99
```

At approximately one NY session:

```text
0.99^390 ≈ 0.02
```

so the economic objective is extremely short relative to multi-week equity behavior.

Also inspect:

```text
GAE lambda
DSR eta
```

and derive their effective horizons.

Document the mismatch quantitatively.

---

# 31. Longer-horizon PPO must be a separate experiment

Do not silently edit baseline PPO defaults.

Use the best representation from the previous stage.

Example later comparison:

```text
H0:
gamma=.99

H1:
gamma≈.9996
```

where the treatment is chosen from an explicitly stated desired reward half-life.

Audit:

```text
gamma
lambda
gamma*lambda
advantage scale
value stability
gradient stability
```

Do not change gamma and lambda simultaneously while calling it a gamma-only experiment.

---

# 32. Reward comparison comes after representation

If the regime-aware model is viable, compare:

```text
TCN-Regime + DSR
vs
TCN-Regime + log-equity growth
```

This isolates reward design under an adequate state representation.

Do not assume log growth should win.

---

# 33. Constrained PPO comes later

Only test Q5 / Lagrangian PPO after there is evidence of non-negative trading edge.

Risk constraints can:

```text
reduce exposure
reduce drawdown
reduce breach probability empirically
```

but cannot create alpha from negative-expectancy entries.

Do not use Q5 to conceal a bad base policy.

---

# 34. SAC is deferred

Do not implement or launch the SAC comparison in this mission unless all earlier gates are complete and there is strong evidence that algorithm choice remains unresolved.

The causal sequence is:

```text
diagnose
↓
representation
↓
reward
↓
horizon
↓
risk constraint
↓
algorithm
```

not:

```text
change everything
```

---

# 35. Do not implement these now

Unless current evidence unexpectedly requires them, defer:

```text
HMM policy
Mixture-of-Experts
W1 neural encoder
MN1 neural encoder
Recurrent PPO
SAC
CPO
CVaR critic
distributional RL
Transformer regime model
online continual learning
meta-learning
```

The current minimum useful intervention is:

```text
existing PPO
+
existing fast TCN state
+
compact causal slow-regime state
```

---

# 36. Historical-data audit

Since you have access to the entire repository/data environment, inspect what US100 history is actually available locally.

Report:

```text
earliest date
latest date
full years
bar availability
bid/ask availability
tick availability
major gaps
```

Do not download new proprietary data unless the repository workflow explicitly supports it and the task requires it.

If multiple historical years already exist, prepare a future multi-regime walk-forward design.

Do not change the current 2025 experiment contract merely because more data exists.

---

# 37. 2026 remains locked

Maintain:

```text
locked_oos_role: final_report_only
locked_oos_exposure: previously_inspected_holdout
selection_allowed: false
```

Never choose:

```text
features
architecture
gamma
reward
risk threshold
regime threshold
```

because it improves 2026.

---

# 38. Static and test gates

Before committing implementation:

Run the repository's authoritative equivalents of:

```text
Ruff format check
Ruff lint
Mypy
focused tests
```

Use the existing environment and project commands rather than inventing an unrelated toolchain.

Then run broader tests as resources allow.

The previous gate had:

```text
Mypy: 763 files
focused tests: 169 passed
warnings: 9
```

The new implementation should not regress this baseline.

Run full pytest if practical.

If not run, explicitly say so.

---

# 39. GPU validation gate

Before a 2M experiment, perform a bounded GPU smoke test.

Verify:

```text
model constructs
CUDA path works
forward pass works
backward pass works
rollout collection works
reward finite
value loss finite
policy loss finite
no NaNs
checkpoint saves
checkpoint reloads
evaluation loads correct schema
```

A 2M run should never be the first test of a new model architecture.

---

# 40. Commit strategy

Make logical commits.

Recommended sequence:

```text
1. Add causal slow-regime analytics/features
2. Add regime observation and TCN-Regime encoder
3. Add provenance/tests/coverage gate
4. Correct EOD capital-stop semantics/reporting
5. Add R0/R1 experiment configs and documentation
```

Exact grouping may differ if repository conventions favor fewer commits.

Do not mix unrelated repository cleanup into these commits.

---

# 41. Required final implementation artifacts

At minimum produce:

```text
docs/research/regime_attribution_20261026.md
docs/research/regime_aware_sustainable_equity_plan.md
docs/research/regime_aware_sustainable_equity_status.md
```

and appropriate machine-readable analysis outputs.

Also create tracked experiment configurations for R0/R1.

Generated GPU campaign outputs may remain ignored if that matches repository convention.

---

# 42. Final handoff report

At the end report:

```text
current HEAD
commits created
files changed
static-check results
focused-test results
full pytest status
GPU smoke result
regime attribution findings
causality validation
baseline parity
observation schema
coverage gate behavior
EOD semantic conclusion
R0/R1 resolved-config diff
training jobs launched, if any
training jobs completed, if any
actual metrics, if available
remaining blockers
recommended next action
```

Do not fabricate or estimate missing experimental results.

---

# 43. Decision autonomy

You do not need user approval for:

```text
reading repository files
analyzing existing artifacts
implementing the planned feature/model changes
writing tests
running static checks
running focused tests
using a free existing GPU allocation safely
running small smoke/diagnostic jobs
fixing demonstrated implementation defects within scope
creating experiment configs
committing completed implementation
```

Do not launch an expensive full 20M multi-seed campaign merely because GPU resources are available.

A 2M matched development screen is allowed only after implementation gates pass and only if it does not interfere with an already active/queued research campaign.

If scheduling state makes immediate execution unsafe, finish all implementation/configuration/reporting work and leave the run ready to launch rather than duplicating resources.

---

# 44. Stop only for real blockers

Do not stop merely because:

```text
one test initially fails
a type error appears
a config needs updating
an implementation assumption was slightly wrong
a short GPU smoke reveals a normal bug
```

Fix those autonomously.

Stop expansion and document the blocker if:

```text
future-data leakage cannot be removed without redesign
required historical inputs do not exist
matched experiment parity cannot be established
baseline checkpoint compatibility is broken
runtime risk semantics contradict recorded experiment claims
active infrastructure makes launching another experiment unsafe
data provenance cannot be established
```

Partial completion is preferable to speculative implementation.

---

# 45. Scientific success criteria

The mission is successful at the engineering level when:

1. A causal slow-regime representation exists.
2. Existing baseline behavior remains available unchanged.
3. Regime attribution can describe where expectancy changes; it does not by itself establish a causal explanation.
4. PPO decisions can be analyzed by market regime.
5. `tcn_regime` is implemented and tested.
6. Training chronology is automatically validated.
7. EOD capital-stop semantics are scientifically accurate.
8. R0/R1 are isolated matched experiments (completed and reported).
9. R2 compares the regular TCN pathway with and without the additional D1 context branch under matched settings.
10. The implementation passes repository quality gates.
11. The research can proceed without changing multiple factors simultaneously.

R0/R1 did not show that source normalization alone repairs sustainable performance. The separate representation hypothesis remains untested until R2 reports matched training and report-only evaluation results.

A negative result is acceptable.

---

# 46. Immediate execution order

Execute autonomously in this order:

```text
1. Verify the current branch, working tree, live allocations, and worker topology.
2. Keep completed R0/R1 artifacts and reports as the evidence baseline.
3. Preserve the existing TCN and keep `tcn_regime` optional.
4. Verify causal completed-D1 values, per-feature masks, source-index train-only normalization, and checkpoint schema compatibility.
5. Resolve and compare the R2 control/treatment configurations before launch.
6. Pass full-tree Ruff format, Ruff lint, Mypy, and focused environment/model/feature/config tests.
7. Commit the tested implementation so the campaign has a stable source identity.
8. After the current allocation ends, reuse or request one suitable GH200 allocation within the repository GPU-hour limit.
9. Run the matched 2M R2 development screen once; preserve its fingerprints, logs, checkpoints, and report artifacts.
10. Generate matched training/report-only results with monthly, regime, action, risk, exit, and equity diagnostics.
11. Update the research status with observed results and limitations.
12. Interpret R2 before considering another representation, reward, gamma, Q5, SAC, or broader robustness experiment.
```

---

# Final goal

Do not try to make PPO predict the next bull or bear market from calendar position.

Build a policy that has:

```text
fast intraday state
+
slow causal market state
+
account/risk state
```

so that it can learn:

> The same intraday setup can have different expected value depending on the larger market regime, and therefore direction, selectivity, and risk should change accordingly.

The next scientific question is:

> **Does a separate completed-D1 context branch improve on a TCN that already receives the same source-normalized D1 channels, under otherwise matched PPO training?**

Answer that question rigorously before adding more complex RL algorithms.
