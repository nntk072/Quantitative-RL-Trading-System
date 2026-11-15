# QA: Order blocks and premium/discount

- **Status:** passed
- **Reviewer:** `qa_engineer`
- **Source revision:** `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` plus current working tree
- **Date:** 2026-11-15

## Source claims

| Claim checked against current hub | Source | Result |
|---|---|---|
| Close-through uses prior confirmed swing levels | `features/context/order_blocks.py::_build_order_block_features` | PASS |
| Bullish and bearish zones search opposing source candles | `features/context/order_blocks.py::_build_order_block_features` | PASS |
| Age and distal-edge close expire zones | `features/context/order_blocks.py::_build_order_block_features` | PASS |
| Retest confirms on a later row after intersection | `features/context/order_blocks.py::_build_order_block_features` | PASS |
| Premium/discount routes session ranges and separates raw levels | `features/context/premium_discount.py::build_pd_context_features`; `PD_CONTEXT_FEATURE_COLUMNS`; `PD_CONTEXT_RAW_COLUMNS` | PASS |

## Artifact and structure

`examples/order-blocks-and-premium-discount.ipynb` declares Tier A, CPU, bundled/deterministic data, and forced execution. Its code cell has saved execution count 1, one result output, and no error output. Displayed tail rows have inactive order blocks and premium flags. The hub has 150 lines, all 11 required sections, its notebook toctree and contract, and 8/8 resolving Markdown links.

## Evidence limit

The synthetic example checks columns, index, and exclusive flags; its displayed rows do not show a formed or retested block. Saved output does not prove a fresh run, runtime, predictive value, or tradability.
