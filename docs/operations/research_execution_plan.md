# Active research execution plan

This page is the operational queue for the current research program. It records
the last evidence-gate disposition and the conditions for any successor work;
it is not a general architecture guide or a personal academic-submission plan.

## Current gate disposition

The latest recorded selected-pair evaluation is the seed-50 P6 reanalysis
completed on 2026-10-24. The treatment completed the 2025 training interval
above the hard account floor but lost 2.154% over 987 trades. Its matched
control breached the $90,000 hard floor by $56.05 on 2025-10-28 and lost 10.06%
over 825 trades. Both arms were unprofitable, so the pair did not pass its
viability gate. The report-period evaluation also breached the hard floor for
both arms; that interval is exposed exploratory evidence, not a fresh
confirmation period.

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
  by focused tests and was used in the seed-50 reanalysis.

## Next actions and gates

1. Identify a specific mechanism in the failed matched results before changing
   the research configuration. Do not tune on the exposed 2026 interval as if
   it were untouched.
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

Preserve existing jobs, allocations, checkpoints, fingerprints, and evidence.
Follow [Triton operations](triton.md) before any compute request. Do not start
an expensive training run for a documentation or maintenance change.
