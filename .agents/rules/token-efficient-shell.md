---
trigger: model_decision
description: "Use when invoking shell commands or controlling command output."
---

# Token-efficient shell and tool output

Use compact commands so terminal output stays small.

Before execution, check that the complete shell command is syntactically closed:
no dangling `&&` / `||`, unmatched quotes, or unfinished heredocs. Prefer one
command per tool call; do not append a separator when there is no following
command. Never invoke bare `python` or `python3` for project work, even for
one-line scripts. Use the full architecture-matched environment executable in
the command itself so it can be copied and rerun; do not rely on shell aliases
or PATH. Before a batch edit, validate every read/modify target exists and every create
target has an intended parent; perform these checks before the first write so a
missing later path cannot leave a partial edit. Confirm referenced executables
and paths before longer commands; compare targets against the repository path
list instead of retyping similar names.
When a project helper expects a filesystem path, pass a resolved absolute path
if its root is absolute; do not assume it resolves relative arguments itself.
For unfamiliar CLI options, inspect that executable's usage and confirm whether
each option expects a file, directory, or value. For repository scripts, inspect
the argument parser before adding flags; some scripts have no parser and a
`--help` probe may launch their default workload. Do not assume every command
supports `--help`. After a syntax, path, option, or command-not-found error,
correct the invocation before retrying. For project builds, reuse the repository
configuration and extension set instead of assembling a second plugin stack.

## Prefer tools over shell

- **Search code**: use search with tight patterns — not `grep -r` / `rg` dumping whole repos.
- **Find files**: use file globs — not `find .` without depth limits.
- **Read files**: open with offset/limit — not `cat`, `head -n 5000`, or generated/vendor trees.

## Git (compact first)

1. `git status -sb` or `git status --porcelain=v1`
2. `git log --oneline -20` (increase only when debugging history)
3. `git diff --stat` or `git diff -U0 -- <paths>` before full hunks
4. `git show --stat <rev>` before `git show -p`
5. `git diff main...HEAD --stat` then path-limited diffs

## Search in terminal (only when tools are insufficient)

- Ripgrep: `rg -n --max-columns 120 -m 80 <pattern> <path>`
- Never run unbounded `rg` / `grep -r` on `.` or large dirs (`node_modules`, `dist`, `.git`).

## RTK

Use RTK only when the command is supported and its filtering preserves the
diagnostics needed for the task. Otherwise use compact native commands; see
[`extension-routing.md`](extension-routing.md).

## Builds, tests, installs

- Run the narrowest command (single package, single test file, `-q` / quiet).
- On success: one-line confirmation; do not paste full logs.
- On failure: failing test names, error lines, and ~20 lines of context only.

Before invoking project Python directly, match the environment to `uname -m`:

| Host architecture | Environment |
|---|---|
| `x86_64` | `.venv-x86/bin/python` (normal local environment) |
| `aarch64` or `arm64` | `.venv-arm/bin/python` |
| AMD MI210 node | `.venv-mi210/bin/python` |

Prefer `./tools/check` for supported repository gates; it selects the local
environment by architecture. `.venv` is a legacy alias for `.venv-arm` and must
not be used to choose an interpreter. If Python returns `Exec format error`, stop and correct the
environment path before retrying; do not run a different architecture's
environment or reinstall packages as a workaround.

## Docker / k8s / cloud CLIs

- `docker ps --format '...'`, `kubectl get pods -o wide` over wide defaults.
- Avoid `kubectl logs` without `--tail=50` (or smaller).

## JSON / logs

- `jq 'keys'` or targeted `jq '.field'` — not multi-MB pretty-printed JSON.
- Logs: filter (`rg -i 'error|warn|fail'`) and cap lines.

## General

- Do not read secrets (`.env`, credentials).
- Batch independent commands in parallel; avoid redundant runs.
- Explain conclusions in prose; do not quote large output.

## Relations

- Activates: whenever running terminal commands, builds, tests, git, docker, or inspecting JSON/logs.
- Complements [context-management.md](context-management.md) and [extension-routing.md](extension-routing.md).
