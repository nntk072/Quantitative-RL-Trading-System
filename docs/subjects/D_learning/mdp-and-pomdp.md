# MDP and POMDP

**Status:** Wave D draft
**Use this when:** You need to reason about the boundary between hidden market/account state and the observation presented to a policy.

## Summary and use this when

The environment advances through actions, rewards, and terminal conditions. A policy sees an observation assembled by the environment, not the full market process. Treat the account schema and runtime observation branches as distinct contracts; MDP/POMDP vocabulary models the decision problem but does not prove market dynamics are Markov.

- Start with the resolved configuration and the named input/output contracts.
- Follow one transition or fit path in source before interpreting a metric.
- Treat the linked notebook as a mechanics example using bundled synthetic data.

## Key terms

- [MDP](../../glossary.md)
- [POMDP](../../glossary.md)
- [Episode](../../glossary.md)
- [Observation schema](../../glossary.md)
- [Action schema](../../glossary.md)

## Explanation

### Decision or learning boundary

The environment advances through actions, rewards, and terminal conditions. A policy sees an observation assembled by the environment, not the full market process. Treat the account schema and runtime observation branches as distinct contracts; MDP/POMDP vocabulary models the decision problem but does not prove market dynamics are Markov.

The five source-backed contracts below identify where this subject crosses a
package boundary. Read them together: a policy output has meaning only under
the environment, schema, and run identity that produced it.

### 1. One environment step is the decision boundary

A policy action enters the environment transition. The environment owns execution, accounting, reward, and episode-end stages; a policy cannot infer those from an observation value alone.

- Source: `simulation/environment/env.py::TradingEnv.step` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/simulation/test_environment/test_simulation_transition_contract.py`.
- Practical check: Check action, next observation, reward, terminated, truncated, and info together.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 2. The vector adapter preserves Gymnasium episode endings

The adapter combines terminated or truncated into SB3 done, records TimeLimit.truncated only for truncation without termination, saves terminal_observation, then resets that slot.

- Source: `learning/rl/environment_adapter.py::_shard_worker` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_agent_vector_env.py`.
- Practical check: Do not mistake the reset observation for the terminal observation.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 3. The account branch has declared coordinates

`ObservationSchema` declares the account branch version and ordered coordinates. `build_observation_schema` optionally appends entry-state coordinates. Account width alone cannot establish coordinate meaning.

- Source: `decisioning/observations.py::build_observation_schema` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/decisioning/test_observations.py`.
- Practical check: Compare saved account schema metadata before loading a policy.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 4. The visible sequence is a finite history

The fixed window retains recent real rows and left-pads short histories with a row mask. History can reduce ambiguity, but it does not reveal unobserved state.

- Source: `decisioning/observations.py::pad_observation_window` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/decisioning/test_observations.py`.
- Practical check: Keep the row mask with the sequence.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 5. Eligibility and observation are separate

The runtime assembles observations and configured masks. An eligible action can still be a poor decision; a missing observation row is different from an ineligible action.

- Source: `simulation/environment/observation_runtime.py` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/simulation/test_environment/test_observation_schema.py`.
- Practical check: Inspect branch and mask meaning before comparing trajectories.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

## Worked example

Two hidden states emit the same visible symbol; a short observation history separates only some histories. The notebook computes a small belief update with fixed probabilities and no market data.

Open the [Tier A notebook](examples/mdp-and-pomdp.ipynb). It runs on CPU using
only deterministic values bundled in the cell. It neither trains nor evaluates
a market policy.

```{toctree}
:hidden:

examples/mdp-and-pomdp
```

The [compact contract reference](../../reference/subjects/mdp-and-pomdp.md) records
the exact source-facing obligations for maintainers.

## Tasks

- Trace one call from the environment step to the returned tuple.
- Compare a terminal observation with the reset observation in the vector adapter.
- Inspect account coordinates in the observation schema before changing a policy input.
- Keep the eligibility mask and sequence validity mask on their declared axes.

## Contract

| Boundary | Required behavior | Source |
|---|---|---|
| One environment step is the decision boundary | A policy action enters the environment transition. | `simulation/environment/env.py::TradingEnv.step` |
| The vector adapter preserves Gymnasium episode endings | The adapter combines terminated or truncated into SB3 done, records TimeLimit.truncated only for truncation without termination, saves terminal_observation, then resets that slot. | `learning/rl/environment_adapter.py::_shard_worker` |
| The account branch has declared coordinates | The account schema declares its version and ordered coordinates, with optional entry-state coordinates. | `decisioning/observations.py::build_observation_schema` |
| The visible sequence is a finite history | The fixed window retains recent real rows and left-pads short histories with a row mask. | `decisioning/observations.py::pad_observation_window` |
| Eligibility and observation are separate | The runtime assembles observations and configured masks. | `simulation/environment/observation_runtime.py` |

## Verify

For this subject, inspect the focused tests before changing a contract:

- `tests/unit/simulation/test_environment/test_simulation_transition_contract.py` — one environment step is the decision boundary.
- `tests/unit/models/test_agent_vector_env.py` — the vector adapter preserves gymnasium episode endings.
- `tests/unit/decisioning/test_observations.py` — account branch version and coordinates.
- `tests/unit/decisioning/test_observations.py` — the visible sequence is a finite history.
- `tests/unit/simulation/test_environment/test_observation_schema.py` — eligibility and observation are separate.

The notebook is a deterministic teaching check. A repository test is a
software check. Neither is an out-of-sample result or a claim of economic
performance. Keep those evidence categories separate in reports.

## Limits and common mistakes

- The Markov property is a modeling assumption; no test establishes it for markets.
- A belief update on fixed toy probabilities is not a production state estimator.
- The notebook has no broker, market feed, learned model, or return measurement.

- Do not use a smoke run as evidence of a strategy effect.
- Do not select a model or threshold using the exposed 2026 reporting interval.
- Preserve invalid, negative, breached, no-trade, and incomplete outcomes.

## Change checklist

Before changing this behavior:

1. Trace one call from the environment step to the returned tuple.
2. Compare a terminal observation with the reset observation in the vector adapter.
3. Inspect account coordinates in the observation schema before changing a policy input.
4. Keep the eligibility mask and sequence validity mask on their declared axes.
5. Update the relevant schema, caller, fixture, and focused test if the
   behavior or serialized meaning changes.
6. Record the source revision, resolved config, data identity, and artifact
   digest for any run used in a research claim.

## Review procedure

Read one source path and its directly connected test at the pinned revision.
Recheck any claim against the active checkout before relying on current behavior.
Use the notebook to inspect a tiny boundary case, then inspect actual run
artifacts separately if the question is about a trained policy. Record
mismatches rather than silently adapting a saved checkpoint or report.

## Maintainer note

- Verified source baseline: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Current dirty-source-only behavior is unverified by this page.
- Owner: `ml_engineer`.
- Notebook tier: A; synthetic, deterministic CPU example.
