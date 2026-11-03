# Changelog

Changes that affect users, research reproducibility, public contracts, or
maintainers are recorded here. Historical implementation details remain in
Git history; current findings are indexed in the [research map](docs/research/README.md),
and evidence moves are recorded in the [migration ledger](docs/architecture/migrations/research_evidence_moves.json).

## Unreleased

### Added

- A Sphinx documentation site with generated Python package reference and
  Mermaid diagram support.
- A main-branch line and conditional-branch coverage baseline, package-level
  report, and regression gate.
- Project-neutral research methods, validation protocol, limitations, and
  experiment execution documentation.

### Changed

- Standardized maintained project interfaces and research terminology around
  Quantitative RL Trading System and trade setups.
- Moved historical research reports and machine evidence into indexed archive
  locations while preserving source snapshots and provenance records.
- Added documentation and quality gates to normal pull-request CI.

### Removed

- Academic-only project paths, obsolete command and environment aliases, and
  forwarding scripts that duplicated maintained analysis tools.
- The feature-specific `CHANGES.md` remediation report; its obsolete source
  paths and one-off plan references are preserved in Git history.
