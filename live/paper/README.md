# Paper trading

## Purpose

Package boundary reserved for paper-trading logging and adapters. There are
no concrete modules in this directory yet.

## Public API

There is currently no public API exported from `live.paper`.

## Invariants

- Paper-trading adapters must remain separate from live broker execution.
- Add a public surface only with explicit logging, order, and account-state
  contracts and tests.
