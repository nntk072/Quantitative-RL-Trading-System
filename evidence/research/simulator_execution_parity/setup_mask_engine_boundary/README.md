# Setup mask boundary across simulation engines

This packet records a Stage E action-contract mismatch and the opt-in
mask-aware backtest path added in response to the user's decision. It is
bounded current-source evidence, not an economic result or full checkpoint
parity claim.

With all candidate feature bits zero, the environment observation exposes only
the `no_trade` category as eligible. Selecting a concrete M1 FVG-retest setup
is rejected as `trade_setup_inactive`, and no order is submitted. The same bars
and all-zero candidate features passed to the default scalar `run_backtest`
path with action `+1` produce a long open. The opt-in
`trade_setup_actions=True` path now passes the canonical candidate mask to the
policy, decodes `TradeSetupActionSchema`, rejects a masked choice, and carries
candidate ID, idea, and timeframe into order/open records. `NO_TRADE` abstains
and holds an existing position. The scalar path remains the default and keeps
its prior behavior.

The initial characterization and follow-up compatibility batch pass in GH200
allocation `21410051`. The combined current-source suite passes 82/82; scoped
Ruff format and lint pass. Source identities and exact outputs are recorded in
the packet's run metadata and checksum files.

This closes candidate-mask enforcement for the bounded opt-in action path.
Risk sizing, stop/target geometry, exit lifecycle, and full environment
observation fields still use different contracts. Those differences must be
closed or excluded before claiming exact environment/backtest parity or
checkpoint replay equivalence.
