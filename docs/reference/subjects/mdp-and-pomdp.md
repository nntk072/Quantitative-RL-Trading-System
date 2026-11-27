# MDP and POMDP contract

This page records the subject-specific contract at source revision
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`. The generated API pages describe callable signatures;
the entries below record cross-package meaning and validation obligations.

## Contract table

| Contract | Exact obligation | Source and focused test |
|---|---|---|
| One environment step is the decision boundary | A policy action enters the environment transition. The environment owns execution, accounting, reward, and episode-end stages; a policy cannot infer those from an observation value alone. | `simulation/environment/env.py::TradingEnv.step`; `tests/unit/simulation/test_environment/test_simulation_transition_contract.py` |
| The vector adapter preserves Gymnasium episode endings | The adapter combines terminated or truncated into SB3 done, records TimeLimit.truncated only for truncation without termination, saves terminal_observation, then resets that slot. | `learning/rl/environment_adapter.py::_shard_worker`; `tests/unit/models/test_agent_vector_env.py` |
| The account branch has declared coordinates | `ObservationSchema` declares the account branch version and ordered coordinates; `build_observation_schema` optionally appends entry-state coordinates. Width alone cannot establish coordinate meaning. | `decisioning/observations.py::ObservationSchema`, `build_observation_schema`; `tests/unit/decisioning/test_observations.py` |
| The visible sequence is a finite history | The fixed window retains recent real rows and left-pads short histories with a row mask. History can reduce ambiguity, but it does not reveal unobserved state. | `decisioning/observations.py::pad_observation_window`; `tests/unit/decisioning/test_observations.py` |
| Eligibility and observation are separate | The runtime assembles observations and configured masks. An eligible action can still be a poor decision; a missing observation row is different from an ineligible action. | `simulation/environment/observations/runtime.py`; `tests/unit/simulation/test_environment/test_observation_schema.py` |

## Compatibility and evidence

When behavior or serialized meaning changes, inspect the producer, the
consumer, saved metadata, and the focused test together. The resolved config
and artifact identity are necessary to interpret an actual run. A toy notebook
or source-level test does not establish market quality, policy performance,
or survival qualification.

The source anchors above were read from the pinned baseline. Dirty-source-only
behavior in the active checkout remains unverified. See the
[subject guide](../../subjects/D_learning/mdp-and-pomdp.md) and
[Tier A notebook](../../subjects/D_learning/examples/mdp-and-pomdp.ipynb).
