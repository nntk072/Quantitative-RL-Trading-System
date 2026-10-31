# Repository tools

`tools/` contains developer-facing checks and setup helpers. These tools
validate or prepare the repository; they are not part of policy inference,
market simulation, or trading behavior.

The main entrypoint is `./tools/check`, which dispatches named verification
gates. `tools/documentation/` validates maintained links, package guide
coverage, and generated architecture references. Environment setup helpers
select architecture-appropriate Python environments. Read a tool's `--help`
or source before using an operation that writes files.

See [test organization](../tests/README.md),
[documentation maintenance](../docs/MAINTAINING.md), and the
[agent verification rules](../.agents/rules/ci-verification.md).
