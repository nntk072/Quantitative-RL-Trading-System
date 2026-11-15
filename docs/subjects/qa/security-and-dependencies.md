# QA for security and dependencies

**Status:** Five source claims verified at
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Source claims

1. `pyproject.toml` restricts MetaTrader5 to Windows and declares the
   `dev`, `docs`, and `mutation` extras. `tools/check::run_deps`
   calls `make deps-check`, which depends on `lock-check` and checks
   regenerated requirements exports against the committed copies.
2. `scripts/dev/security/dependency_audit.py::run_audit` exports frozen
   requirements with `dev`, omits hashes and the project itself, and
   invokes `pip-audit==2.10.1` with `--no-deps` and `--disable-pip`
   in JSON mode. The advisory CI job uses Ubuntu.
3. `load_exceptions` normalizes the package and advisory key and rejects
   malformed, duplicate, or expired entries. `run_audit` returns 2 for
   an unreviewed skip and 1 for unresolved findings if skips are cleared.
   `tests/unit/tooling/test_dependency_security_gate.py` checks these
   classification and validation contracts.
4. `scripts/dev/security/secret_scan.py` pins `detect-secrets==1.5.0`,
   disables the named entropy detectors, derives the research-table
   exclusion from tracked paths, and reports file, line, and detector type.
   The same test module covers exclusion and scanner result parsing.
5. `SECURITY.md` gives the private-report procedure. The working-tree
   `docs/security/dependency_security_status.md` explicitly labels the
   November 10 audit a historical snapshot and records removal of its
   supporting run artifacts during the November 15 clean restart.

## Document and notebook checks

The 153-line hub has the title and ten required sections. Six local
Markdown links and four pinned Git-source link targets resolve across
the hub and reference. The hidden notebook target resolves. The reference
accurately records the tool flags, result codes, and reviewed-skip policy.

Static notebook checks accepted the metadata, Python 3 kernel, Tier A,
CPU, deterministic bundled data, matching subject and owner, matching
first heading, under-60-seconds target, and forced MyST execution. One
assert-bearing code cell has count 1, one saved result, and zero saved
errors. The output stores one normalized fictional advisory and one skip.
Recorded cell time is 0.018 seconds.

## Evidence limit

The example parses a local fixed payload. The saved result describes a
synthetic dependency and skip. QA made no advisory service requests,
ran no scanner, and assessed no current security posture.
