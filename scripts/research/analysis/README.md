# Research analysis commands

Research analyses inspect recorded data, checkpoints, decisions, fills, and
evidence. They do not redefine the trading simulator, train new policies by
accident, or modify immutable run records. The production packages own
reusable behavior; these commands provide reproducible, source-bound
analysis entry points.

| Area | Responsibility |
|---|---|
| `market_data/` | Input identity, quote availability, alignment, and quality |
| `features/` | Causal availability, opportunity populations, observation validity |
| `decisioning/` | Candidate and action semantics, masks, and identity |
| `models/` | Model structure, encoder inputs, and observation shapes |
| `evaluation/` | Reanalysis, matched comparisons, outcome and fill reconciliation |
| `evidence/` | Provenance, manifest verification, numerical claims, and archives |

## Reuse before adding a command

- Put shared data transformation in `market_data/` or `features/`, trading
  behavior in `trading/` or `simulation/`, policy contracts in
  `decisioning/`, and model behavior in `models/` or `learning/`.
- Keep analysis adapters thin. A command accepts explicit configuration and
  input/output paths, delegates reusable logic to its owning package, and
  writes source-bound artifacts.
- Register repeatable research executions in
  `config/research/experiments.yaml` as component implementations. Refer
  to them from experiments or named assemblies instead of creating separate
  launchers or report structures for each variation.
- Use `experiments/research/reporting.py` for result consolidation, not
  hand-edited research tables. Keep historical inputs read-only and
  distinguish missing evidence from measured zero.

## Evidence interpretation

Archive inventories and recovery searches discover candidate source material;
they do not establish scientific validity. Confirm file hashes, configuration
identity, exact evaluation period, metric denominator, and provenance before
a historical observation is treated as evidence. An unavailable or withdrawn
result stays marked accordingly. The authoritative historical index is
[`config/research/history.yaml`](../../../config/research/history.yaml).

The [research workflow](../../../docs/research/workflow.md) describes
the executable configuration and result schema. Scientific interpretation
belongs in [research methods](../../../docs/research/README.md), rather than
in one-off campaign notes. Unit tests are under `tests/unit/research/`;
protocol-level evidence checks are under `tests/research/`.
