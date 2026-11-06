# Selected policy trade lifecycle packet

Packet verification: **matched** across 4 partitions.

| Partition | Integrity | Decisions | Fills | Positions linked | Charge checks | Flat-close equity checks | Ending reconstructed balance |
|---|---:|---:|---:|---:|---:|---:|---:|
| `a4a_training` | matched | 49271 | 2020 | 987/987 | 1033 | 987 | 97845.68511833169 |
| `a4b_training` | matched | 53629 | 1678 | 825/825 | 853 | 825 | 89943.95098700203 |
| `a4a_testing` | matched | 54416 | 411 | 203/203 | 208 | 203 | 89998.38242865316 |
| `a4b_testing` | matched | 54560 | 413 | 203/203 | 210 | 203 | 89632.06425764649 |

Across the verified partitions, 2,218 positions link to fill events. The cashflow audit checks 2,218 completed closes while flat, validates net-PnL/allocated-entry-fee arithmetic for 2,304 close fills, and applies recorded payouts in event-time order.

Recorded source ledgers reconcile. This does not replay the policy, reconstruct open-position mark-to-market, validate historical candidate eligibility, or establish causal or economic superiority.

Input and report hashes are recorded in `evidence_manifest.json`; each partition retains its own source manifest.
