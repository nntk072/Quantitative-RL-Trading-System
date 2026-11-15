---
trigger: manual
description: "Project-local optional-agent-tool inventory and installation references."
---

# Project-local agent tools

This rule records pinned versions, source revisions, and project-local setup.
The Obsidian checksum is pinned below; machine-specific runtime checksums are
also recorded in the ignored installation manifest under
`outputs/maintenance/agent_tools/`. Skill integrations are plain files under
`.agents/skills/`; no user-global Codex configuration or hooks were changed.

Pinned skill sources: Ponytail 5.3.3 at
`96608e078b2d5ea607c5c3b8b5a54d1c1fba6846`; Caveman at
`b4ee71d557d96e3cbc14f88fa6e953a1362865f5`; Superpowers at
`22f0b463e7a5e579904dd6211a520321035526f7`.

On a fresh checkout, install runtime packages into ignored project storage
with the architecture-matched `uv` executable. For example:

```bash
tool_root="$PWD/outputs/maintenance/agent_tools/code-review-graph"
UV_TOOL_DIR="$tool_root/tools" \
UV_TOOL_BIN_DIR="$tool_root/bin" \
UV_PYTHON_INSTALL_DIR="$tool_root/python" \
UV_CACHE_DIR="$tool_root/cache" \
uv tool install --managed-python --python 3.10.21 code-review-graph==2.3.9
```

For Graphify, use a project-local virtual environment and install the pinned
`graphifyy==0.9.108` package under
`outputs/maintenance/agent_tools/graphify/graphifyy/`.

The Obsidian 1.15.0 x86_64 AppImage is downloaded from the official
[Obsidian Linux download page](https://obsidian.md/download). Its SHA-256 is
`1dd8cfb593deaa644101bdb4df65b159ed7985993b6572dd25fd1363459e91cc`.
The skill integrations and license files are already in `.agents/skills/`.

For a fresh Graphify runtime, use:

```bash
graphify_root="$PWD/outputs/maintenance/agent_tools/graphify/graphifyy"
uv venv --python 3.12 "$graphify_root"
uv pip install --python "$graphify_root/bin/python" graphifyy==0.9.108
```

| Tool | Project-local entry |
|---|---|
| Code Review Graph | `tools/crgraph`, `.mcp.json`, `.codex/config.toml` |
| Graphify | `.agents/skills/graphify/`, `outputs/maintenance/agent_tools/graphify/` |
| Obsidian | `outputs/maintenance/agent_tools/obsidian/`, vault `agent-notes/` |
| Ponytail | `.agents/skills/ponytail*` |
| Caveman Lite | `.agents/skills/caveman/` |
| Superpowers | standalone skill folders under `.agents/skills/` |

## Invocation policy

Use optional capabilities only under
[`extension-routing.md`](extension-routing.md); an installed tool is never a
requirement to invoke it.
