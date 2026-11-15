---
trigger: manual
description: "Project-local Code Review Graph installation and query reference."
---

# Code-review-graph

A structured review method: treat a change as a **graph** and walk it deliberately, reviewing by node priority — not by reading files top to bottom.

## Invocation policy

Use this graph when code relationships are unknown or a change spans shared
symbols. Known-file edits and simple local matches should use native tools.
The canonical tool-selection and fallback policy is
[`extension-routing.md`](extension-routing.md).


## 1. Build the node set (the diff)

- `git diff --stat` (or `git log -1 --stat`) → list changed files/symbols as **nodes**.
- State a one-line goal: what is this change trying to do?

## 2. Discover edges (relationships)

Scoped searches only — no repo-wide dumps:

- **Callers (fan-in):** who calls this symbol? → blast radius.
- **Callees (fan-out):** what does the change call / import / include?
- **Types / contracts:** signatures, interfaces, base classes, public API touched?
- **Tests:** glob `**/test*` + search module or symbol near changed code.

## 3. Prioritize hot spots

- **High fan-in** or **shared / public API** → deep review: one targeted read per hot spot.
- **Leaf / internal nodes** → diff + summary only.
- Always deep: concurrency, error paths, resource lifecycle, security boundaries.

## 4. Walk by depth, not breadth

- **Depth-1 first:** direct callers / callees / tests of changed nodes.
- **Depth-2** only when a depth-1 node looks risky or a contract changed.
- Hard cap: ≤5 locate steps before opening files; slices only (~80–150 lines).

## 5. Report as a graph

- Short summary: what changed, blast radius, risk level.
- `path:line` citations for each finding.
- Flag: untested changed public symbols, broken contracts, missing error handling.
- Do not paste whole files; show small hunks only.

## Budget

- Stop when a subgraph is all leaves or low-risk.
- Spend tokens on hot spots; diff + summary for low-risk subgraphs.

## Relations

- Activates: reviewing a diff/PR/local change touching >1 file or shared symbols; skip for single-file typo edits.
- Uses [context-management.md](context-management.md) read discipline and [token-efficient-shell.md](token-efficient-shell.md) git commands; findings feed [git-commit-rules.md](git-commit-rules.md) pre-commit checks.

## Graph trust and configuration dependency checks

Use the persistent graph for navigation, blast-radius discovery, and candidate impact analysis. Verify important execution paths and configuration dependencies against source and tests before relying on a graph-only conclusion.

### Bounded impact results

Impact reports are capped. Treat `truncated: true`, omitted-node/edge counts, or a capped result summary as incomplete; an omitted relationship is not evidence that the dependency is absent. Increasing `--max-results` does not necessarily increase the rendered MCP/CLI result window. Start with a depth-1 impact query per changed file, then query specific callers, callees, tests, or flows for any remaining hot spots:

```bash
./tools/crgraph impact --files path/to/changed_file.py --depth 1 --max-results 1000 --repo "$PWD"
```

If the result is still truncated, split the changed-file set or narrow to individual symbols. Record the reported depth, counts, and truncation flag, and verify high-impact paths in source and tests. `unresolved_call_sites` is a separate limitation and must not be treated as proof of a missing relationship.

For reviews of uncommitted code, verify that the graph updater or watcher has processed the changed files. `built_at_commit` identifies the Git base revision; by itself it does not prove that current working-tree edits are present in the index. If the hook state is unknown or stale, run `./tools/crgraph update --repo "$PWD"` once before querying. Recheck after relevant source edits instead of repeating the update before every query.

Repository-owned quality commands:

```bash
./tools/crgraph quality
./tools/crgraph verify-critical --baseline outputs/code_graph_quality/baseline.json
```

The quality audit classifies `CALLS` edges as `internal_exact`, `internal_ambiguous`, `internal_unresolved`, `external_library`, `python_builtin`, or `dynamic_or_indeterminate`. The principal quality metric is the resolution rate among repository-internal call candidates, rather than exact calls divided by all calls.

Configuration analysis is stored as a companion index under `outputs/code_graph_quality/config_dependencies.json`. This keeps YAML/TOML dependency evidence separate from the upstream graph database schema and records static load sites plus dynamic loads that still require source review.

A resolved `TESTED_BY` relationship means only that the recorded relation points to an indexed node. It does not establish line, branch, path, or behavioral test coverage.

### Strict config reachability and ambiguity policy

`verify-critical` is fail-closed for critical configuration reachability. Each critical config has an allowed reachability state: direct load, evidence-backed indirect registry/default-parameter selection, or an explicitly documented inactive state. A tracked file alone is no longer sufficient.

Baseline behavior is defined directly in `config/base/default.yaml`; the only
strategy overlays are the active PO3/IFVG and distribution configurations.
Those overlays and `config/quality_experiments.yaml` must remain traceable
through their active strategy or quality registry paths.

CALLS quality reports now include both global and research-critical-path resolution. Evidence-backed same-module, explicit-import/re-export, `self`/`cls`, and unique direct-base resolutions may be promoted to `internal_exact`. Generic container/file methods with unknown receivers remain dynamic rather than being matched to unrelated repository methods with the same short name.

Use `outputs/code_graph_quality/ambiguous_call_breakdown.{json,md}` to inspect remaining ambiguity classes. Preserve ambiguity whenever static evidence does not identify one target.
