# Research tools

`research_tools/` contains the repository study framework and reusable
cross-domain diagnostics. These tools may compose public APIs from production
packages; production code must not import this package.

Study definitions and workflow switches live in `config/studies/`. From the
repository root, use `qrl-study validate` to verify the catalog and
`qrl-study plan` to inspect its selected checks.
