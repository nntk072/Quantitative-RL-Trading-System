# Simulation · `backtest.event_driven_backtest`

This page contains 1 public callable records owned by `simulation.backtest.event_driven_backtest`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `run_backtest`

**Kind:** function · **Status:** stable · **Owner:** `simulation.backtest.event_driven_backtest`

**Purpose:** Run a full backtest over aligned bars + features.

**Exact API:** {py:obj}`simulation.backtest.event_driven_backtest.run_backtest` · **Source:** [simulation/backtest/event_driven_backtest.py:538](../../../../simulation/backtest/event_driven_backtest.py#L538)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  policy: Policy used to select or evaluate actions.
  obs_window: Numeric value used for the obs window.
  cost_model: Cost model used by the operation described above.
  broker_kwargs: Key-value data used for the broker kwargs.
  guardrail_kwargs: Key-value data used for the guardrail kwargs.
  initial_balance: Numeric value used for the initial balance.
  lots: Numeric value used for the lots.
  max_loss_per_trade_usd: Max loss per trade usd used by the operation described above.
  take_profit_per_trade_usd: Take profit per trade usd used by the operation described above.
  tickbook: Tickbook used by the operation described above.
  fill_delay_ms: Numeric value used for the fill delay ms.
  randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
  max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
  tick_execution_required: Whether to enable or require the tick execution required.
  server_side_protective_orders: Execute attached SL/TP orders on their triggering
      tick without sampling a new EA/network latency.
  execution_seed: Numeric value used for the execution seed.
  fill_latency_bars: Whole M1 bars added after the ordinary next-bar entry fill.
  use_structure_sl_tp: Whether to enable or require the use structure sl tp.
  risk_frac: Numeric value used for the risk frac.
  policy_risk_frac_range: Optional lower/upper risk-fraction bounds decoded from
      the setup action's risk coordinate. When omitted, that coordinate retains
      the configured fixed risk fraction for backwards-compatible callers.
  rr_ratio: Numeric value used for the rr ratio.
  swing_buffer_pts: Numeric value used for the swing buffer pts.
  sl_buffer_pts: Confirmed-swing trailing-stop buffer in price units.
  min_lot: Numeric value used for the min lot.
  max_lot: Numeric value used for the max lot.
  lot_step: Broker volume increment used by risk-based position sizing.
  contract_size: Number specifying the contract size for this operation.
  hold_on_zero: Whether to enable or require the hold on zero.
  exit_action: Exit action used by the operation described above.
  block_overnight: Whether to enable or require the block overnight.
  eod_risk: Optional environment-compatible position guard settings. When
      supplied, the backtest uses ``max_loss_usd`` as an intrabar adverse
      excursion cutoff, raised to planned structural-stop risk when
      ``respect_planned_risk`` is true. When omitted, the legacy
      ``max_loss_per_trade_usd`` close cap is retained.
  sl_mode: Static stop-management mode for the scalar-action backtest.
      ``fixed``, ``breakeven``, and ``trailing`` are supported. When a
      learned SL coordinate is present, its neutral band starts at
      ``fixed`` and advances through the state machine.
  tp_mode: Deferred TP-management default when the schema has a TP mode
      coordinate; the mode then advances through the state machine.
  sl_mode_defer_threshold: Neutral-band half-width for the learned SL mode.
  tp_mode_defer_threshold: Neutral-band half-width for the learned TP mode.
  tp_breakeven_alpha: Initial-risk fraction used to pull a TP toward entry.
  observation_schema: Explicit account observation contract. Supplying it
      requests the environment's structured observation for scalar or setup policies.
  normalize_account: Emit normalized account coordinates for schemas that require them.
  observation_age_scale_bars: Position-age scale used by normalized account schemas.
  entry_state_machine: Track and gate persistent entry opportunities as in TradingEnv.
  candidate_max_age_bars: Maximum evidence age retained by the entry lifecycle.
  arm_requires_retest: Require a current directional retest before arming a candidate.
  regime_observation: Add the versioned completed-D1 regime vector and validity mask.
  mtf_observation: Add the environment's closed higher-timeframe observation windows.
  mtf_windows: Optional per-timeframe row counts overriding environment defaults.
  feature_validity_channels: Append finite-value channels to sequence windows.
  scheduled_session_closes: Optional local-date to NY-close map for clipped HTF bars.
  session_start: Local session-start clock used by HTF availability calculations.
  vae: Optional frozen encoder used to emit the environment's ``vae_z`` input.
  pre_ny_by_date: Per-session VAE input sequences keyed by local market date.
  pre_ny_data: Legacy row-aligned flattened VAE inputs.
  daily_pnl_basis: Optional daily-loss basis override. Session net equity
      includes realized and open PnL since the supplied session reset;
      legacy gross closed losses does not offset wins or include open PnL.
      When ``trading_policy`` is provided, its daily-PnL contract is used.
  trading_policy: Optional validated account-policy configuration. Repeated
      payout mode enables realized-balance withdrawals and account resets;
      its sizing requires structure-derived stop levels.
  tick_fill_slippage_points: Market-fill slippage override (historical
      parameter name retained). Defaults to ``cost_model.slippage_points``
      for tick and bar quotes. Explicit zero preserves a zero-slippage
      replay. Limit entries stay price-bounded.
  trade_setup_actions: Expose the canonical setup eligibility mask to the
      policy and decode its versioned categorical action instead of a
      scalar direction. Risk, stop/target geometry, and position exits
      continue to use the event backtest's configured controls.
  trade_setup_action_schema: Optional configured setup action schema;
      the canonical default schema is used when setup actions are enabled.
  allow_ema_exit: Whether a selected setup action may choose an EMA-21 exit.
  trade_setup_geometry: Apply the setup action's selected stop/target
      geometry. Defaults to enabled with setup actions and disabled for
      scalar-action callers.
  strategy: Strategy contract used by structural order placement. The
      baseline strategy is used when setup geometry is enabled and none
      is supplied.
  min_sl_atr_mult: Minimum structural stop distance as a multiple of ATR-5.
  min_sl_points: Absolute minimum structural stop distance in price units.
  policy_rr_ratio_range: Inclusive lower/upper reward-risk bounds for
      structural targets. Defaults to the environment's ``[1.0, 3.0]``.
  target_timeframes: Higher timeframes permitted for target references.
  ema_runner_fraction: Fraction reserved for the EMA runner when enabled.
  limit_order_max_offset_atr: Maximum policy-selected limit distance from
      the decision close, expressed in ATR units.
  limit_order_max_ttl_bars: Maximum integer M1-bar lifetime for a policy
      selected resting limit.
  limit_order_require_trade_through: Require the executable quote to
      move strictly beyond the limit for queue-position sensitivity.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = run_backtest(bars=..., features=..., policy=..., obs_window=..., cost_model=..., broker_kwargs=..., guardrail_kwargs=..., initial_balance=..., lots=..., max_loss_per_trade_usd=..., take_profit_per_trade_usd=..., tickbook=..., fill_delay_ms=..., randomized_fill_latency_ms=..., max_tick_quote_wait_ms=..., tick_execution_required=..., server_side_protective_orders=..., execution_seed=..., fill_latency_bars=..., use_structure_sl_tp=..., risk_frac=..., policy_risk_frac_range=..., rr_ratio=..., swing_buffer_pts=..., sl_buffer_pts=..., min_lot=..., max_lot=..., contract_size=..., hold_on_zero=..., exit_action=..., block_overnight=..., eod_risk=..., sl_mode=..., daily_pnl_basis=..., trading_policy=..., tick_fill_slippage_points=..., trade_setup_actions=..., trade_setup_action_schema=..., allow_ema_exit=..., trade_setup_geometry=..., strategy=..., min_sl_atr_mult=..., min_sl_points=..., policy_rr_ratio_range=..., target_timeframes=..., ema_runner_fraction=..., limit_order_max_offset_atr=..., limit_order_max_ttl_bars=..., limit_order_require_trade_through=..., lot_step=..., tp_mode=..., sl_mode_defer_threshold=..., tp_mode_defer_threshold=..., tp_breakeven_alpha=..., observation_schema=..., normalize_account=..., observation_age_scale_bars=..., entry_state_machine=..., candidate_max_age_bars=..., arm_requires_retest=..., regime_observation=..., mtf_observation=..., mtf_windows=..., feature_validity_channels=..., scheduled_session_closes=..., session_start=..., vae=..., pre_ny_by_date=..., pre_ny_data=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
