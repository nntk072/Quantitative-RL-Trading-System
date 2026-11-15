# Project Codex agents

Trust the repository in Codex and open its root to load `.codex/config.toml` and
`.codex/agents/`. The profiles are thin adapters; canonical role identity,
ownership, delegation, context, and concurrency policy lives in
[`.agents/rules/delegation.md`](../.agents/rules/delegation.md), with reasoning
selection in [`.agents/rules/reasoning-effort.md`](../.agents/rules/reasoning-effort.md).

Codex allows a ceiling of four spawned workers plus the coordinator when the
host supports it. This is not a target: root-only work is valid, and work is
spawned only when ready, independent ownership can improve the critical path or
correctness. Reasoning effort is selected per assignment; profiles do not pin a
model or global effort. Platform profiles inherit the parent permissions and
tools; role boundaries are instructions, not access-control enforcement.

Store persistent logs under `logs/agents/<canonical_role_id>/<date>_<task>/`.
See [OpenAI's Codex custom-agent documentation](https://developers.openai.com/codex/subagents/)
for the native profile format.
