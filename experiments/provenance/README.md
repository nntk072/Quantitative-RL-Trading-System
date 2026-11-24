# Experiment provenance

## Purpose

Package boundary for provenance helpers associated with experiment runs.
There are no concrete modules in this directory yet.

## Public API

There is currently no public API exported from `experiments.provenance`.
Run identity and artifact handling remain in their owning experiment modules.

## Invariants

- Add provenance behavior to this package only with an explicit public
  contract and tests.
- Preserve run identity and source references when provenance helpers are
  introduced.
