# Agent Goal: Thesis-Conditioned Multi-Timeframe Reasoning and Decision Architecture

## Repository / Baseline

- Repository: `nntk072/Quantitative-RL-Trading-System`
- Branch: `main`
- Plan against commit: `c15dbde9ef4ae37f4542819988ebe67ed262cfd1`
- Baseline commit message: `Separate timeframe entry idea contexts`
- Preserve the untracked `experiment_run_worker_dispatch.log`; do not add, delete, truncate, rename, or commit it.
- Before making changes, read the repository's `AGENTS.md`, relevant `.agents/domain_maps/*`, and local status. Repository instructions override this plan where they are stricter.
- Do not rewrite unrelated code, do not clean unrelated worktree state, and do not opportunistically refactor modules outside the edit radius.

---

# 1. Mission

Implement a first-class **trade-thesis architecture** so a PPO agent can reason jointly across multiple timeframes while each opened trade has one explicit structural owner.

The key problem is not lack of multi-timeframe data. The repository already exposes separate idea signals across M1, M3, M5, M10, M15, M30, H1, H4, and D1, and it already has an MTF encoder with one causal TCN branch per timeframe.

The problem is that the current decision is still essentially:

```text
all timeframe observations
        ↓
one fused policy state
        ↓
direction + risk + SL/TP/management
        ↓
after the decision, inspect all currently active ideas
        ↓
infer what the trade may have meant
```

That causes semantic leakage between timeframes. For example, an M5 setup can coexist with M1 confirmation and H1 context, but the engine currently does not know which of those actually owns the trade. The current stop-timeframe floor is inferred from the highest timeframe among active ideas instead of from a setup/timeframe explicitly chosen by the policy.

The target architecture is:

```text
causal MTF observations
        ↓
cross-timeframe reasoning
        ↓
valid thesis candidates
        ↓
policy selects ONE primary thesis:
    (idea, setup timeframe, direction)
        ↓
risk / stop / TP / management decision
        ↓
order geometry conditioned on selected thesis
        ↓
auditable trade record:
    primary thesis
    supporting MTF evidence
    structural invalidation
    targets
```

A trade may use many timeframes for reasoning, but **exactly one primary idea/timeframe pair owns structural invalidation semantics**.

---

# 2. Core Design Decision

## 2.1 Primary thesis anchor

Define the primary thesis as:

```text
PrimaryThesis = (idea, setup_timeframe, direction)
```

where:

```text
idea ∈ {
    po3,
    order_block,
    standard_deviation,
    fvg_retest,
    ifvg_retest,
    ifvg_unretested
}

setup_timeframe ∈ {
    M1, M3, M5, M10, M15, M30, H1, H4, D1
}

direction ∈ {LONG, SHORT}
```

The primary thesis is **not** the same thing as an execution timeframe.

The simulator may continue making decisions/fills from its M1 decision spine. If the selected thesis is `FVG_RETEST@M5 LONG`, an M1 confirmation can support the decision without redefining the trade as an M1 trade.

Example:

```text
H1   bullish order block          → higher-timeframe context
M15  bullish PO3                  → higher-timeframe confluence
M5   bullish FVG retest           → PRIMARY THESIS / structure owner
M3   bullish IFVG                 → lower-timeframe confirmation
M1   bullish reaction             → execution timing context

Selected primary thesis:
    FVG_RETEST@M5 LONG
```

The stop floor is therefore M5, not H1 and not M1.

## 2.2 Structural ownership rule

The default invariant for normal structural ideas is:

```text
SL reference timeframe >= selected setup timeframe
TP reference timeframe >= selected setup timeframe
```

Higher-timeframe context must not automatically raise the floor.

Lower-timeframe context must not lower the floor.

Idea-specific rules override the generic rule only when already required by the strategy semantics.

For Standard Deviation:

```text
primary = STANDARD_DEVIATION@M15 LONG
→ allowed structural stop is the selected M15 SD level-1 origin
```

Do not use level 1 from every simultaneously active SD timeframe.

## 2.3 Supporting context is not another action explosion

Do **not** require the policy to explicitly select every timeframe it used.

The first implementation should explicitly select only the **primary thesis**.

All other active timeframe evidence remains available to the neural encoder and is recorded as supporting/conflicting context for diagnostics.

This avoids a combinatorial action such as:

```text
primary setup × trigger × context1 × context2 × context3 × ...
```

while still allowing genuine multi-timeframe reasoning.

A future conditional trigger head may be added only if diagnostics show that an explicit trigger identity is necessary. It is not part of the initial required implementation.

---

# 3. Verified Baseline That Must Be Reused

At `c15dbde`, inspect and preserve the useful work already present.

## 3.1 Per-timeframe ideas already exist

`features/context/entry_ideas.py` now builds separate per-timeframe signals for:

- PO3
- order block reaction
- standard-deviation / Fib-like retracement
- FVG retest
- IFVG retest
- IFVG unretested

Do not replace this detector layer.

Use it as the source of thesis eligibility.

## 3.2 Current semantic bug

`entry_idea_context()` currently collects all active ideas/timeframes and derives:

```text
stop_timeframe_floor = highest timeframe among all active ideas
```

This is useful as legacy reporting but is not a valid primary-thesis rule.

Do not delete the legacy path immediately because old checkpoints/configurations may depend on it.

New thesis-enabled mode must stop using this inferred highest-active-timeframe floor for entry geometry.

## 3.3 Current action schema is flat

`decisioning/actions.py` currently defines the strategy overlay around coordinates such as:

```text
direction
intensity
stop
risk
tp1_sel
tp2_sel
tp3_sel
sl_mode
tp_mode
z1
z2
exit
```

Do not silently reinterpret an existing action schema.

Introduce a versioned thesis-action schema/mode.

Old checkpoints must remain loadable under their existing schema.

## 3.4 Current MTF encoder is a good foundation

`models/encoders/mtf.py` already contains:

- one causal `_CausalTCN` per configured timeframe;
- visibility masks;
- closed-candle MTF observation streams;
- fusion into one latent.

Reuse `_CausalTCN` and the existing observation construction.

Do not create nine new data pipelines.

## 3.5 Existing hybrid categorical/Gaussian PPO machinery exists

`learning/rl/hybrid.py` already supports categorical semantic coordinates for:

- `sl_mode`
- `tp_mode`
- `exit`

while retaining Gaussian coordinates for the continuous remainder.

Reuse and generalize this machinery.

Do not build an unrelated RL stack unless the existing SB3 extension proves structurally incapable of supporting the required masked thesis category.

## 3.6 Existing semantic action heads exist

`learning/rl/semantic.py` already groups action coordinates into semantic families.

Reuse concepts and tests from this module where useful.

Do not duplicate the same head abstractions with different names unless the thesis-conditioned policy requires a genuinely different contract.

---

# 4. Required Architecture

## 4.1 Static thesis candidate catalog

Create a stable catalog containing:

```text
NO_TRADE
+
6 ideas × 9 timeframes × 2 directions
```

Total:

```text
1 + 6 × 9 × 2 = 109 categories
```

The IDs must be deterministic and versioned.

Suggested stable ordering:

```text
0 = NO_TRADE

then:
direction order: LONG, SHORT
idea order: exactly ENTRY_IDEA_NAMES order
timeframe order: M1, M3, M5, M10, M15, M30, H1, H4, D1
```

Alternatively choose idea → timeframe → direction, but once implemented, freeze it and test the exact mapping.

Do not derive category identity from dictionary iteration.

Suggested schema identifier:

```text
thesis-candidate-v1
```

Each candidate must be self-describing:

```python
@dataclass(frozen=True)
class ThesisCandidate:
    candidate_id: int
    idea: str
    setup_timeframe: str
    direction: int
```

`NO_TRADE` may use a separate sentinel type or nullable fields, but its serialized meaning must be explicit.

## 4.2 Dynamic eligibility mask

At each decision row, build:

```text
thesis_mask: shape (109,)
```

Rules:

- `NO_TRADE` is always valid.
- A trade candidate is valid only when the exact per-timeframe idea signal exists for its direction.
- Do not infer eligibility from pooled idea flags.
- Do not promote an M1 idea into an M5 candidate.
- Do not merge FVG retest and IFVG retest.
- Do not treat IFVG unretested as IFVG retest.
- Respect causal visibility: the candidate may exist only after the source timeframe event is actually available to the M1 decision row.

The mask is part of the policy observation contract.

The environment must still validate decoded thesis IDs defensively, but an invalid category selected by the thesis-aware PPO policy should be impossible by construction.

## 4.3 Thesis observation metadata

Add a compact observation branch, minimally:

```text
thesis_mask: float32[109]
```

Optionally also add a compact semantic grid if it can be implemented without duplicating data:

```text
idea_state: float32[9, 6, 2]
```

where the last axis is long/short activity.

The mask is required.

The separate `idea_state` tensor is optional if the existing MTF streams already expose all per-timeframe idea flags cleanly and the candidate mask gives the policy sufficient explicit eligibility information.

Do not add dozens of redundant copies of the same feature values just to make the schema look richer.

Version this observation extension independently from the existing account-state schema if possible. The current account observation version describes account-coordinate meaning; adding a thesis mask should not force unrelated account semantics to change.

Persist a thesis-observation manifest on checkpoints in the same spirit as the existing observation/regime schema metadata.

Suggested identifier:

```text
thesis-observation-v1
```

## 4.4 Multi-timeframe reasoning encoder

Create a new architecture name rather than changing `MTFEncoder` in place.

Suggested:

```text
arch = mtf_reasoning
class MTFReasoningEncoder
```

Reuse `_CausalTCN`.

Recommended minimal architecture:

```text
M1 sequence  → causal TCN → M1 token
M3 sequence  → causal TCN → M3 token
M5 sequence  → causal TCN → M5 token
M10 sequence → causal TCN → M10 token
M15 sequence → causal TCN → M15 token
M30 sequence → causal TCN → M30 token
H1 sequence  → causal TCN → H1 token
H4 sequence  → causal TCN → H4 token
D1 sequence  → causal TCN → D1 token

each token += learned timeframe embedding

9 tokens
    ↓
small cross-timeframe self-attention block
    ↓
global market representation
    +
account embedding
    ↓
policy latent
```

Keep this small.

Recommended default:

```text
token dimension: 128 unless profiling shows unnecessary cost
attention layers: 1
attention heads: 4
feed-forward width: 256
dropout: same order as current encoder, approximately 0.1
```

Nine tokens do not justify a deep Transformer.

Do not introduce a GNN in v1.

Do not interpret attention weights as causal explanations in reports.

The explicit selected thesis is the auditable decision; attention is only representation learning.

## 4.5 Thesis-aware hybrid PPO distribution

Extend the existing hybrid-policy path.

New thesis-enabled strategy action should conceptually contain:

```text
thesis
stop
risk
tp1_sel
tp2_sel
tp3_sel
sl_mode
tp_mode
z1
z2
exit
```

The selected thesis already contains direction and no-trade intent, so a separate direction coordinate and entry-intensity hold mechanism are redundant in thesis mode.

Expected width with multi-TP + simplex:

```text
11 coordinates
```

Do not mutate the existing 12-D schema.

Create a new schema/version, for example:

```text
thesis-overlay-action-v1
```

or another repository-consistent name discovered during implementation.

The `thesis` coordinate is categorical even if the Gym action space remains a Box for SB3 compatibility.

The policy distribution must emit an exact encoded center for the selected thesis category, just as current hybrid categorical coordinates emit exact centers for SL/TP/exit modes.

There are 109 thesis categories. Exact category centers can be deterministically spaced in the Box interval and decoded by nearest center. Because the hybrid distribution emits exact centers rather than noisy Gaussian samples for that coordinate, the number of categories is acceptable.

The environment decoder must reject non-finite thesis values and decode finite values deterministically.

### Masking requirement

The thesis categorical distribution must apply `thesis_mask` before sampling and before deterministic argmax:

```text
invalid logits → effectively -∞
NO_TRADE always remains valid
```

The mask used by:

- rollout sampling;
- deterministic prediction;
- `evaluate_actions()` during PPO updates;

must be identical for the same stored observation.

Never sample an invalid thesis and then remap it in the environment. That would make PPO optimize a log-probability for an action different from the executed semantic action.

This invariant is non-negotiable.

### Implementation note for Luna

The current `HybridClampedStdMultiInputPolicy._get_action_dist_from_latent()` receives latent state but not raw observations, while the thesis mask is observation-dependent.

Therefore inspect the current SB3 `MultiInputActorCriticPolicy` methods used by the pinned dependency before coding.

Implement the smallest correct override surface needed to pass the observation mask consistently through:

- forward / rollout action distribution;
- deterministic distribution access;
- `evaluate_actions`;
- checkpoint reconstruction.

Do not copy the entire SB3 policy implementation if overriding a few methods is enough.

Add focused tests around this boundary before running training.

## 4.6 V1 execution head does not need conditional trigger selection

For the first complete implementation:

- thesis selection is categorical and masked;
- risk/SL/TP/management outputs may remain factorized from the same final policy latent;
- order construction is conditioned on the selected thesis.

This is already a major semantic improvement.

Do not immediately build:

```text
sample thesis
→ feed sampled thesis embedding through a second recurrent policy
→ sample trigger
→ sample execution
```

unless required for correctness.

A second-stage thesis-conditioned execution head is an optional refinement after the basic architecture is proven.

The critical v1 property is that the selected thesis controls candidate eligibility and order geometry.

---

# 5. Domain Model

Add a decisioning-owned thesis contract. Suggested location:

```text
decisioning/thesis.py
```

`decisioning/` owns action/decision meaning, so the stable thesis semantics belong there rather than in `learning/` or `simulation/`.

Suggested contents:

```python
THESIS_SCHEMA_VERSION = "thesis-candidate-v1"

TIMEFRAMES = (...)
TIMEFRAME_RANK = {...}
IDEAS = ENTRY_IDEA_NAMES  # or a non-circular stable shared definition

@dataclass(frozen=True)
class ThesisCandidate:
    candidate_id: int
    idea: str
    setup_timeframe: str
    direction: int

@dataclass(frozen=True)
class SelectedThesis:
    candidate_id: int
    idea: str
    setup_timeframe: str
    direction: int
```

Add pure functions for:

```text
candidate catalog
candidate → stable ID
ID → candidate
Box center → candidate ID
candidate ID → Box center
timeframe rank
```

Keep this module independent of pandas, Gym, SB3, and simulation.

If importing `ENTRY_IDEA_NAMES` creates a bad dependency direction, move the stable idea-name contract to a small neutral decisioning/features contract and have `entry_ideas.py` import it.

Do not create circular imports for convenience.

---

# 6. Candidate Builder

Create a pure/mostly-pure bridge from feature row to candidate mask.

Potential location:

```text
features/context/thesis_candidates.py
```

or, if repository ownership conventions favor decision semantics:

```text
decisioning/thesis_candidates.py
```

Choose based on existing dependency rules after inspection.

It should consume the exact per-timeframe idea columns created in `entry_ideas.py`.

Required API concept:

```python
def thesis_candidate_mask(row) -> np.ndarray:
    ...
```

Optional diagnostic API:

```python
def active_thesis_candidates(row) -> tuple[ThesisCandidate, ...]:
    ...
```

Required properties:

- deterministic;
- no look-ahead;
- does not inspect future rows;
- does not infer a timeframe from pooled signals;
- exact mapping for bare M1 columns;
- exact mapping for prefixed M3–D1 columns;
- correct handling of the IFVG confirmation timeframe code where existing features require it.

Add unit tests before wiring it into the environment.

---

# 7. Observation Wiring

Modify the environment observation path minimally.

Likely touch-points:

```text
simulation/environment/episode_spaces_initialization.py
simulation/environment/observation_runtime.py
simulation/environment/observation_arrays_initialization.py
simulation/environment/observations.py
```

but inspect actual ownership before editing.

Required behavior when thesis mode is enabled:

```text
observation_space["thesis_mask"] = Box(0, 1, shape=(109,), dtype=float32)
```

and `_get_observation()` returns the exact mask for the current decision row.

If masks can be precomputed safely in a bundle without changing causal visibility, support that path too. Otherwise compute from the current feature row; correctness is more important than premature optimization.

When thesis mode is disabled:

- observation keys must remain unchanged;
- existing checkpoints must see exactly their expected observation space.

Add config-gated behavior, e.g.:

```yaml
env:
  thesis_actions: true
```

or a better name consistent with current config conventions.

Do not turn it on globally in existing experiment runs.

---

# 8. Action Schema and Decoder

## 8.1 New action schema

Do not overload `ActionSchema` flags until it becomes unreadable.

Either:

1. extend it cleanly with an explicit thesis capability; or
2. add `ThesisActionSchema`.

Prefer the approach that keeps old serialized manifests exactly stable.

Required schema metadata must include:

```text
schema version
layout key
ordered coordinates
thesis candidate schema version
thesis category count
```

## 8.2 Decoder

In thesis mode:

1. decode thesis category;
2. if `NO_TRADE`, return hold and zero entry risk;
3. otherwise derive direction from the selected thesis;
4. verify that candidate is valid under the current `thesis_mask`;
5. decode risk/SL/TP/management coordinates;
6. store the selected thesis in the decision state for later order construction and logging.

Do not call `strategy.context_direction()` to override the thesis direction after thesis selection.

Legacy strategy-action mode continues to use the old behavior.

## 8.3 No entry without a valid thesis

When `env.thesis_actions=true`:

```text
new trade → must have selected valid active thesis
```

This requirement is independent of legacy `strategy.entry.enforce_gate`.

The legacy gate setting remains relevant only to legacy action mode unless a narrow compatibility reason exists.

Do not allow thesis mode to select `NO_TRADE` and then open because another old path inferred direction.

---

# 9. Thesis-Conditioned Stop Logic

Replace the new thesis path's call pattern:

```text
entry_idea_context(...)
→ highest active timeframe
→ entry_timeframe_floor
```

with:

```text
SelectedThesis
→ selected setup timeframe
→ stop eligibility
```

Modify `place_strategy_order()` carefully.

Preferred new contract:

```python
place_strategy_order(
    ...,
    thesis: SelectedThesis | None = None,
    legacy_entry_timeframe_floor: str = "M1",
    ...
)
```

or an equivalent backwards-compatible boundary.

When a thesis is present:

```text
entry_timeframe_floor = thesis.setup_timeframe
```

Do not consult the highest-active-timeframe heuristic.

### Standard Deviation special case

Current behavior can see several active SD timeframes and allow level 1 from the active SD set.

New behavior:

```text
primary = standard_deviation@TF
→ only TF_standard_deviation_level_1_price is the SD structural stop
```

For M1 use the unprefixed M1 field.

If that exact structural stop is unavailable, reject the setup rather than silently substituting another active SD timeframe.

### Other ideas

For PO3 / OB / FVG / IFVG:

- construct current structural candidates as before;
- filter lower-than-primary-setup timeframe candidates;
- preserve higher/equal timeframe candidates;
- retain manipulation, distance, side, causality, and execution filters;
- preserve active sweep semantics only if the sweep satisfies the selected thesis floor and is actually allowed by the existing rule.

If an existing special rule conflicts with the thesis floor, make the conflict explicit in audit output and add a test.

---

# 10. Thesis-Conditioned Target Logic

Extend `target_menu()` with optional thesis/timeframe filtering.

Do not delete the existing target universe.

When thesis mode is active:

```text
target reference timeframe >= selected setup timeframe
```

by default.

Preserve:

- correct side of entry;
- min distance / stop distance;
- max TP reach;
- RR range logic;
- confirmed-at causality;
- front-running/tick rounding;
- multi-TP ordering.

Do not allow unrelated M1 or M3 targets to become TP for an M15 primary thesis merely because they are close.

If there is no valid target under thesis constraints and structural mode requires a target, reject with a thesis-specific diagnostic reason rather than falling back to a lower-timeframe target.

EMA runner semantics remain as currently implemented unless directly affected by candidate filtering.

---

# 11. Supporting Multi-Timeframe Context

Continue using `entry_idea_context()` or a successor diagnostic helper to capture all evidence active at entry.

But split reporting semantics:

```text
primary_thesis
```

is the selected reason.

```text
supporting_context
```

contains all other active ideas/timeframes.

Do not label every active idea as an “entry reason.”

Suggested context classification relative to primary setup timeframe:

```text
same_tf_confluence
higher_tf_context
lower_tf_confirmation
opposing_context
```

Classification may be deterministic and diagnostic-only.

Do not use these labels as hard trading rules in v1.

For example:

```text
primary = FVG_RETEST@M5 LONG

higher_tf_context:
    PO3@M15 LONG
    ORDER_BLOCK@H1 LONG

same_tf_confluence:
    IFVG_UNRETESTED@M5 LONG

lower_tf_confirmation:
    IFVG_RETEST@M1 LONG

opposing_context:
    ORDER_BLOCK@M15 SHORT
```

The policy may learn how much those states matter through the MTF encoder.

---

# 12. MTF Reasoning Encoder Implementation

Suggested new file:

```text
models/encoders/mtf_reasoning.py
```

Do not turn `models/encoders/mtf.py` into an incompatible implementation.

Reuse:

```text
_CausalTCN
_ACCOUNT_EMB_DIM
AccountMLP
mask handling
configured MTF stream discovery
```

## Required tests

1. Output shape.
2. Every configured timeframe branch contributes.
3. Changing one valid timeframe input can change output.
4. Poisoning masked/padded rows does not change output.
5. No future candle becomes visible.
6. Gradients are finite.
7. FP32 CPU forward works.
8. CUDA/BF16 smoke only where supported.
9. Architecture checkpoint validation distinguishes `mtf` from `mtf_reasoning`.

## Timeframe embedding

Add a learned embedding indexed by the stable timeframe order.

This is important because otherwise the cross-timeframe block only receives anonymous branch tokens.

## Cross-timeframe block

One TransformerEncoderLayer or equivalent self-attention block is sufficient.

Avoid:

- deep transformer stacks;
- cross-attention over every raw candle across every timeframe;
- graph libraries;
- exotic positional encodings.

The goal is explicit timeframe interaction with low implementation and runtime cost.

---

# 13. Thesis Hybrid Policy

Suggested new learning module:

```text
learning/rl/thesis_hybrid.py
```

Reuse code from `learning/rl/hybrid.py` where practical.

Do not fork large chunks without a reason.

Conceptual distribution:

```text
thesis:       masked Categorical(109)
sl_mode:      Categorical(existing semantics)
tp_mode:      Categorical(existing semantics)
exit:         Categorical(existing semantics)

stop:         Normal
risk:         Normal
tp1_sel:      Normal
tp2_sel:      Normal
tp3_sel:      Normal
z1:           Normal
z2:           Normal
```

Packed into the Box coordinate order using exact categorical centers.

Log probability:

```text
log π(a|s)
=
log π(thesis|s, mask)
+ log π(sl_mode|s)
+ log π(tp_mode|s)
+ log π(exit|s)
+ Σ log π(continuous_i|s)
```

Entropy uses the same factorization.

Masked invalid thesis categories must contribute zero probability.

### Numerical behavior

When only `NO_TRADE` is valid:

- thesis distribution must be deterministic on category 0;
- log probability must remain finite;
- entropy for thesis may be zero;
- no NaNs.

When multiple candidates are valid:

- probabilities normalize only over valid candidates.

### Checkpoint serialization

Persist enough constructor metadata for `PPO.load()` to reconstruct:

- thesis coordinate position;
- candidate schema;
- candidate category centers;
- mask observation key;
- defer thresholds;
- continuous log-std bounds.

Add round-trip save/load test.

---

# 14. Agent Wiring

Update `learning/rl/agent.py` minimally.

Add:

```text
encoder_for("mtf_reasoning")
```

Add a new policy-distribution selector, for example:

```yaml
ppo:
  policy_distribution: thesis_hybrid_v1
```

Require compatible config:

```text
env.thesis_actions = true
agent.arch = mtf_reasoning   # preferred research path
strategy_actions = true
```

The thesis distribution may technically work with another encoder for ablation, but the primary experiment run should use the new MTF reasoning encoder.

Reject incompatible configs early and clearly.

Examples:

- thesis distribution without `thesis_mask` observation → error;
- thesis action schema with legacy Gaussian policy → error;
- thesis mode with discrete legacy action space → error;
- old checkpoint loaded into new thesis schema without an explicit migration → error.

Do not attempt to auto-migrate a 12-D legacy checkpoint into the new 11-D thesis policy. They represent different action semantics and should be trained separately.

---

# 15. Trade / Order Persistence

Selected thesis must survive the entire order lifecycle, including delayed fills.

Current pending-order state already stores selected action fields.

Add the selected thesis to the pending order.

Do not recompute the thesis at fill time from a later feature row.

The thesis belongs to the decision-time state.

If fill latency occurs:

```text
decision-time thesis = immutable
fill-time price = execution state
```

The order may still be rejected if execution/risk constraints make it invalid, but its semantic origin must not mutate.

Store on `Position` or equivalent immutable entry metadata:

```text
thesis_candidate_id
thesis_schema_version
primary_idea
setup_timeframe
direction
decision_time
```

Do not infer these later from SL/TP names.

---

# 16. Logging and Reporting Contract

On `order_submit` where applicable, and definitely on `open`, include:

```text
thesis_candidate_id
thesis_schema_version
primary_idea
primary_setup_timeframe
primary_direction
supporting_idea_timeframes
higher_tf_context
same_tf_confluence
lower_tf_confirmation
opposing_context
sl_ref
sl_timeframe
tp1_ref / tp1_timeframe
tp2_ref / tp2_timeframe
tp3_ref / tp3_timeframe
```

Retain existing `entry_ideas` and `entry_idea_timeframes` if downstream reports use them, but treat them as context fields.

Deprecate the semantic meaning of:

```text
entry_idea_stop_timeframe_floor
```

under thesis mode.

If retained for compatibility, it must either:

- equal the selected thesis setup timeframe and be clearly renamed/annotated; or
- remain as legacy diagnostic context while a new `thesis_stop_timeframe_floor` field drives execution.

Prefer explicit new fields over silently changing the meaning of an existing report column.

---

# 17. Diagnostics

Add metrics that make it possible to tell whether the architecture is working before expensive training.

At minimum:

```text
thesis/no_trade_count
thesis/trade_candidate_count
thesis/eligible_candidate_mean
thesis/eligible_candidate_max
thesis/selected/<idea>
thesis/selected_tf/<timeframe>
thesis/selected_direction/long
thesis/selected_direction/short
thesis/rejected_invalid_id          # should be zero for thesis-aware policy
thesis/rejected_inactive            # should be zero for thesis-aware policy
thesis/rejected_no_sl
thesis/rejected_no_tp
thesis/sl_below_floor               # must be zero for opened trades
thesis/tp_below_floor               # must be zero for opened trades
```

If easy, report candidate entropy and fraction of steps where more than one thesis candidate is available.

Do not create hundreds of logger keys for all 108 categories. Aggregate by idea/timeframe/direction.

---

# 18. Tests: Required Before Training

Create focused tests rather than relying on a full long run to reveal semantic bugs.

## 18.1 Candidate catalog tests

Verify:

- 109 total categories;
- category 0 is `NO_TRADE`;
- stable ID round trip;
- stable center round trip;
- all six ideas present;
- all nine timeframes present;
- both directions present;
- no duplicate IDs;
- no duplicate semantic candidates.

## 18.2 Candidate-mask tests

Hand-build rows proving:

```text
FVG_RETEST@M5 LONG active
→ exact M5-long candidate enabled
→ M1-long FVG candidate not enabled unless M1 signal is also active
→ M5-short candidate disabled
```

Repeat at least for:

- PO3
- order block
- standard deviation
- FVG retest
- IFVG retest
- IFVG unretested

Test M1 bare-column handling separately.

Test IFVG confirmation timeframe-code handling separately.

## 18.3 Thesis stop semantics

Canonical test state:

```text
H1 ORDER_BLOCK LONG active
M15 PO3 LONG active
M5 FVG_RETEST LONG active
M1 IFVG_RETEST LONG active
```

When selected thesis is:

```text
FVG_RETEST@M5 LONG
```

assert:

```text
stop floor = M5
M1 stop references rejected
M3 stop references rejected
M5+ allowed if otherwise valid
H1 active context does NOT raise the floor to H1
```

Then select:

```text
PO3@M15 LONG
```

and assert:

```text
stop floor = M15
M5 references rejected
```

This is the core regression test for the original problem.

## 18.4 Standard-deviation test

Have SD active on M5 and M15.

Select:

```text
STANDARD_DEVIATION@M5
```

Assert only M5 level-1 is the SD stop.

Select:

```text
STANDARD_DEVIATION@M15
```

Assert only M15 level-1 is the SD stop.

No cross-timeframe substitution.

## 18.5 Target semantics

For primary M5:

- M1/M3 targets rejected;
- M5/M15/H1 targets eligible if otherwise valid.

For primary H1:

- lower than H1 targets rejected.

Preserve RR and reach filters.

## 18.6 Masked PPO distribution

Verify:

- invalid thesis categories are never sampled;
- deterministic mode never chooses invalid category;
- log probabilities finite;
- entropy finite;
- gradients finite;
- only `NO_TRADE` valid case works;
- mixed batch with different masks works;
- `evaluate_actions()` uses each row's stored mask;
- save/load round trip preserves behavior.

## 18.7 MTF reasoning encoder

Verify causal/padding behavior as described earlier.

## 18.8 Delayed fill

Select thesis at decision time.

Advance to a fill row with different currently active ideas.

Assert the opened position/log retains the original thesis.

## 18.9 Legacy compatibility

With thesis mode off:

- existing 12-D action schema unchanged;
- existing hybrid_v1 tests unchanged;
- old `MTFEncoder` unchanged;
- legacy order geometry follows existing path;
- existing experiment run configs parse as before.

This is essential.

---

# 19. Implementation Phases

Luna should implement in this order.

Do not start with the neural policy.

## Phase A — Repository audit and invariants

Before edits:

1. confirm HEAD is the expected commit or identify newer user changes;
2. inspect `git status`;
3. preserve `experiment_run_worker_dispatch.log`;
4. read `AGENTS.md`;
5. inspect decisioning, entry ideas, stop/target construction, MTF encoder, hybrid policy, semantic policy, checkpoint schema validation, observation-space initialization, and tests;
6. write a short local implementation map in working notes;
7. run the most relevant existing focused tests once before changing behavior.

Do not run expensive training.

## Phase B — Thesis domain contract

Implement:

- stable candidate catalog;
- schema version;
- ID/center mapping;
- timeframe ordering;
- tests.

No environment/policy changes yet.

Gate:

```text
Ruff + Mypy on touched files
candidate contract tests pass
```

## Phase C — Candidate eligibility

Implement exact row → candidate mask.

Use per-timeframe idea features.

Add tests for all six ideas.

Gate:

```text
candidate-mask tests pass
existing entry-idea tests pass
```

## Phase D — Thesis observation branch

Add optional `thesis_mask` observation.

Add schema metadata.

Thesis mode off must be byte/shape compatible with legacy observation contract.

Gate:

```text
environment reset/step observation-space tests
no mismatch between declared and returned observation keys/shapes
```

## Phase E — Thesis action schema and decoding

Add new schema.

Decode `NO_TRADE` and active thesis.

Direction comes from thesis.

Persist selected thesis in decision state and pending orders.

Do not yet change stop/TP semantics if isolating the patch makes testing easier.

Gate:

```text
action schema tests
decoder tests
pending-order thesis persistence tests
```

## Phase F — Thesis-conditioned order geometry

Change stop and target filtering only in thesis mode.

Implement exact SD-timeframe rule.

Add canonical MTF semantic tests.

Gate:

```text
100% of opened thesis-mode test trades obey SL/TP timeframe invariant
legacy order tests remain green
```

## Phase G — MTF reasoning encoder

Add the small cross-timeframe attention encoder.

Wire architecture selection.

Gate:

```text
encoder tests
causal visibility tests
finite gradient tests
architecture validation tests
```

## Phase H — Masked thesis hybrid PPO

Generalize hybrid categorical distribution.

Wire mask correctly through rollout and PPO update.

Do not proceed until mask/log-prob tests are strong.

Gate:

```text
invalid candidate sample count = 0 in tests
finite log_prob/entropy/gradients
PPO one-update smoke works
save/load round trip works
```

## Phase I — Reporting and diagnostics

Add thesis-native logs.

Ensure charts/reporting can read old runs without the new fields.

Add readable idea labels for all six idea types if still missing.

Gate:

```text
report formatters handle thesis and legacy rows
no KeyErrors on old artifacts
```

## Phase J — CPU functional smoke

Use a tiny deterministic/synthetic or short real-data environment run.

Validate:

- candidate masks vary;
- `NO_TRADE` works;
- actual thesis candidates can be selected;
- SL/TP floors match selected thesis;
- pending fills retain thesis;
- no NaNs.

Do not judge profitability.

## Phase K — GPU learning smoke

Only after all semantic gates pass.

Use existing repository resource rules and reuse an existing allocation when available.

Run a bounded PPO smoke sufficient to prove:

- rollout collection works;
- PPO update works;
- thesis distribution trains;
- checkpoint saves/loads;
- evaluation runs;
- trades can occur;
- multiple valid thesis categories are observed in the data;
- no invalid thesis is executed.

Do not launch a long 2M/20M scientific experiment run merely to test wiring.

If the policy collapses immediately to `NO_TRADE`, diagnose rewards/entropy/mask availability before increasing timesteps.

---

# 20. Initial Research Configuration

Do not modify the existing `sustainable_growth_ppo_three_policy_seed50_train2025_2m_v31_20261027_v1.yaml` in place.

Create a new clearly named research config after implementation.

Conceptual overrides:

```yaml
env:
  strategy_actions: true
  thesis_actions: true
  agent_direction_control: false
  # old direction control is not the thesis direction source

features:
  entry_ideas:
    enabled: true

agent:
  arch: mtf_reasoning

ppo:
  policy_distribution: thesis_hybrid_v1
  actor_arch: shared
```

Keep existing multi-TP / risk / exit settings unless incompatibility requires an explicit new setting.

Do not change reward function at the same time as the architecture. The first comparison should isolate the reasoning/action change.

Do not change data split.

Do not expose locked OOS data for model selection.

---

# 21. Acceptance Criteria for “Implementation Complete”

The coding task is complete only when all of the following are true.

## Semantic correctness

- Every opened thesis-mode trade has exactly one primary thesis.
- Primary thesis is one of the six defined ideas on one exact timeframe and direction.
- The thesis was active at the decision row.
- Direction always agrees with the selected thesis.
- SL floor comes from the selected setup timeframe, never highest-active timeframe.
- Higher-TF context does not automatically raise the floor.
- Lower-TF context does not lower the floor.
- Standard-deviation stop uses level 1 from the selected SD timeframe only.
- Structural targets respect the thesis timeframe floor.
- Delayed fills preserve decision-time thesis.
- No future timeframe candle is used.

## Policy correctness

- Invalid thesis categories have zero sampling probability.
- `NO_TRADE` is always valid.
- PPO rollout and `evaluate_actions()` use identical masks.
- Log probability, entropy, values, and gradients are finite.
- Thesis policy checkpoint can be saved and loaded.
- Legacy checkpoint/action schemas remain isolated and valid.

## Architecture correctness

- MTF reasoning encoder keeps one causal branch per timeframe.
- A small cross-timeframe interaction layer exists.
- Timeframe identity is explicitly embedded.
- No giant GNN/Transformer rewrite.
- Existing plain MTF encoder remains available.

## Diagnostics

Every opened trade exposes at least:

```text
primary_idea
primary_setup_timeframe
thesis_candidate_id
direction
sl_ref
sl_timeframe
TP reference/timeframe fields
supporting MTF context
```

## Quality gates

Run repository-standard formatting/lint/type gates.

Run all focused tests touching:

- decisioning schemas;
- entry ideas;
- action schema;
- hybrid actor;
- semantic actor where relevant;
- encoders;
- entry levels;
- target references;
- environment observation/action paths;
- checkpoint save/load.

Then run the broader relevant test suite according to repository policy.

Do not claim the full suite passed unless it was actually run.

---

# 22. Explicit Non-Goals

Do not do these as part of this implementation unless a correctness issue forces them.

- Do not redesign PO3, OB, FVG, IFVG, or SD detectors.
- Do not change their research definitions.
- Do not fix unrelated IFVG scientific-definition questions in the same patch.
- Do not introduce a GNN.
- Do not add an LLM-style reasoning trace.
- Do not make attention weights a claimed explanation.
- Do not create one agent per timeframe.
- Do not force trades to use only one timeframe.
- Do not add explicit selection of every supporting timeframe.
- Do not add explicit trigger-head hierarchy in v1.
- Do not redesign rewards.
- Do not change FTMO guardrails.
- Do not change execution cost semantics.
- Do not change train/test dates.
- Do not retrain legacy checkpoints under silently changed semantics.
- Do not run a large experiment run before semantic and learning smoke gates pass.
- Do not touch `experiment_run_worker_dispatch.log`.

---

# 23. Optional Phase 2 — Only After V1 Evidence

Do not implement this automatically just because it sounds sophisticated.

Consider it only if v1 diagnostics show a clear need.

## 23.1 Explicit trigger selection

Potential action:

```text
primary thesis
+
conditional trigger
```

Trigger candidate constraints:

- same direction as primary;
- timeframe <= primary setup timeframe;
- currently active;
- compatible semantic type.

This requires a **conditional categorical distribution** because trigger validity depends on the sampled primary thesis.

Do not implement it as two independent categorical heads.

Correct factorization would be:

```text
π(primary | state)
×
π(trigger | state, primary)
×
π(execution | state, primary, trigger)
```

Only add this if the primary-only architecture cannot adequately distinguish setup from confirmation.

## 23.2 Thesis-conditioned execution head

Potentially condition risk/SL/TP actor state on a learned embedding of the selected primary thesis.

Again, this changes distribution factorization and requires correct PPO log-probability accounting.

Do not approximate it by executing different semantics than the logged action.

## 23.3 Auxiliary representation losses

Only if needed, consider an auxiliary task such as predicting:

- active thesis candidates;
- higher/lower timeframe alignment;
- future-neutral labels that do not leak.

Do not add auxiliary losses in the initial implementation.

---

# 24. Evaluation After Implementation

The first scientific comparison should isolate architecture.

Suggested sequence:

```text
A. Current flat action / current encoder
B. Thesis action + existing MTF encoder
C. Thesis action + MTF reasoning encoder
```

This separates:

```text
effect of explicit thesis semantics
```

from:

```text
effect of cross-timeframe neural interaction
```

Do not compare five simultaneous changes.

Primary early diagnostic outcomes:

- trade count;
- thesis selection distribution;
- selected setup timeframe distribution;
- SL/TP provenance consistency;
- invalid/rejected geometry rate;
- risk per trade;
- no-trade rate;
- policy entropy;
- frequency of multiple simultaneously eligible theses.

Only after those are healthy should the experiment run be judged on:

- return;
- PF;
- drawdown;
- FTMO-style breach behavior;
- sustainable-growth metrics;
- seed stability.

---

# 25. Expected File Touch-Points

Treat this as a map, not an instruction to edit every file.

Likely new files:

```text
decisioning/thesis.py
models/encoders/mtf_reasoning.py
learning/rl/thesis_hybrid.py
```

Potential modified files:

```text
decisioning/actions.py
decisioning/contracts.py                     # only if stable decision output requires it
features/context/entry_ideas.py             # preferably minimal
simulation/environment/episode_spaces_initialization.py
simulation/environment/observation_runtime.py
simulation/environment/action_runtime.py
simulation/environment/step_action_execution.py
simulation/environment/entry_execution_runtime.py
simulation/environment/entry_runtime.py
trading/orders/entries.py
trading/orders/stops.py
trading/orders/targets.py
learning/rl/agent.py
models/encoders/__init__.py
trading/execution/... or position model      # only where entry metadata belongs
evaluation/reporting/plotting modules        # only for thesis fields
```

Likely tests:

```text
tests/integration/test_thesis.py        # follow actual test layout
tests/unit/features/test_entry_ideas.py
tests/integration/test_action_schema_contract.py
tests/unit/models/test_hybrid_actor.py
tests/unit/models/test_encoders.py
tests/integration/backtest/test_entry_levels.py
tests/integration/backtest/test_target_reference_contract.py
plus focused environment/checkpoint tests
```

Before creating a new test directory, follow the repository's existing layout.

---

# 26. Luna 6 Working Style

This task is intended for Codex Luna 6 with full repository access.

Operate autonomously, but optimize for correctness and implementation speed.

## At each phase

1. inspect the exact existing code before editing;
2. identify the smallest stable boundary;
3. write/adjust focused tests;
4. implement;
5. run focused gates;
6. inspect diff;
7. move to the next phase only when the previous invariant is proven.

Do not spend time producing speculative design documents inside the repository unless they directly help implementation or the repository requires them.

Prefer code + tests + concise status notes.

## When repository reality differs from this plan

Do not blindly force names or paths from this document.

Preserve the architectural invariants:

```text
explicit primary thesis
exact per-timeframe eligibility
masked categorical selection
selected thesis owns SL/TP timeframe semantics
causal MTF reasoning
legacy compatibility
```

Adapt filenames/classes to the actual codebase.

Document material deviations in the final handoff.

---

# 27. Final Handoff Required From the Agent

At completion, report:

## A. Commit / status

- final commit SHA(s);
- whether pushed;
- remaining worktree items;
- explicit confirmation that `experiment_run_worker_dispatch.log` was preserved.

## B. Architecture implemented

Briefly state:

- thesis schema;
- number of thesis categories;
- observation mask;
- action schema;
- MTF reasoning encoder;
- masked PPO distribution;
- SL/TP thesis conditioning.

## C. Tests / gates

List exact commands and results.

Separate:

- focused pytest;
- lint/format;
- mypy;
- broader/full pytest if actually run;
- GPU smoke if actually run.

## D. Behavioral evidence

Provide counts/metrics showing:

- candidate masks exist;
- policy never executed invalid thesis;
- trade rows contain primary thesis;
- stop/target timeframe invariants hold;
- thesis selection is not silently replaced at fill time.

## E. Remaining caveats

Especially state whether these remain intentionally deferred:

- explicit trigger selection;
- thesis-conditioned second-stage execution head;
- full long training;
- multi-seed research validation.

Do not claim SOTA, profitability, or research success from an implementation smoke test.

---

# 28. Definition of the Final System

The implementation is successful when the following statement is true:

> The agent observes causal market state from all configured timeframes, learns cross-timeframe relationships, selects one currently valid idea/timeframe/direction as the primary trade thesis, and constructs risk, stop, target, and management decisions under the structural semantics of that selected thesis. Other timeframes remain available as learned supporting or conflicting context, but they can no longer accidentally redefine the trade's stop/target timeframe simply because their signals are active.

That is the target.
