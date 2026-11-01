# Decision provider adapters

Adapters implement the backend-neutral decision provider contract for concrete
policies. `rule_based.py` adapts a rule policy, while `sb3.py` adapts a
Stable-Baselines3 model and decodes its output using the model's action schema.

The adapter boundary accepts the versioned input contract from
`decisioning/contracts.py` and returns a typed decision. Keep action ordering,
schema identity, deterministic inference behavior, and metadata consistent
with the model checkpoint. Simulator and live callers depend on this shared
meaning; vendor and broker translation belongs elsewhere.

Focused tests are in `tests/unit/decisioning/` and model checkpoint tests are
in `tests/unit/models/`. See the [decisioning guide](../../docs/modules/decisioning.md)
and [action schema reference](../../docs/reference/action_schemas.md).
