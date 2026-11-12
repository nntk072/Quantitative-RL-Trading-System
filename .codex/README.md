# Project Codex agents

This directory ships the project-scoped Codex setup so a fresh clone can use
the same roles and defaults. First trust the repository in Codex and open the
repository root; Codex then loads `.codex/config.toml` and `.codex/agents/`.
Do not copy project settings into user-home config. Existing `AGENTS.md` and
`.agents/rules/` remain authoritative. The coordination and file-ownership
source of truth is
[`../.agents/rules/agent-coordination.md`](../.agents/rules/agent-coordination.md).

```text
.codex/
├── config.toml
├── README.md
└── agents/
    ├── architect.toml
    ├── configuration-engineer.toml
    ├── data-engineer.toml
    ├── rl-engineer.toml
    ├── risk-engineer.toml
    ├── ci-gate-engineer.toml
    ├── qa-engineer.toml
    ├── independent-reviewer.toml
    ├── experiment-compute-engineer.toml
    ├── evidence-reporting-engineer.toml
    └── campaign-monitor.toml
```

Choose the Architect as the coordinator. It assigns only the specialist needed
for the task: Configuration, Data, RL, Risk, Experiment & Compute, Evidence &
Reporting, CI Gate, QA, or Independent Reviewer. The Campaign Monitor is a
reusable one-check role for a concrete live handle; assign only one check at a
time and reuse it after the prior result if the handle is still live. Profiles
contain the role boundaries; see the coordination rule before delegating.

The project default is two spawned agents plus the root (three concurrent
agents). Reasoning effort is chosen per task at spawn time (`low`, `medium`,
`high`, or rarely `xhigh`); profiles do not pin a default. For a justified
five-agent session on a host with enough slots, use
`codex -c agents.max_concurrent_threads_per_session=4` after recording the
independence and resource checks required by the coordination rule. The
setting excludes the root and cannot raise the host's actual limit. Keep this
project default in `.codex/config.toml`; do not set a global reasoning effort.

Agent profiles inherit the parent session's permissions and tools. Their role
boundaries are instructions, not access-control enforcement. Use separate Git
worktrees for parallel writers and keep the independent reviewer read-only by
workflow.

See [OpenAI's Codex custom-agent documentation](https://developers.openai.com/codex/subagents/)
for the current profile format.

The adoption and validation sequence is in the coordination rule. Validation
starts with TOML/schema checks and then uses one read-only smoke assignment per
implementation and gate role before code writers are run in parallel.
