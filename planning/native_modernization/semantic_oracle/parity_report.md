# SEMANTIC-ORACLE parity report

Branch `feat/semantic-oracle`, base `origin/main-native` at `a3b3e442`. Fixture version 1.0.0 (digest in `fixtures/MANIFEST.json`).
Python: `/scratch/work/nguyenl37/Quantitative-RL-Trading-System/.venv-x86/bin/python` (3.12.14, pytest 9.1.1, hypothesis 6.170.14, numpy 2.2.6), `PYTHONPATH` set to the worktree, `OMP_NUM_THREADS=2`. No network, no broker, no orders, no Slurm.
Raw logs: `logs/agents/quantitative_trading_engineer/2026-11-26_semantic_oracle/` (git-ignored; the exact lines are reproduced below).

## 1. Required checks (exit codes)

Files touched by this package are the three new test modules. No source module under `trading/`, `simulation/`, `market_data/` or `config/base/` was changed.

| # | Command | Exit | Result |
|---|---|---|---|
| 1 | `ruff format --check` on the three new test modules | 0 | `3 files already formatted` |
| 2 | `ruff check` on the three new test modules | 0 | `All checks passed!` |
| 3 | `python -m mypy` on the three new test modules | 0 | `Success: no issues found in 3 source files` |
| 4 | `python -m pytest -q -p no:cacheprovider -o addopts= -rxX` on the three new modules, `test_semantic_oracle_costs.py`, `test_semantic_oracle_limits_sizing.py` and `tests/unit/research_tools/test_study_audits.py` | 0 | `137 passed, 7 xfailed in 24.15s` |
| 5 | `python -c` load of the fixture JSON | 0 | `fixture-json-valid semantic-oracle-fixtures.v1` |
| 6 | `sha256sum` of the fixture | 0 | `d0e3f9961ce6418634595f8e8a59e689ffc2189884fe274e5cc013e132736e22` (equal to `MANIFEST.json`) |

The seven xfails are the strict defect cases listed in section 3. Each xfail prints its classification as its reason.

Study-catalog audit. The first run of `tests/unit/research_tools/test_study_audits.py` failed on the inventory check. The fixes were registrations only, in three profiles, and each was made because the audit named it:

- `config/studies/profiles/market_data.yaml`: `caller_paths` gained the two trading test modules that import `market_data`.
- `config/studies/profiles/trading.yaml`: `api_paths` gained `trading/positions/multi_tp.py` and `trading/risk/execution_reserve.py`. `caller_paths` gained the two trading test modules.
- `config/studies/profiles/simulation.yaml`: `caller_paths` gained the env causality module and the two trading test modules.

Failure before the registrations, verbatim:
`StudyCatalogError: market_data API/caller inventory mismatch: missing_api=[], extra_api=[], missing_callers=['tests/unit/trading/test_semantic_oracle_fixture_replay.py', 'tests/unit/trading/test_semantic_oracle_properties.py'], extra_callers=[]`

After the registrations, `4 passed in 8.74s` (exit 0) on the audit module alone.

Development-stage replays before the final battery (same tests, earlier edit state):

- Fixture replay on first run: `84 passed, 5 xfailed`. The manifest test failed only because `MANIFEST.json` did not yet exist. Created, then `85 passed, 5 xfailed`.
- With `--runxfail`, the five defect cases fail for the stated reasons (section 3).
- Hypothesis properties: `15 passed in 8.15s`.
- Environment causality: `8 passed in 4.09s`, after two test-design fixes (section 5). `9 passed in 3.98s` after the no-trade test was added.

## 2. Hypothesis and environment evidence

Property tests (`tests/unit/trading/test_semantic_oracle_properties.py`, 15 tests, `max_examples=200`, `derandomize=True`):

- Adverse slippage never improves the transacted side; undo restores the quote.
- Market fill lies between bid and ask; stop fill never beats the stop level.
- Sized lots fit the all-in budget (stop risk plus execution reserve) and sit on the lot grid.
- `compute_lots` output is clipped to the broker range.
- Cash and equity conservation over any partition of exits (ledger identity checked after every close and mark).
- Partitioned close equals single close at one quote (partition invariance).
- Mark-to-market never changes balance.
- Daily breach equals strictly-below-floor (integer USD values).
- Log-growth rewards telescope to one transition (batch vs single). Equity-delta rewards are additive.
- FTMO day is independent of the source zone. Session mask is per-bar partition invariant and invariant to whole-day shifts.
- Event-keyed RNG stream is independent of other keys drawn first.

Environment tests (`tests/unit/simulation/test_environment/test_semantic_oracle_env_causality.py`, real `TradingEnv`, 120-bar synthetic tape):

- Ordering keys: valuation index advances by one per step and is unique.
- Reset determinism with the same seed.
- Batch vs single: two instances stepped alternately equal the solo traces.
- Causality: perturbing OHLC of bars at or after a cut leaves every output valued before the cut unchanged (Hypothesis over cut 62..100, four perturbation columns, four deltas).
- Unused fields: volume, tick volume and `vol` changes leave the full trace identical.
- Append-future: a shorter tape reproduces every output except its own data-end output (Hypothesis over lengths 70..110).
- Data-end truncation: `truncated=True`, `terminated=False`, final valuation index equal to the tape length.
- Characterization: the data-end observation differs from the in-episode observation at the same index (open item E1).
- No-trade action 0 over 30 steps: no trade, no position, equity constant at 100000.0, reward 0.0.

Probe outputs that established the timing contract (run before the tests were written, with features sliced consistently):

```
cut 61 first differing step index 0 (step i decision bar 60 ) n 40 40
cut 64 first differing step index 3 (step i decision bar 63 ) n 40 40
cut 70 first differing step index 9 (step i decision bar 69 ) n 40 40
```

Read with valuation index `v_j = 61 + j`, these say output `j` first changes when its valuation bar is perturbed, as the contract in section 3 of `semantic_contracts.md` states.

Test-design hazard found during probing: `_make_features(bars)` draws from a shared RNG sized by the number of rows, so features for a shorter tape are not a prefix of the longer tape's features. Prefix comparisons must slice features (`features.iloc[:L]`), not regenerate them. Early probes that regenerated features reported a false causality failure. The final tests slice.

## 3. Disagreements and reproducers (exact outputs)

Reproducers were run in the worktree with the `.venv-x86` interpreter.

```
reserve lots 0.29: 0.28
0.29/0.01 = 28.999999999999996 floor: 28.0
zero-leg close size: 0.01 (position size 0.01)
tp1 close of 0.125 lot leg: 0.12 round(0.125,2)= 0.12
after open: balance 9998.0 equity 10000.0 open_pnl 0.0
fill dir 0: 99.5
```

Defect list (strict xfail, so each stays visible and fails loudly if fixed without a version bump):

| ID | Classification | Exact observed value | Fixture |
|---|---|---|---|
| C1 | source defect (fail-open invalid side) | `CostModel().fill_price(99.5, 100.5, 0)` returns `99.5`, expected ValueError | QF-07 |
| C2 | source defect or docstring defect (owner to choose) | `CostModel(slippage_points=0.5).fill_price(99.5, 100.5, 1)` returns `100.5`, expected `101.0` | QF-08 |
| C3 | source defect (zero-leg full exit) | `target_close_size` returns `0.01` for a 0.01 position with fraction 0.3 | TG-05 |
| C4 | source defect, latent at broker API; env compensates | `Broker.open_position` with commission 2.0: balance `9998.0`, equity `10000.0` | AC-A2 |
| SZ-14 | documented alternative semantics with undocumented one-step under-size | budget 2.9 gives `0.28`, hand value `0.29` | SZ-14 |

Characterizations (passing, labelled in the fixture and in `semantic_contracts.md` section 5): `compute_lots` zero budget returns min lot (SZ-08); target leg 0.135 rounds to 0.14 under undeclared round-half-even (TG-06); `spread_points` is price units (QF-04); event-keyed RNG bit stream (RN-04, golden, not hand-calculated); inclusive session endpoints (SS-01); data-end observation differs (E1).

Source changes made: none. C1 to C4 and SZ-14 need owner decisions, and changing `fill_price`, `target_close_size` or `open_position` would alter API or trading behavior, which the plan requires to carry a new version and new evidence identity.

## 4. Mutation check (injected source faults, then restored)

Method: one text substitution at a time in a production file, the three new test modules run, then the file restored from its saved text. `git diff --stat HEAD` was empty afterwards. The run used the test set before the no-trade test was added and before ruff formatting. Raw log: `logs/agents/quantitative_trading_engineer/2026-11-26_semantic_oracle/mutation_check.log`.

```
M1 trading/execution/quotes.py KILLED | 3 failed, 105 passed, 5 xfailed in 9.97s
M2 trading/risk/sizing.py KILLED | 2 failed, 107 passed, 4 xfailed in 11.77s
M3 trading/risk/guardrails.py KILLED | 1 failed, 107 passed, 5 xfailed in 9.75s
M4 trading/account/limits.py KILLED | 2 failed, 106 passed, 5 xfailed in 13.38s
M5 trading/positions/multi_tp.py KILLED | 2 failed, 106 passed, 5 xfailed in 17.50s
M6 simulation/environment/episode_runtime.py KILLED | 1 failed, 107 passed, 5 xfailed in 24.89s
M7 trading/execution/broker.py KILLED | 6 failed, 102 passed, 5 xfailed in 20.43s
M8 trading/execution/costs.py SURVIVED | 108 passed, 5 xfailed in 13.52s
restored
```

Mutants: M1 flips the opening-long slippage sign; M2 turns the lot floor into a ceiling; M3 makes the daily breach non-strict; M4 adds instead of subtracts the daily loss from the floor; M5 rounds the TP leg to one decimal; M6 fills one bar late (at `t + 2`); M7 adds 0.5 USD per lot to every realised close; M8 maps direction 0 to ask.

M8 survives on purpose. It is equivalent on valid sides (+1 and -1) and changes behavior only for direction 0. That branch is defect C1, whose strict xfail does not count as a kill. Recorded as an unkilled equivalent on the valid domain and a known open defect on the invalid one.

## 5. Test-design corrections made during the run (not golden changes)

- The causality cut range was 61..100 in the first draft. Cut 61 is vacuous because the first output is valued at bar 61, so there was no output to check. The range is now 62..100, with that reason in the docstring.
- The first environment tape had 48 actions, which is shorter than the valuation range. The action tape is now 80 entries and `_run` allows 200 steps.
- Hypothesis arguments that carried the large baseline trace produced a 38 kB repr warning. Traces are now cached and not passed as arguments.

None of these changed any expected value. One fixture expectation was corrected during authoring, before the first replay run and before `MANIFEST.json` was written: QF-17 bid was first typed as `101.4` and is `102.0` (`short gap up: ask = 102.6; bid = 102.6 - 0.6 = 102.0`). The digest in `MANIFEST.json` is of the corrected file. No expected value has changed since the digest was written.

## 6. Not run and not claimed

- Native backend parity: `qrl_native` is not importable in `.venv-x86` (`ModuleNotFoundError: No module named 'qrl_native'`). `native/domain` Rust tests were not run. No backend result is claimed.
- Captured broker events: not in the tree and not fabricated. Not required for offline acceptance.
- Pending, cancel and replace; candidate mask and geometry; env-level ambiguous both-level bars; breach-latch persistence across sessions: not covered in this package (gaps G1 to G4 in `semantic_contracts.md` section 7).
- Full repository gates (full-tree ruff, full-tree mypy, `./tools/check unit`) were not run. The task scope was the touched files and the scoped tests listed above.
