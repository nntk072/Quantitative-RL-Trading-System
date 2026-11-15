# Security and dependencies

**Status:** draft
**Use this when:** You need to change a dependency, understand what the security checks cover, or report a software vulnerability privately.

## Summary and use this when

The repository declares package requirements in `pyproject.toml` and
resolves them in `uv.lock`. It maintains separate checks for lock
consistency, dependency advisories, and credential findings in repository
files. Their scope differs. Read the check result against the exact revision,
platform, and inputs it examined.

Report vulnerabilities using the private reporting instructions in the
[security policy](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/c0d982f94ab9df8b2a9ddd013d2ae9a562573529/SECURITY.md). Keep credentials, account IDs and
affected private artifacts out of reports intended for public discussion.

## Key terms

- [Artifact](../../glossary.md)
- [Lineage](../../glossary.md)
- [Checkpoint](../../glossary.md)

## Explanation

### Declared dependencies and the lock

`pyproject.toml` declares Python requirements, runtime packages, platform
markers, optional extras, and package sources. Development, documentation,
and mutation tools are declared as separate extras. MetaTrader5 in the base
dependencies has a Windows marker. The project resolves versions in
`uv.lock`, which should be reviewed with any dependency or source change.

The `deps` check routes through `Makefile::deps-check`. Frozen lock export
is a separate step in the advisory check. Preserve the distinction when
recording a lock check and when recording which packages were audited.

### Advisory checks and exceptions

`./tools/check security-deps` invokes the repository's dependency audit
script. It exports the frozen requirements including the development extra,
omits the project package, and invokes the pinned `pip-audit` tool in its
isolated runner. The maintained status page describes the Linux
runtime-plus-development scope. Windows-specific packages and the docs and
mutation extras need their own coverage when those environments are relevant.

The audit parses advisory findings and explicit skipped-dependency records.
Exceptions are keyed by normalized package name and uppercased advisory ID.
The exception file requires a reason, impact and review date. Invalid,
duplicate or expired records fail validation. An allowlisted skipped
dependency is an explicitly unaudited dependency. An advisory exception is a
recorded decision about a finding within its declared scope and review date.

### Credential scan and artifact trust

`./tools/check security-secrets` invokes the isolated credential scanner.
The wrapper scans Git-visible text and prints safe finding metadata such as
file, line and detector type. It disables two entropy detectors and excludes
generated CSV/Parquet tables under `evidence/research/` when those tracked
files are present. Treat each scan as a scoped assertion about its inputs
and enabled detectors.

Supply credentials through the environment or local secret configuration, as
specified by the project. Review notebooks and logs for credentials before
sharing them. Read the repository's security rules before handling
externally supplied data, configuration, or serialized models. Verify
artifact provenance before passing material to a loader.

### Failure modes

- Updating a dependency declaration alone leaves the review of its resolved
  packages incomplete.
- Reporting a clean advisory count without skips and exception details hides
  parts of the dependency coverage.
- Treating a historical scanner report as current evidence loses its
  revision, platform, and time boundary.
- Adding a credential or machine-specific path to a public bug report can
  disclose it beyond the intended audience.

## Worked example

The Tier A notebook parses fixed synthetic advisory and skip records using
the same helper as the dependency audit. It shows package normalization and
keeps skip coverage visible without invoking an external scanner.

```{toctree}
:hidden:

examples/security-and-dependencies
```

## Tasks

- Use the [private reporting procedure](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/c0d982f94ab9df8b2a9ddd013d2ae9a562573529/SECURITY.md) for an
  affected revision, component, and privately shared supporting details.
- Read the [dependency security status](../../security/dependency_security_status.md)
  for the tracked report, platform scope, and documented exceptions.
- Use the [security check contract](../../reference/subjects/security-and-dependencies.md)
  for the tools, inputs, exit conditions, and blind spots.
- Follow the [contribution workflow](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/c0d982f94ab9df8b2a9ddd013d2ae9a562573529/CONTRIBUTING.md) to review
  dependency changes and their lockfile impact.

## Contract

| Item | Contract | Source |
|---|---|---|
| Dependency identity | Runtime declarations, extras, markers and sources resolve through the committed lockfile | `pyproject.toml`; `uv.lock` |
| Lock check | Canonical check runs the make lock-consistency target | `tools/check::run_deps`; `Makefile` |
| Audit input | Frozen runtime + dev export for Linux audit invocation | `scripts/dev/security/dependency_audit.py::run_audit` |
| Exceptions | Package plus advisory, reason, impact, review date | `scripts/dev/security/dependency_audit.py::load_exceptions` |
| Skips | Unexpected unauditable dependencies fail the audit | `scripts/dev/security/dependency_audit.py::unexpected_skips` |
| Credential findings | Safe location/detector fields, with defined exclusions | `scripts/dev/security/secret_scan.py::findings_from_baseline` and `main` |

## Verify

- `tests/unit/tooling/test_dependency_security_gate.py` checks reported
  findings, exception handling, skips, and safe scanner parsing.
- `tests/architecture/test_dependency_rules.py` checks that development
  dependencies are kept out of the declared runtime package set.
- `.github/workflows/ci.yml` defines the lock, dependency advisory, and
  credential jobs. Use the individual job result for a current check claim.

## Limits and common mistakes

The audit scope excludes platform and extras outside its report. A
credential scan can leave ignored, excluded, or unsupported material
unexamined. Advisory and credential checks give bounded evidence about
their inputs. A security posture claim requires current evidence beyond
these examples.

The tracked status page records a dated audit. Any subsequent advisory or
dependency change requires reevaluation against the exact target
environment.

### Review the audit scope

Read the report alongside the lock revision and the invocation platform.
An accepted advisory exception and an unaudited package each need their own
entry in the review, since they answer different coverage questions.

## Change checklist

- Update and review both the declaration and the lock resolution.
- Verify which platform markers and extras are in the intended scan.
- Preserve reason, impact, and review date for any approved exception.
- Check inputs and outputs for secret values before sharing.
- Record the source revision, date, scan scope, unresolved findings and skips.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `ci_operation_engineer`
