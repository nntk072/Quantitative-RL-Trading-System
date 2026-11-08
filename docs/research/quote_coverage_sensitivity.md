# MT5 tick-quote coverage and candidate-outcome sensitivity

**Status:** completed training-window sensitivity study, 2026-11-08. The archived
historical evidence remains unchanged. The measurements below are conditional
fixed-entry replay diagnostics; they do not establish broker-tape completeness,
broker-equivalent fills, profitability, or RL policy performance.

## Research question

The historical candidate-outcome study reported roughly 72% unresolved outcomes.
The current frozen packet contains 1,067,731 conditional proposal/stop/target
combinations, of which 764,680 are unresolved (`71.617%`). The purpose of this
study was to determine how much of that censoring came from the local
quote-coverage rule, while holding the candidate population, TickBook, config,
execution parameters, and execution source fixed.

The answer is that the historical unresolved rate should not be interpreted as
evidence that about 72% of candidate trades were intrinsically unevaluable in
MT5. A large portion came from a conservative local rule that treated a raw row
as incomplete unless it carried a simultaneous finite bid and ask and also
required raw-row count parity with M1 `tickvol`.

## Four concepts that must remain separate

1. **Raw MT5 export events.** The local CSV contains source-ordered quote-change
   records. In the training window, flags `2`, `4`, and `6` are present.
2. **Locally reconstructed TickBook quote state.** Production loading preserves
   source-row order and causally carries forward an unchanged side. This is a
   reconstruction of the local exported event stream.
3. **M1 `tickvol`.** It is a useful source diagnostic, but the local evidence
   does not support treating it as the count of all exported quote-change rows.
4. **Broker tape / broker execution.** Neither raw-source reconstruction nor M1
   parity proves the complete broker tape, queue priority, partial-fill behavior,
   rejects, or broker-equivalent execution.

Official MT5 references used for semantic interpretation:

- https://www.mql5.com/en/docs/constants/structures/mqltick
- https://www.mql5.com/en/docs/series/copyticks
- https://www.mql5.com/en/docs/trading

## Raw-source findings

The final audit scanned `56,245,046` raw training rows from
`data/training/US100.cash_202412300105_202610162349.csv`
(SHA256 `631dbc13f17e6a974429cd00c87e9019b4f2c8f459fa9109e799c02863df5b23`).

| Raw flag | Rows | Local export interpretation |
|---|---:|---|
| `2` | 99,960 | Bid changed; ask field blank |
| `4` | 61,342 | Ask changed; bid field blank |
| `6` | 56,083,744 | Both bid and ask present |

There are `161,302` one-sided source rows and `56,083,744` valid simultaneous
two-sided rows. There are also `237,775` adjacent equal-millisecond source
events. Production TickBook construction preserves source-row order and carries
the unchanged side forward. That is appropriate for replaying this local export
format, but it is not proof that the export contains every broker event.

### M1 tick-volume diagnostic

The strict coverage packet contains `351,432` M1 minutes. Raw rows differ from
M1 `tickvol` in `40,330` minutes:

- raw rows > M1 `tickvol`: `40,303` minutes;
- raw rows < M1 `tickvol`: `27` minutes, including `23` minutes with zero raw
  rows and positive M1 `tickvol`;
- raw rows = M1 `tickvol`: `311,102` minutes.

A separate flag-alignment audit found that among the `351,409` minutes that
actually contain raw rows, M1 `tickvol` equals the count of bid-changing rows in
`351,402` minutes. For all `351,409` such minutes, non-bid rows equal ask-only
rows. In `40,300` of the `40,303` raw>M1 minutes, M1 `tickvol` equals the
bid-change row count.

For example, `2024-12-30 01:21:00` has `62` raw rows, M1 `tickvol=60`,
`60` bid-changing rows, and `2` ask-only rows. This is strong evidence that M1
parity is not a correctness law for this export.

### Genuine local source gap

There is one contiguous interval of `23` M1 minutes with positive M1 `tickvol`
and zero raw rows:

`2025-03-21 14:57:00` through `2025-03-21 15:19:00` (source wall clock).

Nearby anomalous minutes include `14:55`, `14:56`, `15:20`-`15:23`; a separate
raw<M1 minute appears at `2025-12-02 13:23`. The 23-minute zero-row interval is
a genuine local source gap and is not repaired by side carry.

## Three paired coverage protocols

| Protocol | Coverage rule | Interpretation |
|---|---|---|
| `strict_raw` | raw rows = M1 `tickvol` > 0 and every raw row has a simultaneous valid bid/ask pair | historical conservative control |
| `reconstructed_count_checked` | every source row survives into a finite non-crossed TickBook quote, at least one quote exists, and raw rows = M1 `tickvol` | isolates side reconstruction while retaining count parity |
| `reconstructed_tickbook_only` | every source row survives into a finite non-crossed TickBook quote and at least one quote exists; no M1 parity requirement | exploratory local-TickBook sensitivity |

All three fresh post-fix ledgers contain the same `1,067,731` outcome IDs and
use the same proposal ledger, production TickBook identity, config, execution
parameters, and execution-source hashes.

| Profile | Filled resolved | Unfilled expired | Unresolved |
|---|---:|---:|---:|
| `strict_raw` | 273,350 | 29,701 | 764,680 |
| `reconstructed_count_checked` | 579,259 | 75,617 | 412,855 |
| `reconstructed_tickbook_only` | 930,453 | 129,299 | 7,979 |

The unresolved ordering is monotone:
`764,680 >= 412,855 >= 7,979`.

### Paired status transitions

Strict to count-checked:

| Strict status | Count-checked status | Rows |
|---|---|---:|
| filled resolved | filled resolved | 273,350 |
| unfilled expired | unfilled expired | 29,701 |
| unresolved | filled resolved | 305,909 |
| unresolved | unfilled expired | 45,916 |
| unresolved | unresolved | 412,855 |

Strict to TickBook-only:

| Strict status | TickBook-only status | Rows |
|---|---|---:|
| filled resolved | filled resolved | 273,350 |
| unfilled expired | unfilled expired | 29,701 |
| unresolved | filled resolved | 657,103 |
| unresolved | unfilled expired | 99,598 |
| unresolved | unresolved | 7,979 |

The comparator verified that every outcome already completed under strict
coverage retained status, fill time, fill price, exit time, exit price, exit
reason, and net R under both reconstructed profiles. The mean R of newly
resolved rows is descriptive only (`-0.2340655085` for count-checked and
`-0.1565891283` for TickBook-only); it is selection-biased and must not be
interpreted as strategy return or policy value.

## Protective-order execution correction

The investigation also found a separate candidate-replay execution bug. After a
position was accepted with attached SL/TP levels, the replay could apply
request/network latency again when resolving the already attached protective
orders. Accepted protective levels are now treated as server-side for this
quote-based model and execute on the first source-ordered triggering quote.

Regression coverage includes long and short, market and limit entries with
`500 ms` entry latency. The replay manifest now records:

- `randomized_fill_latency_scope = "entry_requests_only"`;
- `protective_exit_execution = "server_side_attached_first_trigger_quote"`;
- `protective_exit_network_latency_ms = 0.0`.

For the strict full-data replay, the correction leaves all status counts,
fill times/prices, exit times, and exit reasons unchanged. It changes exit price
and net R for `2,037` filled outcomes because duplicate-millisecond events must
preserve the exact triggering source row instead of performing a later timestamp
lookup that can select another row.

The `2,037` changed rows comprise `1,163` market and `874` limit entries,
`1,069` long and `968` short outcomes, and `1,033` SL versus `1,004` TP exits.
Mean net-R delta is `-0.0078296993`, median `-0.0015540016`, minimum
`-0.4179104478`, and maximum `0.3652173913`. This correction is a simulator
fidelity fix for the conditional replay; it is not evidence of broker-equivalent
fills or profitability.

## Reproducibility identities

Fresh post-fix evidence root:

`/home/nguyenl37/mt5_ftmo_fidelity_evidence_20261108_postfix1/`

Key identities:

- proposal manifest:
  `80ca5e249ad302fe7f325d61f13d4b9d587e88ac187ef80b07f47f09f76e1662`;
- proposal Parquet:
  `0dd4a94288ffe714fa87b6e72b0c15112805d5eb0267f67d4a1a154b1609c1da`;
- production TickBook:
  `2e55f5d6e4100877e3cd0df8191438281b4b0afee9d82e657f475608067b2fbc`;
- strict coverage manifest:
  `48e03b4e07166e3baa12de92e1ee35a9c0aaf30f5b9c7932c36fcdd2b41ddb3b`;
- strict coverage CSV:
  `ab1f3533394a2197a65c36b550ccec40b7cb06e9b919bdd49d31f2b9541982f5`;
- fresh strict outcome manifest:
  `7c9755fa38607947de56e2ba37f35f9a086df0be9c218c3b3f64546a04410d38`;
- fresh strict outcome Parquet:
  `1b6611a898720ddd8f5ec2ec4c82f2bde093e257b0686aeff7da6f983688d899`;
- count-checked outcome manifest:
  `808a3fb6ec259d19c29bba69546c139de60b3be66cc147017add442e9b76d623`;
- count-checked outcome Parquet:
  `d339d525f806036a19cb5e50e9c199af1f2c8c4ca4787e159b635e6bcb3b040d`;
- TickBook-only outcome manifest:
  `83f34e5067a9e0da7c756d3c3a898417ab3e74880fdca5d93ab0cdc687c6f313`;
- TickBook-only outcome Parquet:
  `79d6fa258c80c15d197bf281382cc70c8f1ac31bcdce527c3af490f458e80113`;
- paired comparison JSON:
  `5db4ce8071e2a31873e4e4c897af93759331bc8bb7710d41d9416b43dd9d74bb`;
- final audit JSON:
  `2d9545ec7a09acc12c1f22612c7c75491b4e9653bb38e752df101a3704075a97`;
- protective-exit reconciliation JSON:
  `1dd0cbc8c1357918b0e70462e5ec1fb560e356dfcc57afe9e88d81cc49bad37e`.

Each evidence subdirectory contains its own `OUTPUT_SHA256SUMS`. Historical
tracked evidence was not overwritten.

## Simulator verdict and limits

The production TickBook/event reconstruction is reasonable for reconstructing
the local MT5 export stream: source order is preserved and the unchanged side is
carried causally. The historical strict coverage rule was too conservative for
that local export. The candidate replay also contained a real protective-order
latency/trigger-row fidelity bug, which is corrected and regression-tested.

The simulator still does not reproduce broker queue priority, partial fills,
rejects, exact broker-tape completeness, continuous account-server risk
monitoring, or broker-exact execution. The coverage sensitivity therefore
supports a statement about **local missing-data censoring**, not broker
equivalence.

No RL agent was trained as part of this study.

## Thesis-safe interpretation

> The historical ~72% unresolved conditional-outcome rate should not be
> interpreted as evidence that 72% of candidate trades were intrinsically
> unevaluable in MT5. A substantial portion arose from a conservative local
> coverage rule that treated one-sided MT5 quote-change records as invalid
> unless every source row contained a simultaneous bid/ask pair. Production
> TickBook reconstruction preserves source order and carries forward the
> unchanged side, substantially increasing locally reconstructable quote
> coverage. This reduces missing-data censoring under sensitivity assumptions,
> but does not establish broker-tape completeness, broker-equivalent fills,
> profitability, or RL policy performance.

Separately:

> The candidate replay also applied execution latency inconsistently to already
> attached protective SL/TP orders. The corrected replay treats accepted
> protective orders as server-side and executes them on the first source-ordered
> triggering quote. This changes 2,037 strict-replay exit prices/net-R values
> under duplicate-millisecond source events while leaving outcome-status counts
> unchanged.
