# Research-tool unit tests

These tests check deterministic research utilities such as report generation,
ledger reconciliation, manifest validation, paired statistics, and checkpoint
parity comparisons. They validate the analysis code's contracts; they do not
replay a market year or establish a policy's trading performance.

Keep each test beside its behavior rather than grouping it under an academic
program name. Use small in-memory frames and temporary artifact directories.
Tests that require real market data, a full checkpoint replay, a GPU, or a
cluster belong in a separately marked integration or research suite.

The tests run with the normal scoped unit command. Shared research fixtures
belong under `tests/fixtures/` or alongside the owning test when they are
specific to one analysis.
