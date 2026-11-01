# Result registry

This registry describes what the tracked evidence can support. “Reproduce” means recomputing a finding from frozen inputs; it does not mean retraining a policy.

| Result | Status | Source commit / data / config | Seed and checkpoint | Evidence | Level | Hardware / runtime | Notebook |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Exit-action semantics, frozen v2/v3 replay | Exploratory; no new training authorized by this evidence packet | Source `cbf7825170dee7f68ad578a19023e0847b11393f`; 2025 training partition; resolved config and bar/feature/tick identities in provenance | Seed 50; checkpoint digest is recorded, checkpoint file is not tracked | Common-entry CSV, cohort summaries, action/exit tables, provenance, analysis script snapshots | R2 for tracked cohort summaries and regenerated comparison; full replay remains unavailable from the tracked bundle | CPU; seconds for analysis | [Recompute cohort comparison](exit_action_semantics.ipynb) |
| Setup-conditioned replay (C/D) | Exploratory negative result | Evidence packet records training/testing summaries; complete per-arm ledgers are not tracked here | See evidence README for provenance scope | PNG reports and policy-metric JSON; underlying ledger/source artifacts are incomplete | R1; selected JSON metrics are inspectable, plots cannot all be independently rebuilt | Static evidence; replay requires unavailable artifacts | [Evidence explorer](setup_conditioned_evidence) |
| Deterministic environment trace | Software behavior demonstration | Repository source plus fixed synthetic bars and action sequence | No trained checkpoint | Expected fill, stop, equity, and reward asserted by the notebook | R2 software trace; not a research result | CPU; seconds | [Environment trace](environment_trace.ipynb) |

## Evidence gap vocabulary

No research result in this registry currently meets R3 or R4. The environment
trace is a reproducible software behavior check, not a frozen-checkpoint replay.

The [generated evidence sufficiency audit](evidence_audit) checks tracked files
against the claim scope below.

- **Complete:** all required identity and outcome artifacts for the stated reproduction level are present.
- **Partial:** some required artifacts are available, but the claim must be narrowed.
- **Missing:** a required identity or outcome artifact is absent.

The exit-action packet lacks full per-arm raw ledgers and raw tick data, so the notebook reproduces the tracked exact-common-entry cohort and its figure only. It does not claim to reproduce the complete closed-loop replay.
