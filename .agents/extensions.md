# Optional agent extensions

This is a capability inventory, not a requirement to load or call every tool.
Use the conditions and fallbacks in [`rules/extension-routing.md`](rules/extension-routing.md).
`tools/agent/extension-doctor` reports the current host state without model
inference; rerun only when availability matters.

| Capability | Current observed state (2026-11-15) | Interface | Use / fallback |
|---|---|---|---|
| Code Review Graph | Project MCP enabled; 2.3.9 local runtime; graph indexed at `c0d982f` | MCP and `tools/crgraph` | Code topology; fall back to source/tests. Graph may be stale or truncated. |
| Serena | Not found in Codex MCP or PATH | Optional MCP/LSP | Precise symbol navigation; fall back to editor/search. |
| Graphify | Project-local 0.9.108 runtime and skill | Local CLI/skill | Broader code-document/research relationships; fall back to source/docs search. |
| Obsidian | x86_64 AppImage staged; GUI not opened on the headless host; no MCP | Desktop app and `agent-notes/` vault | Human historical notes; fall back to repository documentation. |
| Ponytail | Skills copied into `.agents/skills/`; upstream source pinned in install docs | Skill | Minimal complete implementation/review; fall back to core execution rule. |
| Caveman Lite | Skill only in `.agents/skills/caveman/` | Skill | Concise handoffs; preserve exact validation and risk details. |
| Superpowers | Standalone skills in `.agents/skills/` | Skills | Use only when it adds a missing method; repository rules remain canonical. |
| RTK | Found at `/home/nguyenl37/.local/bin/rtk`; host-level, not project-local | Shell proxy | Optional output filtering; fall back to compact raw commands. |
| ast-grep | `ast-grep` not found; `sg` is present but is not treated as ast-grep | CLI | Structural matching if installed; fall back to scoped search. |
| CodeQL | Not found in PATH | CLI/CI | Security analysis when available; fall back to security rules and tests. |

The Obsidian binary and Python runtimes live in ignored project storage; the
portable skill files and setup instructions are versioned. Do not commit large
machine-specific binaries, credentials, graph databases, or generated indexes.
