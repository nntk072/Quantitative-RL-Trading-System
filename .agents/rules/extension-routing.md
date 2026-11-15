---
trigger: model_decision
description: "Use when selecting source navigation, graph, memory, or terminal extensions."
---

# Extension routing

Extensions are optional capabilities. Choose one that answers the information
problem; do not invoke a tool merely because it is installed. If it is absent
or fails, use its listed fallback and continue. Never treat extension output as
authoritative over current source, tests, config, or verified evidence.

| Need | Preferred capability | Use when | Fallback |
|---|---|---|---|
| Known file or local text | Native file/search tools | Path or string is known | Scoped `rg` |
| Callers, callees, tests, impact, code flows | Code Review Graph | Code relationship is unknown or change spans shared symbols | Scoped source/test traversal |
| Symbol definitions/references and precise edits | Serena | Language-server navigation or rename materially helps | Native editor/search |
| Code ↔ docs/research concepts or cross-repo relations | Graphify | Code Review Graph cannot answer the broader relationship | Search authoritative docs and source |
| Historical rationale | Obsidian vault | A specific prior decision/note is needed | Repository docs or user context |
| Smaller implementation/review | Ponytail | Refactor risks needless abstraction or duplicated code | Core minimal-complete-change rule |
| Terminal output filtering | RTK | Command is supported and exact output is unnecessary | Compact raw command |
| Syntax-aware pattern migration | ast-grep | Structural repetition exceeds safe text search | Scoped source edits |
| Security analysis | CodeQL or existing security gate | Security-sensitive code or explicit audit | Repository security rules/tests |

Avoid duplicate retrieval: CRG owns code topology; Serena owns language-server
symbols; Graphify is only for broader semantic/cross-artifact relations.
Obsidian supplies history, never current implementation truth. RTK filters I/O;
it does not replace source/graph retrieval. Do not stack compression layers.
Choose one primary tool for a question; combine tools only when their roles are
distinct (for example, CRG impact followed by Serena symbol navigation).

Expose only tools supported by the current platform and task. Codex custom
profiles may disable supported feature classes, but MCP servers are configured
at the parent session and inherited. Where tool hiding is unavailable, apply
this routing behavior in the role instructions without claiming technical
enforcement.
