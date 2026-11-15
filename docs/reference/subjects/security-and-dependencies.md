# Security and dependency check contract

**Status:** draft
**Source of truth:** `pyproject.toml`; `uv.lock`; `tools/check`; `scripts/dev/security/dependency_audit.py`; `scripts/dev/security/secret_scan.py`

## Checks

| Surface | Contract |
|---|---|
| `./tools/check deps` | Runs `make deps-check` using the selected `uv` environment. |
| `./tools/check security-deps` | Exports frozen requirements with extra `dev`, without hashes or the project itself, then runs `pip-audit==2.10.1` in JSON mode with dependency resolution disabled. |
| `./tools/check security-secrets` | Runs `detect-secrets==1.5.0`, disabling `Base64HighEntropyString` and `HexHighEntropyString`. Excludes generated CSV/Parquet research tables under `evidence/research/` when present in tracked files. |

## Advisory input and results

The audit accepts `--exceptions` and `--report-out`. The default exception
document is `docs/security/vulnerability_exceptions.toml`. Each exception
requires advisory, package, reason, impact, and TOML date `review_after`.
Case and PEP 503 spelling are normalized in the package/advisory key.
Invalid, duplicate, and past-dated records are rejected.

Exit 0 means no unresolved advisory or unreviewed scan skip. Exit 1
reports unresolved advisories; unexpected skips or malformed audit output
return 2. Export and tool errors can propagate nonzero status. The reviewed
unauditable set is declared in `ALLOWED_UNAUDITABLE_DEPENDENCIES`.

## Credential results

The scanner wrapper returns 1 for reported findings and returns nonzero
for scan or parse failure. Finding details use filename, line, and
detector type. See the [dependency scan status](../../security/dependency_security_status.md)
for the tracked audit scope and the [security policy](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/c0d982f94ab9df8b2a9ddd013d2ae9a562573529/SECURITY.md)
for reporting procedure.
