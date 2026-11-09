# Evaluation · `rollout.trained_policy_rollout`

This page contains 4 public callable records owned by `evaluation.rollout.trained_policy_rollout`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `evaluate_provider`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.rollout.trained_policy_rollout`

**Purpose:** Evaluate a backend-neutral decision provider through the trading environment.

**Exact API:** {py:obj}`evaluation.rollout.trained_policy_rollout.evaluate_provider` · **Source:** [evaluation/rollout/trained_policy_rollout.py:957](../../../../evaluation/rollout/trained_policy_rollout.py#L957)

**Inputs and outputs:**

- **Args:**

  ```text
  provider: Provider used by the operation described above.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_evaluate_provider_uses_the_same_trading_rollout`](../../../../tests/unit/evaluation/test_rollout.py#L225)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    provider = SB3DecisionProvider(
        _ScriptedModel(script),
        input_schema_version=OBSERVATION_SCHEMA_V1,
    )

    result = evaluate_provider(
        provider,
        bars=bars,
        features=features,
        obs_window=obs_window,
        initial_balance=100_000.0,
    )

    assert not result["trades"].empty
    assert result["completed_data_split"] is True
    assert result["equity"].index[0] == bars.index[obs_window]
    assert len(result["equity"]) == len(bars) - obs_window + 1
```

2. [test fixture: `test_supervised_provider_runs_through_shared_evaluation_path`](../../../../tests/unit/learning/test_learning_supervised_reference.py#L104)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    features = pd.DataFrame(0.0, index=index, columns=["f0"])
    features["last_swing_low"] = close - 5.0
    features["last_swing_high"] = close + 5.0

    result = evaluate_provider(
        provider,
        bars,
        features,
        obs_window=10,
        observation_schema_version="account-state-v1",
        block_overnight=False,
    )

    assert result["n_steps"] > 0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `evaluate_model`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.rollout.trained_policy_rollout`

**Purpose:** Walk a trained RL ``model`` over *bars*/*features* and collect trades.

**Exact API:** {py:obj}`evaluation.rollout.trained_policy_rollout.evaluate_model` · **Source:** [evaluation/rollout/trained_policy_rollout.py:176](../../../../evaluation/rollout/trained_policy_rollout.py#L176)

**Inputs and outputs:**

- **Args:**

  ```text
  model: Model used for this operation.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  obs_window: Numeric value used for the obs window.
  initial_balance: Numeric value used for the initial balance.
  cost_model: Cost model used by the operation described above.
  broker_kwargs: Key-value data used for the broker kwargs.
  guardrail_kwargs: Key-value data used for the guardrail kwargs.
  risk_frac_range: Items supplied for the risk frac range, in input order.
  rr_ratio_range: Items supplied for the rr ratio range, in input order.
  swing_buffer_pts: Numeric value used for the swing buffer pts.
  min_lot: Numeric value used for the min lot.
  max_lot: Numeric value used for the max lot.
  lot_step: Broker volume increment used for risk-based sizing.
  contract_size: Number specifying the contract size for this operation.
  max_loss_per_trade_usd: Numeric value used for the max loss per trade usd.
  dsr_eta: Numeric value used for the dsr eta.
  deterministic: Whether to enable or require the deterministic.
  max_episode_steps: Number specifying the max episode steps for this operation.
  continuous_actions: Whether to enable or require the continuous actions.
  use_sweep_reward: Whether to enable or require the use sweep reward.
  sweep_alpha: Numeric value used for the sweep alpha.
  sweep_beta: Numeric value used for the sweep beta.
  sweep_hold_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
  dsr_weight: Numeric value used for the dsr weight.
  sweep_weight: Numeric value used for the sweep weight.
  block_overnight: Whether to enable or require the block overnight.
  eod_risk: Key-value data used for the eod risk.
  use_vae: Whether to enable or require the use vae.
  vae: Vae used by the operation described above.
  strategy: Strategy used to select or evaluate trades.
  strategy_actions: Whether to enable or require the strategy actions.
  trade_setup_actions: Whether to enable or require the trade setup actions.
  candidate_geometry_actions: Whether the policy consumes the fixed candidate
      price-geometry observation tensor.
  agent_entry_execution: Whether the policy selects market or limit execution.
  entry_state_machine: Whether to enable or require the entry state machine.
  candidate_max_age_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
  arm_requires_retest: Whether to enable or require the arm requires retest.
  entry_state_observation: Whether to enable or require the entry state observation.
  observation_schema_version: Text or path value identifying the observation schema version.
  observation_age_scale_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
  reachable_r_validity_mask: Whether to append the reachable-R validity sequence channel.
  strict_research_eligibility: Whether to enable or require the strict research eligibility.
  strategy_reward: Strategy reward used by the operation described above.
  strategy_weight: Numeric value used for the strategy weight.
  sl_buffer_pts: Numeric value used for the sl buffer pts.
  pre_ny_by_date: Key-value data used for the pre ny by date.
  min_sl_atr_mult: Numeric value used for the min sl atr mult.
  min_sl_points: Numeric value used for the min sl points.
  max_entries_per_session: Numeric value used for the max entries per session.
  open_manipulation_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
  entry_cooldown_bars: Market bar or price data used for walk a trained RL ``model`` over *bars*/*features* and collect trades.
  reward_mode: Text or path value identifying the reward mode.
  equity_log_growth_scale: Numeric value used for the equity log growth scale.
  fixed_risk_usd: Numeric value used for the fixed risk usd.
  risk_band_max_usd: Numeric value used for the risk band max usd.
  risk_band_hold_below_usd: Numeric value used for the risk band hold below usd.
  risk_mode: Text or path value identifying the risk mode.
  allow_ema_exit: Whether to enable or require the allow ema exit.
  ema_runner_fraction: Numeric value used for the ema runner fraction.
  entry_intensity_threshold: Numeric value used for the entry intensity threshold.
  peak_trailing_dd_limit: Numeric value used for the peak trailing dd limit.
  tickbook: Tickbook used by the operation described above.
  tick_execution_required: Whether to enable or require the tick execution required.
  fill_delay_ms: Numeric value used for the fill delay ms.
  randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
  max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
  fill_latency_bars: Whole-M1-bar delay applied to entry orders.
  tick_fill_slippage_points: Market-fill slippage override. Defaults to the
      supplied ``cost_model.slippage_points``; explicit zero preserves a
      zero-slippage replay.
  execution_seed: Execution seed used by the operation described above.
  agent_direction_control: Whether to enable or require the agent direction control.
  direction_override_threshold: Numeric value used for the direction override threshold.
  sl_mode: Text or path value identifying the sl mode.
  tp_mode: Text or path value identifying the tp mode.
  tp_reference: Text or path value identifying the tp reference.
  allow_agent_sl_mode: Whether to enable or require the allow agent sl mode.
  sl_mode_defer_threshold: Numeric value used for the sl mode defer threshold.
  allow_agent_tp_mode: Whether to enable or require the allow agent tp mode.
  tp_mode_defer_threshold: Numeric value used for the tp mode defer threshold.
  allow_multi_tp: Whether to enable or require the allow multi tp.
  allow_simplex: Whether to enable or require the allow simplex.
  tp_breakeven_alpha: Numeric value used for the tp breakeven alpha.
  risk_floor: Numeric value used for the risk floor.
  mtf: Whether to enable or require the mtf.
  mtf_windows: Key-value data used for the mtf windows.
  regime_observation: Whether to enable or require the regime observation.
  feature_validity_channels: Whether sequence streams include per-feature finite masks.
  target_timeframes: Items supplied for the target timeframes, in input order.
  scheduled_session_closes: Key-value data used for the scheduled session closes.
  session_start: Text or path value identifying the session start.
  env: Environment whose state is read or updated.
  legacy_sequence_columns: Whether to enable or require the legacy sequence columns.
  sequence_columns_override: Exact saved input coordinates for a bounded replay.
  trading_policy: Key-value data used for the trading policy.
  limit_order_max_offset_atr: Maximum policy limit distance in ATR units.
  limit_order_max_ttl_bars: Maximum pending-limit lifetime in M1 bars.
  limit_order_require_trade_through: Whether limit fills require a trade through the price.
  server_side_protective_orders: Resolve attached SL/TP orders on triggering ticks.
  ```

- **Returns:**

  ```text
  dict with keys ``equity``, ``trades``, ``account``, ``breaches``,:
  ``breach_events``, ``n_sessions``, ``n_breach_sessions``,:
  ``n_sessions_with_trades``, ``n_sessions_skipped`` — the same shape:
  produced by ``simulation.backtest.run_backtest``.:
  ```

**Observed usage:**

1. [test fixture: `test_random_setup_baseline_uses_shared_rollout_decision_trace`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L105)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert schema.names[0] == "trade_setup"
    model = RandomEligibleSetupRolloutModel(
        RandomEligibleSetupPolicy(schema, seed=17, trade_probability=1.0)
    )

    result = evaluate_model(
        model,
        bars,
        features,
        env=env,
        strategy_actions=True,
        trade_setup_actions=True,
    )

    decisions = result["trade_setup_decisions"]
    assert len(decisions) == 4
    assert decisions["decision_id"].notna().all()
    assert decisions["decision_id"].is_unique
# … caller assertions omitted …
```

2. [test fixture: `test_model_choice_probabilities_survive_rollout_and_artifact_export`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L251)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert isinstance(schema, TradeSetupActionSchema)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    probabilities = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    probabilities[[NO_TRADE_ID, candidate_id]] = [0.25, 0.75]

    result = evaluate_model(
        _FixedSetupModel(schema, candidate_id, probabilities),
        bars,
        features,
        env=env,
        strategy_actions=True,
        trade_setup_actions=True,
    )
    run_dir = save_run(
        run_dir=tmp_path / "model-choice-trace",
        train_result=result,
        train_metrics=calculate_metrics(
            result["equity"],
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `evaluate_provider`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.rollout.trained_policy_rollout`

**Purpose:** Evaluate a backend-neutral decision provider through the trading environment.

**Exact API:** {py:obj}`evaluation.rollout.trained_policy_rollout.evaluate_provider` · **Source:** [evaluation/rollout/trained_policy_rollout.py:957](../../../../evaluation/rollout/trained_policy_rollout.py#L957)

**Inputs and outputs:**

- **Args:**

  ```text
  provider: Provider used by the operation described above.
  bars: Market bars to process.
  features: Feature values supplied to the operation.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_evaluate_provider_uses_the_same_trading_rollout`](../../../../tests/unit/evaluation/test_rollout.py#L225)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    provider = SB3DecisionProvider(
        _ScriptedModel(script),
        input_schema_version=OBSERVATION_SCHEMA_V1,
    )

    result = evaluate_provider(
        provider,
        bars=bars,
        features=features,
        obs_window=obs_window,
        initial_balance=100_000.0,
    )

    assert not result["trades"].empty
    assert result["completed_data_split"] is True
    assert result["equity"].index[0] == bars.index[obs_window]
    assert len(result["equity"]) == len(bars) - obs_window + 1
```

2. [test fixture: `test_supervised_provider_runs_through_shared_evaluation_path`](../../../../tests/unit/learning/test_learning_supervised_reference.py#L104)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    features = pd.DataFrame(0.0, index=index, columns=["f0"])
    features["last_swing_low"] = close - 5.0
    features["last_swing_high"] = close + 5.0

    result = evaluate_provider(
        provider,
        bars,
        features,
        obs_window=10,
        observation_schema_version="account-state-v1",
        block_overnight=False,
    )

    assert result["n_steps"] > 0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `make_action_fn`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.rollout.trained_policy_rollout`

**Purpose:** Return an observation → action callable with explicit action typing.

**Exact API:** {py:obj}`evaluation.rollout.trained_policy_rollout.make_action_fn` · **Source:** [evaluation/rollout/trained_policy_rollout.py:117](../../../../evaluation/rollout/trained_policy_rollout.py#L117)

**Inputs and outputs:**

- **Args:**

  ```text
  model: Model used for this operation.
  continuous_actions: Whether to enable or require the continuous actions.
  deterministic: Whether to enable or require the deterministic.
  strategy_actions: Whether to enable or require the strategy actions.
  ```

- **Returns:**

  ```text
  Result of return an observation → action callable with explicit action typing.
  ```

**Observed usage:**

1. [test fixture: `test_evaluation_rollout_routes_providers_through_semantic_adapter`](../../../../tests/unit/evaluation/test_decision_provider_rollout.py#L149)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_evaluation_rollout_routes_providers_through_semantic_adapter() -> None:
    action_schema = ActionSchemaRef(
        version="discrete-v1", key="hold-enter", coordinates=("hold", "enter"), kind="discrete"
    )
    provider = _Provider(Decision(DiscreteAction(1, "enter"), action_schema))
    action_fn = make_action_fn(provider)

    assert action_fn({"seq": np.ones((2, 3), dtype=np.float32)}) == 1
    assert provider.inputs[0][0].schema_version == "obs-v1"
```

2. [test fixture: `test_random_eligible_rollout_model_uses_shared_action_adapter`](../../../../tests/unit/evaluation/test_random_eligible_setup.py#L105)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    model = RandomEligibleSetupRolloutModel(policy)
    observation = _observation(2, 7, 31)
    expected = RandomEligibleSetupPolicy(schema, seed=31, normalized_risk=0.4)

    direct_action, recurrent_state = model.predict(observation, deterministic=True)
    rollout_action = make_action_fn(model, strategy_actions=True)(observation)

    np.testing.assert_array_equal(direct_action, expected(observation))
    np.testing.assert_array_equal(rollout_action, expected(observation))
    assert recurrent_state is None
    assert model.policy.hybrid_action_coordinates == schema.names
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
