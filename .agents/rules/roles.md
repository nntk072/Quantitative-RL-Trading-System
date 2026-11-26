---
trigger: model_decision
description: "Use when assigning a subagent role, adding a role, or writing a delegation brief."
---

# Subagent roster

This file is the roster for delegation. Each role has one row. The Owns column
repeats the paths in the Canonical roles table of `delegation.md`; a change to
one must change the other in the same commit. A new role is added by the steps
under Adding a role, so the workflow rules do not need rewriting.

Columns:

- **Workflow mode.** `pr` when the output lands on `main-native` or `main`
  through a pull request. `local` when the output stays in scratch, research,
  or read-only work. A brief sets the mode; this column gives the default.
- **May push.** Feature branches only, and only when the coordinator authorizes
  it. `none` for roles that make no commits.
- **May merge.** Never unless the lead names the PR.
- **Read-only.** `yes` means the role edits no file.
- **CI watch.** `yes` means the role's open PRs get the CI watcher's failure
  messages.

## Subagent roster

| Role id | Owns (paths) | Workflow mode | May push | May merge | Read-only | CI watch | Notes |
|---|---|---|---|---|---|---|---|
| `architect` | Cross-domain contracts, decomposition, integration, acceptance; assigned coordination docs | pr | feature branches only, when authorized | never unless the lead names the PR | no | no | Coordinator. Drives the PR flow and merges only a PR the lead names. Never signs off independent review. |
| `ml_engineer` | `configuration/`, `config/`, `decisioning/`, `models/`, `learning/`, `training/`, `experiments/`, `compute/`, assigned tests | pr | feature branches only, when authorized | never unless the lead names the PR | no | yes | No trading or data meaning, risk semantics, or protocol decisions. |
| `data_scientist_engineer` | `market_data/`, `features/`, directly owned tests | pr | feature branches only, when authorized | never unless the lead names the PR | no | yes | No trading interpretation, account, or execution code. |
| `quantitative_trading_engineer` | `trading/`, `simulation/backtest/`, assigned execution and risk files in `simulation/environment/`, trading tests | pr | feature branches only, when authorized | never unless the lead names the PR | no | yes | No data pipeline, policy, or optimizer code. |
| `evidence_reporting_engineer` | `artifacts/`, `evaluation/`, assigned reporting, documentation structure, build and inventory tooling | pr | feature branches only, when authorized | never unless the lead names the PR | no | yes | Does not accept claims; the architect does. |
| `ci_operation_engineer` | `.github/workflows/`, `tools/check*`, CI tests and config | pr | feature branches only, when authorized | never unless the lead names the PR | no | yes | Source fixes go to the owning specialist. Workflow reruns need authorization. |
| `resource_monitoring_engineer` | Read-only resource inspection; approved environment setup; approved disposable-file cleanup; assigned resource helpers | local | none | never unless the lead names the PR | no | no | Edits only approved setup and cleanup, never source, checkpoints, logs, or evidence. Slurm is requested only by the coordinator. |
| `qa_engineer` | Assigned test-only edits and independent test design | pr | feature branches only, when authorized | never unless the lead names the PR | no | yes | Mode `pr` when it adds landing tests. The brief sets `local` for test design that lands nothing. |
| `independent_reviewer` | None; read-only review | local | none | never unless the lead names the PR | yes | no | Starts after the implementation exists. Reviews, never edits. |

## Adding a role

A new role gets no work until the lead approves it and its row is in the
roster above. A role with no lead approval or no roster row is not dispatched.
Record the new role with this template, in its roster row and in the Canonical
roles table of `delegation.md`:

- **Role id:** lowercase snake_case, the name used in `logs/agents/<role_id>/`.
- **Owned paths:** list them. A path already owned by another role needs one
  named writer from the lead; every other role sees it read-only.
- **Workflow mode:** `pr` or `local`, with the default.
- **Push and merge rights:** feature branches only, when authorized; merge never
  unless the lead names the PR.
- **Read-only flag:** `yes` or `no`.
- **CI-watch flag:** `yes` when its open PRs get CI failure messages.
- **Lead approval:** the lead's approval, recorded before the role's first brief.

## Brief fields

Every brief carries these fields, in addition to the fields listed under
Assignment and handoff in `delegation.md`:

- **`role_id`:** one id from the roster above.
- **`workflow`:** `pr` or `local`. The lead sets it for each task. When the lead
  leaves it out, the roster default applies. Scratch and research work uses
  `local` with any role.

Every brief starts with the push-access and `gh` preflight. A `local` brief
opens no PR and pushes nothing.
