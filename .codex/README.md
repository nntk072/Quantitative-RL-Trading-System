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
    ├── ml-engineer.toml
    ├── data-scientist-engineer.toml
    ├── quantitative-trading-engineer.toml
    ├── evidence-reporting-engineer.toml
    ├── ci-operation-engineer.toml
    ├── qa-engineer.toml
    ├── independent-reviewer.toml
    └── resource-monitoring-engineer.toml
```

Use the canonical profile name as the spawned agent identity (`task_name`); put the work item in the assignment.

Choose the Architect as the coordinator. It assigns only the specialist needed
for the task: ML, Data Scientist, Quantitative Trading, Evidence & Reporting,
CI Operation, Resource Monitoring, QA, or Independent Reviewer. The Resource
Monitoring Engineer owns resource/environment operations and scheduled polling;
assign one timed check at a time and reuse the role after the prior result if
the handle remains live. Profiles contain the role boundaries; see the shared
coordination rule before delegating.

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

Store persistent task logs and handoffs under the ignored
`logs/agents/<canonical_role_id>/<YYYYMMDD>_<task_slug>/` path defined by the
shared coordination rule.

See [OpenAI's Codex custom-agent documentation](https://developers.openai.com/codex/subagents/)
for the current profile format.

The adoption and validation sequence is in the coordination rule. Validation
starts with TOML/schema checks and then uses one read-only smoke assignment per
implementation and gate role before code writers are run in parallel.
