# QA: Stops, targets, multi-TP exits

**Status:** source claims checked after the owner’s corrections. Reviewed against source commit `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15; no tests or notebooks were rerun by QA.

## Source claims checked

1. Long and short swing stops require the swing on the protective side, add the buffer, and derive the target from the resulting risk distance: confirmed in `trading/risk/sizing.py::compute_sl_tp_long` and `compute_sl_tp_short`.
2. Disabled target selections fall back to TP3 and slot repair preserves a valid ordered subset: confirmed in `trading/orders/selection.py::decode_tp_selections`.
3. Active target fractions are renormalized and the input slot mask must have length three: confirmed in `trading/orders/selection.py::decode_tp_fractions`.
4. Target legs use initial size, cap at remaining size, and may reserve an EMA runner: confirmed in `trading/positions/multi_tp.py::target_close_size`, with the exception below.
5. Ambiguous OHLC stop and target touches use the stop-first simulator path, and a gap stop may fill at the open or worse: supported by `simulation/environment/exits/protective_levels.py`, `trading/execution/quotes.py`, and `tests/unit/simulation/test_environment/test_tp_execution.py`.

## Resolved corrections

- The Explanation and Contract table now state the zero-size fallback: runner retention is conditional, and `target_close_size` can close the full remainder.
- The ambiguous OHLC source citation now points to `simulation/environment/exits/protective_levels.py`; the test citation remains correct.

## Document and notebook checks

The hub has 150 lines and all required sections: Summary, Key terms, Explanation, Worked example, Tasks, Contract, Verify, Limits, Review procedure, Diagnostic cases, and Maintainer note. All 10 local Markdown links resolve; the hidden toctree notebook exists. The paired notebook has a title, Tier A/CPU/deterministic data/under-60-second/subject/owner metadata and forced MyST execution. Its one code cell has execution count 1, one saved output, and no saved error. The output reports long `(97.0, 106.0)`, short `(103.0, 94.0)`, slots `(0, 1, 2)`, and equal fractions.

The notebook is a synthetic contract example. It gives no market outcome or broker-fill evidence. `trading/risk/sizing.py` has dirty docstring-only changes relative to the pinned commit; this review does not certify other current dirty code.
