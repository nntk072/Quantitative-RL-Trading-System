# MT5 tick-quote coverage: strict audit versus reconstructed execution sensitivity

**Status:** experimental method. This document intentionally contains **no claimed new measurements**. The agent must run the full protocol and attach hash-verified evidence before any results enter the thesis.

## Research question

The previous conditional candidate-outcome study classified a large fraction of independent proposal/stop/target combinations as unresolved. That is a statement about a **strict local-source censoring protocol**, not an estimate of the percentage of missing market ticks, and not RL-policy performance. The strict raw-data audit requires every raw row in a minute to contain two valid quote sides and the raw row count to equal M1 `tickvol`.

MT5 documentation distinguishes a bid-price change from an ask-price change via `TICK_FLAG_BID = 2` and `TICK_FLAG_ASK = 4`; `MqlTick` and `CopyTicks` normally retain the last known unchanged side. Some local CSV exports instead leave the unchanged side blank. The production loader in `market_data/loading/ticks.py` causally forward-fills missing/nonpositive sides and rejects crossed or still-incomplete quote pairs. The exact CSV export process and authoritative feed are not verified here.

Primary vendor documentation:
- https://www.mql5.com/en/docs/constants/structures/mqltick
- https://www.mql5.com/en/docs/series/copyticks
- https://www.mql5.com/en/docs/trading

### Three explicitly different local-source protocols

| Protocol | Criteria for a source minute | Allowed interpretation |
|---|---|---|
| **strict_raw** (historical control) | Raw rows = M1 `tickvol` > 0, every raw row carries simultaneously valid bid and ask | Conservative source-export consistency. **Not** proven venue completeness. |
| **reconstructed_count_checked** | Each raw row survives into a valid production TickBook quote; at least one quote exists; raw rows = M1 `tickvol` | Sensitivity isolating missing-side reconstruction **while retaining count parity**. |
| **reconstructed_tickbook_only** | Each raw row survives into a valid production TickBook quote; at least one quote exists; M1 count parity not required | Exploratory sensitivity isolating whether count parity drives censoring. **Not** a reason to relax production execution checks. |

A usable reconstructed quote **is not** proof that both sides were directly observed in the same raw record, that the entire external tick history was exported, or that the MT5 server would have filled an order. The study does not redefine M1 `tickvol` as equivalent to raw `CopyTicks` row counts. A tick-volume mismatch requires separate investigation of export type, symbol feed, filters, clock, data roles and exact tick definition.

## Method and reproducibility

The new generator, `scripts/research/analysis/market_data/build_reconstructed_quote_coverage.py`, verifies immutable strict packet checksums, configured train-period/source hashes, symbol and training boundaries, and the same production TickBook identity used for the candidate-proposal ledger. It reads the post-preprocessing book in bounded time chunks, aggregates source-local minute counts, and writes **two new** complete coverage packets. It never writes into `evidence/research/tick_quote_coverage`.

The existing `scripts/research/analysis/evaluation/replay_candidate_proposal_outcomes.py` is then run three times, always with identical configuration, proposals, TickBook, execution parameters, stop/target enumerations and code:

1. Historical strict coverage path (fresh reproduction, **never replace the frozen control packet**).
2. `reconstructed_count_checked` coverage path (new scratch output).
3. `reconstructed_tickbook_only` coverage path (new scratch output).

These packets expose `minute_quote_coverage.csv` with the existing `quote_complete` column, so the production replay continues to consume the same interface. Each new CSV retains an additional `strict_raw_quote_complete` field plus the reconstructed source-specific columns. Metadata states the protocol and includes source/proposal/TickBook/input checksum identities. Neither production simulation nor RL training code is modified.

The comparator `scripts/research/analysis/evaluation/compare_quote_coverage_sensitivity.py` requires identical proposal populations, data identities, execution-parameter values and source-code SHA256s. It compares rows by unique `outcome_id`. **Already-classified strict outcomes must keep their status, fill/exit times, prices and net R exactly.** A violation aborts the comparison rather than being labeled an improvement. Report raw status transition tables, previously unresolved reasons, and counts made classifiable, with original denominators. Never infer a trading edge or a representative return from these conditional candidates.

## How to interpret possible results

- A large reduction in unresolved rows in the **count-checked** protocol would isolate the impact of treating a one-sided export record as incomplete even when the production TickBook can causally reconstruct it.
- A further reduction in the **TickBook-only** protocol would identify dependence on M1 tick-count parity, **not** prove that count mismatches are harmless.
- Persistently unresolved rows in all protocols can reflect unquotable market entries, out-of-session submission, actual feed gaps, invalid stop/target geometry, or administrative cutoffs; inspect reason codes and a stratified raw-tick trace.
- The comparison cannot establish broker-equivalent MT5 execution, queue priority, partial fills, stop/limit behavior under actual liquidity, DST correctness, or independent data completeness.
- A drop in unresolved outcomes does **not** automatically justify changing the simulator, reward, training policy, historical labels or thesis conclusions.

## Mandatory follow-up gates before promoting a result

1. Review export provenance and MT5 tick-side flags against official documentation. In particular, a blank unchanged side, an explicitly empty market book, and genuinely unavailable quote data are distinct. Verify source-row sequence at equal millisecond timestamps.
2. Explain the 40,330 training-minute raw tick-count mismatches using source files and actual M1 `tickvol` semantics, including examples where count is greater and smaller. Do **not** assume rows equal one MT5 tick-volume unit.
3. Cross-check at least 20 stratified changed outcomes and 20 unchanged outcomes against raw source events and production book events. Include both limit and market orders, missing-side patterns, count mismatches, source ties, session boundaries, and early/late months.
4. Run current repository unit tests, full-tree Ruff format/lint and full-tree Mypy before committing, per `AGENTS.md` and `.agents/rules/`.
5. Publish the three exact profile names, input hashes, candidate counts, unresolved status/reason counts, pairing invariants, and the limits of each interpretation. Check the historical PDF's **72.0%** against the current manifest's **71.6%** and do not silently replace a result from a different source snapshot.
6. Only if a **reproducible MT5-semantic contradiction in production execution** is found, create a separately justified simulator correction with deterministic before/after traces and both long/short and market/limit test coverage. Do not infer a simulator bug from quote-audit censorship alone.

## Output discipline

Write full Parquet and alternate coverage CSV packets in an isolated scratch directory, not in the tracked historical evidence directories. Keep every packet's `OUTPUT_SHA256SUMS`, `coverage_manifest.json`, `outcome_manifest.json`, and comparison report. If promoted into the repository after review, use a new versioned evidence directory and record the exact generating commit; preserve the original strict outputs, the original PDF number, and the historical report until a new thesis version explicitly supersedes them.


## 2026-11-08 full training-window sensitivity

A paired rerun from base 9c3b80d9e456930fd833c5e6b23a4935dfba453a used the same proposal ledger, production TickBook, execution code, config, and execution parameters across all three profiles. Strict historical evidence remains frozen and unchanged. The frozen packet was generated from commit 367561a7717a3367fbb280084ffcf0781f57119c and has different source/config hashes; the fresh strict rerun exactly reproduced its row/status counts and is the valid current-source pairing control.

| Profile | Resolved fills | Expired unfilled | Unresolved |
|---|---:|---:|---:|
| strict raw current-source replay | 273,350 | 29,701 | 764,680 |
| reconstructed count checked | 579,259 | 75,617 | 412,855 |
| reconstructed TickBook only | 930,453 | 129,299 | 7,979 |

The comparison invariant held: all 303,051 outcomes already completed by the strict current-source replay kept status, fill/exit times, prices, exit reason, and net R. Under count-checked reconstruction, 305,909 strict-unresolved rows became fill-resolved and 45,916 became expired unfilled. Under TickBook-only reconstruction, 657,103 became fill-resolved and 99,598 became expired unfilled. These are conditional fixed-entry censoring sensitivities, not policy value; resolved-only R is selection-biased. Strict unresolved rate is 71.617% (the frozen thesis value remains 72.0% until its source snapshot/protocol is reconciled).

Minute totals over 351,432 M1 rows: strict raw 258,106; count-checked reconstruction 311,102; TickBook-only 351,409. Raw tick-row versus M1 tickvol mismatches remain 40,330 minutes; tickvol is not assumed to equal exported tick rows.

Evidence is outside the repository at /home/nguyenl37/mt5_ftmo_fidelity_evidence_20261108_precommit3/. Fresh strict Parquet SHA256: 9372cfb2213d633f17c8b152151d8ff51f8e72d8875ca635f5293e2a3a0693e0. Count-checked comparison JSON SHA256: 844e1d805200829be9d99a7a296fe711d49bca03e2206d08df24ba985f418f85. TickBook-only comparison JSON SHA256: 50e8ddaf44c85fda1eca611ff1c9630218591918dcf9f2350bff63726e1df5a6. Reconstructed coverage CSV hashes: count-checked 8a2379b71ac3f589d60cfa50c13a0b9fb576382ec1b230c35303a37d1585eeda; TickBook-only 64041173efd182701e401702861165376fecd7c950184a2f744b99434136444a.

Synthetic resolver timing matrix: /home/nguyenl37/mt5_ftmo_fidelity_evidence_20261108_precommit3/protective_timing_matrix.json (SHA256 328ad5b29b17a3fd4dca2239016e9b95a53e1ba4e9c2cb308c4d4152e0be493c). It shows long/short stop gaps and target trade-through using one seeded legacy latency draw versus attached-order timing. It is not a full account replay or broker reference trace. No external MT5 terminal metadata or authoritative Strategy Tester account trace was available locally; broker parity remains unverified. Risk checks still occur at decision/market-event boundaries rather than every broker tick.
