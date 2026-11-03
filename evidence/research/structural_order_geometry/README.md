# Structural order geometry contract

## Scope

This packet records a source and synthetic-test audit of stop and target price
geometry. It is contract evidence only: the preserved historical artifacts do
not contain qualifying per-decision candidate-to-order geometry links, so this
packet makes no claim about historical action frequency or realized outcomes.

## Findings and implementation

- The environment passes `cost_model.point_size` to order construction as the
  instrument price increment (`simulation/environment/entry_order_runtime.py`).
- Targets apply front-running, round toward the entry to the configured price
  grid, then check side, minimum reward distance, and maximum room
  (`trading/orders/targets.py`).
- Structural stops previously applied their buffer without rounding the final
  price. A non-grid reference or buffer could therefore create an executable
  stop off the configured price grid. `stop_menu` now rejects non-finite or
  non-positive increments and rounds long stops down and short stops up, away
  from entry. Side and minimum-distance eligibility are checked after that
  rounding, and the audit row records the executable stop price
  (`trading/orders/stops.py`).
- Stop references obey the selected setup timeframe floor. Target references
  intentionally admit all configured timeframes unless a caller supplies
  `min_timeframe`; both paths reject explicit future confirmation timestamps.
  Missing historical action links mean source-side contract checks cannot prove
  which geometry a past policy selected.

The change preserves already grid-aligned prices. It can change an off-grid
buffered stop by at most one increment, always farther from entry. The selected
local campaign price distribution has not been rescanned by this packet, so no
frequency or economic impact is claimed.

## Verification

The focused order-geometry integration module passes 45/45 cases, including
long and short conservative grid rounding, invalid increment rejection, and
invalid trade-direction rejection. A broader 86-case batch also passes across
structural entry geometry, target reference chronology, cost-model bid/ask
direction, and environment/backtest execution quotes. Touched-path Ruff check
and format check pass. Captured outputs are stored beside this file.

Reproduce from the repository root with a compatible x86 environment:

```bash
.venv/bin/python -m pytest tests/integration/backtest/test_entry_levels.py -q
.venv/bin/ruff check trading/orders/stops.py tests/integration/backtest/test_entry_levels.py
.venv/bin/ruff format --check trading/orders/stops.py tests/integration/backtest/test_entry_levels.py
.venv/bin/python -m pytest tests/integration/backtest/test_entry_levels.py tests/integration/backtest/test_target_reference_contract.py tests/unit/trading/test_cost_model.py tests/integration/backtest/test_engine_execution_contract.py -q
```

This closes the source-contract portion of the structural stop grid audit. It
does not close the broader Stage D gate for empirical candidate geometry,
source-time causality across every feature producer, or historical
candidate-to-action attribution.
