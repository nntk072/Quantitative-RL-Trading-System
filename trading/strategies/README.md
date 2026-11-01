# Trading strategies

`trading/strategies/` defines broker-neutral strategy interfaces and concrete
rule implementations. The PO3/IFVG strategy consumes feature rows to validate
entries, resolve stop references, and propose target candidates. Baseline and
distribution strategies implement related strategy contracts.

Strategies describe decisions and references; they do not execute orders or
own broker adapters. Preserve feature causality and distinguish a candidate
setup from an accepted order. Focused tests are in `tests/unit/trading/` and
`tests/unit/simulation/`.
