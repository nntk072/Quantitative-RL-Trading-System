# Paired lifecycle characterization

On 2026-11-04, seven focused integration modules passed together: 69/69 tests
in the existing one-GH200 allocation. The batch covers controlled
environment/backtest account transitions, multi-target protective exits,
risk-event precedence and lifecycle, repeated payouts, fill accounting,
quote-side behavior, and stratified local TickBook action traces.

The exact command and test output are in this packet. `SOURCE_SHA256SUMS`
records the tested test modules and core environment/backtest entry points.

This is bounded current-source characterization. It does not close the full
Stage E gate: historical policy-action linkage is unavailable in the recovered
trace set; external within-timestamp chronology, financing, every risk/order
configuration, and live broker parity remain unsupported or open. See the
sibling packets for independently verified local traces, session transitions,
quote-wait behavior, and stop lifecycle.
