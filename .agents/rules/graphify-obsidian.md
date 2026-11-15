---
trigger: manual
description: "Project-local Graphify installation and Obsidian notes-vault boundary."
---

# Graphify and Obsidian

- Graphify skill: `.agents/skills/graphify/`.
- Graphify runtime: `outputs/maintenance/agent_tools/graphify/graphifyy/`.
- Obsidian AppImage: `outputs/maintenance/agent_tools/obsidian/`.
- Obsidian vault: `agent-notes/`.
- Install versions: `.agents/rules/agent-tools.md`; current checksums are in the ignored installation manifest.
- Keep generated graph outputs and binaries under ignored `outputs/maintenance/`.
  The vault is for human-facing project notes; source, plans, protocols,
  evidence, and results remain authoritative. Do not copy secrets, raw data,
  checkpoints, or research results into the vault.

## Invocation policy
