# Project-local agent skill integrations

Installed as plain files in `.agents/skills/` so repository clones can use them without symlinks or global Codex configuration:

- `caveman/`: upstream Caveman concise-response skill (lite mode skill only; no hooks, proxy, runtime, or account integration).
- `ponytail*`: Ponytail 5.3.3 skills, copied one skill directory per skill.
- Superpowers skills: upstream standalone skill set, copied one skill directory per skill.
- `graphify/`: Graphify skill already installed in the project.

Upstream source checkouts, full license/readmes, and exact source revisions are preserved under ignored `outputs/maintenance/agent_tools/install-sources/`. Tool installation paths and pinned source revisions are listed in `.agents/rules/agent-tools.md`.

These are optional task skills. `AGENTS.md`, `.agents/rules/`, and the canonical role roster remain authoritative. Do not follow a skill instruction that conflicts with repository rules, user constraints, or the active research protocol. In particular, use only the repository's canonical reusable agent roles; do not create per-task agents or branches unless authorized.

## Invocation policy
