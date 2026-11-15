# QA: Trade setups

- **Status:** passed
- **Reviewer:** `qa_engineer`
- **Source revision:** `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` plus current working tree
- **Date:** 2026-11-15

## Source claims

| Claim checked against current hub | Source | Result |
|---|---|---|
| Catalog has six ideas, nine timeframes, two directions | `decisioning/trade_setup.py::TRADE_SETUP_IDEAS`; `TRADE_SETUP_TIMEFRAMES`; `TRADE_SETUP_DIRECTIONS` | PASS |
| No-trade zero plus 108 executable candidates form 109 categories | `decisioning/trade_setup.py::NO_TRADE_ID`; `_catalog`; `TRADE_SETUP_CATEGORY_COUNT` | PASS |
| Eligibility reads exact idea, timeframe, and direction feature | `features/context/trade_setup_candidates.py::active_trade_setup_candidates` | PASS |
| Mask is fixed-width with no-trade always eligible | `features/context/trade_setup_candidates.py::trade_setup_candidate_mask` | PASS |
| Event identity retains missing and conflicting source-time statuses | `features/context/trade_setup_candidates.py::trade_setup_candidate_event_identities` | PASS |

## Artifact and structure

`examples/trade-setups.ipynb` declares Tier A, CPU, bundled/deterministic data, and forced execution. Its code cell has saved execution count 1, one result output, and no error output. Saved output round-trips candidate 30 and enables only IDs 0 and 30. The hub has 150 lines, all 11 required sections, its notebook toctree and contract, and 9/9 resolving Markdown links.

## Evidence limit

The invented signal row checks catalog and mask mechanics, not source-event identity, strategy performance, or locked OOS generalization. Saved output does not prove a fresh run or runtime.
