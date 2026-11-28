# Execution, fill, and cost contract

**Status:** draft
**Source of truth:** `trading/execution/broker.py`; `trading/execution/costs.py`; `trading/execution/quotes.py`; `simulation/environment/accounting/trades.py` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Fill inputs and outputs

| Field | Unit | Meaning |
|---|---|---|
| `quote` | Price pair | `(bid, ask)`; finite, positive, `ask >= bid` |
| `direction` | Signed integer | `+1` long or `-1` short |
| `lots`, `size` | Lots | Open quantity or optional partial close quantity |
| `contract_size` | Units per lot | Multiplier in margin and gross PnL |
| `commission_per_lot` | Account currency per lot per side | Explicit fee charged at open and close |
| `fill_price` | Price | Executable ask/bid determined by trade side |
| `pnl` | Account currency | Realized close gross PnL less close commission |
| `fill_quote_source` | Provenance label | Observed tick, bar, or derived protective level |

## Transitions

- Invalid quote raises before account mutation (`trading/execution/broker.py`).
- Open rejects invalid side, nonpositive lots, or insufficient margin (`trading/execution/broker.py`).
- A long opens ask and closes bid; a short opens bid and closes ask (`trading/execution/broker.py`).
- `total_cost` is commission only; spread lives in the quote (`trading/execution/costs.py`).
- Partial close caps at current size and books only that leg (`trading/execution/broker.py`).
- Protective bar fill may be worse than stop on a gap (`trading/execution/quotes.py`).

See the [subject guide](../../subjects/C_trading_risk_execution/execution-fills-costs.md), the [risk/execution reference](../risk_and_execution.md), and the [integration module guide](../../modules/integrations.md). Live broker equivalence is **not measured**.
