# Active research execution plan

This page is the operational queue for the current research program. It records
the last evidence-gate disposition and the conditions for any successor work;
it is not a general architecture guide or a personal academic-submission plan.

## Current gate disposition

The latest recorded selected-pair evaluation is the seed-50 P6 reanalysis
completed on 2026-10-24. The treatment recorded 987 positions and −2.154%,
with aggregate ledger equity ending at $97,845.69. Its strict zero-breach
risk-survival gate failed on one `daily_loss` event on 2025-03-06. The
evaluation nevertheless completed the configured data split. Its matched
control recorded 825 positions, −10.056%, aggregate equity $89,943.95, and two
breach events: `daily_loss` on 2025-03-06 and `max_drawdown` on 2025-10-28.
That evaluation also completed the data split; its aggregate endpoint was
$56.05 below the $90,000 floor. Both arms failed the declared survival gate.
At the pinned run source, `trading_policy.mode=legacy` accumulated gross
negative closed-trade P&L without offsetting winning closes or measuring net
daily equity. The March `daily_loss` events therefore establish failure of
that configured legacy counter, not an FTMO-style net daily-equity breach. The
close ledgers show gross negative closes of $5,017.66 / $5,399.25 and net
realized close P&L of −$3,004.28 / −$3,389.32 for A4A / A4B through those
events. A4B's later `max_drawdown` event is separate. The stored `fail_time` is
the first breach timestamp, not the episode end. The report-period evaluation
also breached the hard floor for both arms; that interval is exposed exploratory
evidence, not a fresh confirmation period.

Do not resume or duplicate the failed run, start a 20M-step continuation, or
start the corrected five-seed comparison while P6 is failed. A successor needs
a specific, evidence-supported change to a scientific factor, a newly
registered matched configuration, and a predeclared acceptance rule. Preserve
the failed results and their run identities as historical evidence.

## Period roles and fixed inputs

- The recorded training period is 2024-12-30 through 2025-12-31.
- The inspected reporting period is 2026-01-01 through 2026-10-16. Treat it as
  exposed exploratory/report-only data; a rerun on the same dates cannot make
  it a fresh holdout.
- The M1 sequence is the policy timeline. Supplied M3–D1 bars and bid/ask ticks
  remain available to configured features and execution.
- Retain all supplied bars. Date-level scheduled-session context is available
  from the first bar; several near-full sessions and the report-period date
  shapes have not been classified against an authoritative instrument
  calendar.
- Any future comparison must preserve matched data, features, action meaning,
  costs, risk rules, training budget, seed, starting capital, and evaluation
  window, or explicitly identify the difference and limit the claim.

## Completed evidence gates

- **Inputs and split:** chronological train/report identities and split-cache
  provenance are recorded in run manifests. Session schedule context reaches
  training and reanalysis from each date's first bar. Feed-specific calendar
  completeness remains a documented limitation.
- **Execution:** the selected run uses seeded 0–30 ms arrival latency and the
  first eligible bid/ask tick after order arrival; missing required tick input
  fails closed.
- **Recovery:** deterministic checkpoint recovery was verified. The associated
  smoke did not pass its training risk-survival gate and is not viability
  evidence.
- **Screen and selection:** the 18-variant corrective screen is terminal and
  exploratory. The predeclared matched pair is retained; the pair's later P6
  evaluation did not pass.
- **Reanalysis:** chronological non-episodic daily-loss breaches stop trading
  for that session and allow the rollout to continue. Maximum-loss and
  trailing-drawdown breaches remain annual failures. This behavior is covered
  by focused tests and was used in the seed-50 reanalysis. The seed-50
  `legacy` mode's daily counter sums negative closes without offsetting gains;
  it must not be treated as net daily-equity or FTMO daily-loss semantics.

## Next actions and gates

1. Resolve and version the daily-loss/account contract for future research;
   validate deterministic equity, winning-close, losing-close, open-P&L, and
   reset traces (including the intended 00:00 CE(S)T anchor if targeting FTMO
   2-Step semantics) plus training/live parity. The historical legacy result stays
   immutable and cannot establish net daily-equity survival. Identify a
   specific economic mechanism before changing the research configuration.
   Do not tune on the exposed 2026 interval as if it were untouched.
2. Register any proposed successor with immutable data, source, config,
   feature/cache, checkpoint, and run identities. State the control, treatment,
   changed factor, evaluation window, risk gate, and action-mode/seed rules in
   advance.
3. Run a bounded P6 pair only after the new protocol is complete. Advance to
   multi-seed comparison or cost stress only if the pair passes its declared
   gate. Keep prior failed runs unchanged.
4. Freeze a consolidated result report only after the corrected P6 evidence
   and any authorized successor comparison are complete. Report negative and
   inactive outcomes, period exposure, uncertainty, and unresolved feed
   limitations alongside performance.

P8 independent review was waived for the prior deliverable; no independent
review is claimed. Reopen it only if requested or needed to support a claim.

## Evidence and execution safeguards

Historical reports and machine records are preserved in the
[research evidence archive](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/archive_2026/README.md).
Run directories remain under `outputs/experiment_runs/`; they are immutable
evidence, not an alternate task queue. The documented P6 trade ledgers and
monthly analyses are in
[P6 monthly dynamics and decomposition](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/archive_2026/evidence/p6_monthly_entry_exit_20261025/p6_monthly_entry_exit_decomposition.md)
and [P6 training dynamics](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/archive_2026/evidence/p6_monthly_entry_exit_20261025/p6_training_dynamics_control.md).

As of 2026-11-01, the local scratch campaign
`outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/`
was found with its source snapshot, resolved configs, per-arm provenance,
final checkpoints, and train/test trade ledgers. Its campaign fingerprint
matches the paired-decomposition evidence. The recorded training outcomes are
987 A4A positions at −2.154% and 825 A4B positions at −10.056%; both failed
the strict zero-breach survival gate, and report-period replays remain
exposed, report-only results. Both training evaluations reached `data_end`.
A4A's sole recorded breach was the legacy gross-loss `daily_loss` counter;
A4B recorded that event and a later `max_drawdown`. The March events do not
establish net daily-equity breaches. The stored `fail_time` is each arm's first
breach, not its episode end. A4A's aggregate ledger ends above $90,000, but
that does not erase its historical configured-gate failure. The semantics and
close-level reconciliation are documented in the release snapshot's P6 risk
gate trace. This scratch recovery does not change the tracked-packet
R2 registry grade: 10/10 manifest-listed per-arm artifact hashes match, and
all 39 manifest-listed input paths are present. The selected campaign input
audit verified 8,162,529,858 bytes against its SHA-256 manifest. The separate
full local-data inventory hashes 140 declared paths resolving to 64 distinct
files (16,325,449,095 unique bytes); all 38 overlapping campaign data files
match their observed hashes. The machine-readable checksum report is in
`evidence/research/releases/negative-evidence-readiness-2026-11-01/RAW_DATA_SHA256_MANIFEST.json`.
Per the user's scope, provider/license records were not investigated; no raw
data is bundled and no rights claim is made. No checkpoint replay was run. The
scan found missing/non-finite required bid/ask values in all four tick files,
adjacent timestamp ties, and 23 training M1 minutes without ticks for each
instrument. Minute overlap does not establish within-minute quote availability
or schedule correctness. Detailed scan job 21340127 classified
329,471 ties as 328,918 changed-quote pairs, 553 pairs with a missing quote,
and zero identical-quote pairs. It counted 371,390 rows with one required
bid/ask side missing or non-finite, and none with both sides missing. No
timestamp parse failures, adjacent reversals, nonpositive or inverted quotes,
or invalid OHLC rows were observed. This does not determine within-tie
chronology or the authoritative feed clock/session calendar. A durable
release manifest must preserve this external-artifact boundary. The separate 20M-step
`p6_entry_fsm_viability_seed50_train2025_20261021_scratch1` campaign has a
different fingerprint and only seven training positions per arm; do not
conflate it with the selected pair or resume it.

The current and selected-campaign tick-builder source blocks independently
carry bid and ask sides across missing values before retaining valid pairs.
Thus an executable row may combine a new side with a value from an earlier
source row; this does not establish simultaneous quote availability. The
current tick builder file hash differs from the selected campaign's source
hash, although this preprocessing block is identical. Detailed source and
quote-quality evidence is in
`evidence/research/releases/negative-evidence-readiness-2026-11-01/DATA_PROVENANCE_AND_ACCESS.md`.

## Release readiness snapshot

The 2026-11-01 release candidate is recorded at
`evidence/research/releases/negative-evidence-readiness-2026-11-01/README.md`.
It is **blocked**, not ready. The expanded current-source scoped suite passed
153 tests, skipped one accelerator-only test, and emitted two PyTorch
nested-tensor warnings. The hybrid actor's CPU checks passed; its CUDA/ROCm
round-trip test was skipped because no accelerator allocation was available,
and no short GPU job was requested. The latest strict Sphinx result and the
remaining release checks are recorded in
`evidence/research/releases/negative-evidence-readiness-2026-11-01/FINAL_READINESS_REPORT.md`.

The archived real-data feature-prefix and tick-quality reports are tied to
older source hashes. The 39 selected-campaign inputs have been rehashed and
structurally scanned; this is not a full data inventory or complete
timeframe-parity audit. At the user's direction, continue using only data
already present in the checkout; do not seek or add an external export. The
user-reported source is FTMO Demo; provider and license details are outside the
current local-analysis scope, and no raw input is included in the release.
Schedule ambiguities remain unresolved. No training or report-period promotion
is supported by this snapshot. The release package preserves the negative P6
result and lists the specific gates that remain open.

Preserve existing jobs, allocations, checkpoints, fingerprints, and evidence.
Follow [Triton operations](triton.md) before any compute request. Do not start
an expensive training run for a documentation or maintenance change.
