# Simulation · `environment.trading_environment_factory`

This page contains 16 public callable records owned by `simulation.environment.trading_environment_factory`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_eval_common`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Kwargs shared by the in-loop dashboard slice and the final eval.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.build_eval_common` · **Source:** [simulation/environment/trading_environment_factory.py:216](../../../../simulation/environment/trading_environment_factory.py#L216)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  args: Parsed command-line arguments for this operation.
  env_vae: Env vae used by the operation described above.
  pre_ny_by_date: Key-value data used for the pre ny by date.
  arch: Arch used by the operation described above.
  tick_fill_slippage_points: Market-fill slippage override; defaults to
      ``costs.slippage_points``. Explicit zero preserves a zero-slippage replay.
  ```

- **Returns:**

  ```text
  Whether build eval common meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `evaluate_tier0_setup_baselines`](../../../../evaluation/rollout/matched_setup_baselines.py#L414)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        raise ValueError(f"unknown baseline_names: {unknown_policy_names}")
    if not policy_names:
        raise ValueError("baseline_names must select at least one policy")
    for baseline_name in policy_names:
        # Resolve anew to give every baseline fresh stateful strategy adapters.
        eval_common, _, _, _, _ = build_eval_common(
            effective_cfg,
            args=None,
            tick_fill_slippage_points=resolved_tick_slippage,
        )
        eval_common = dict(eval_common)
        eval_common["execution_seed"] = execution_seed

        # build_eval_common serves both environment construction and rollout.
        # Route values by each API's declared signature at this seam.
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `cost_model`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Build the broker ``CostModel`` from ``costs.*``.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.cost_model` · **Source:** [simulation/environment/trading_environment_factory.py:514](../../../../simulation/environment/trading_environment_factory.py#L514)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Result of build the broker ``CostModel`` from ``costs.*``.
  ```

**Observed usage:**

1. [test fixture: `test_configured_backtest_runner_resolves_static_daily_loss_semantics`](../../../../tests/unit/training/test_backtest_runner_policy.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configured_backtest_runner_resolves_static_daily_loss_semantics() -> None:
    cfg = load_config()

    policy = _configured_backtest_policy(cfg)
    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.daily_loss_includes_open_pnl
    assert policy.daily_loss_limit_pct == 0.05
    assert cost_model(cfg).slippage_points == float(cfg.costs.slippage_points) == 5.0
    assert not policy.repeated_payout
```

2. [production caller: `evaluate_tier0_setup_baselines`](../../../../evaluation/rollout/matched_setup_baselines.py#L365)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        raise TypeError("matched setup baselines require a DatetimeIndex")
    if len(bars) != len(features) or not bars.index.equals(features.index):
        raise ValueError("bars and features must have identical rows and ordered timestamps")
    try:
        resolved_tick_slippage = (
            float(cost_model(effective_cfg).slippage_points)
            if tick_fill_slippage_points is None
            else float(tick_fill_slippage_points)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("tick_fill_slippage_points must be finite and non-negative") from exc
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `eval_guardrail_kwargs`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Resolve percentage-based daily and maximum-loss rules for evaluation.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.eval_guardrail_kwargs` · **Source:** [simulation/environment/trading_environment_factory.py:111](../../../../simulation/environment/trading_environment_factory.py#L111)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``float`` values.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L259)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    eval_common = {
        "obs_window": cfg.env.obs_window,
        "initial_balance": cfg.account.initial_balance,
        "cost_model": resolved_cost_model,
        "guardrail_kwargs": eval_guardrail_kwargs(cfg),
        "risk_frac_range": risk_frac_range,
        "rr_ratio_range": rr_ratio_range,
        "sl_mode": str(cfg.risk.get("sl_mode", "fixed")),
        "tp_mode": str(cfg.risk.get("tp_mode", "fixed")),
        "tp_reference": str(cfg.risk.get("tp_reference", "structural")),
# … caller assertions omitted …
```

2. [production caller: `_run`](../../../../training/runner/backtest.py#L184)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            features=feats,
            policy=_random_policy,
            obs_window=cfg.env.obs_window,
            cost_model=cost_model(cfg),
            initial_balance=cfg.account.initial_balance,
            guardrail_kwargs=eval_guardrail_kwargs(cfg),
            max_loss_per_trade_usd=max_loss_per_trade,
            take_profit_per_trade_usd=take_profit_per_trade,
            eod_risk=dict(cfg.env.get("eod_risk", {})),
            sl_mode=str(cfg.risk.get("sl_mode", "fixed")),
            daily_pnl_basis=daily_pnl_basis,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `fill_delay_ms`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Milliseconds between the crossing tick and the SL/TP fill.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.fill_delay_ms` · **Source:** [simulation/environment/trading_environment_factory.py:352](../../../../simulation/environment/trading_environment_factory.py#L352)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``fill_delay_ms``.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L310)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "feature_validity_channels": bool(cfg.env.get("feature_validity_channels", False)),
        "entry_intensity_threshold": float(cfg.env.get("entry_intensity_threshold", 0.0)),
        "peak_trailing_dd_limit": float(cfg.env.get("peak_trailing_dd_limit", 0.0)),
        "agent_direction_control": bool(cfg.env.get("agent_direction_control", False)),
        "direction_override_threshold": float(cfg.env.get("direction_override_threshold", 0.0)),
        "fill_delay_ms": fill_delay_ms(cfg),
        "randomized_fill_latency_ms": randomized_fill_latency_ms(cfg),
        "tick_fill_slippage_points": float(resolved_market_slippage),
        "tick_execution_required": tick_execution_required(cfg),
        "max_tick_quote_wait_ms": max_tick_quote_wait_ms(cfg),
        "server_side_protective_orders": bool(
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L661)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ema_runner_fraction=float(cfg.env.get("ema_runner_fraction", 0.0)),
        tp_breakeven_alpha=float(cfg.env.get("tp_breakeven_alpha", 0.5)),
        risk_floor=float(cfg.env.get("risk_floor", 0.0005)),
        tickbook=configured_tickbook,
        tick_execution_required=tick_execution_required(cfg),
        fill_delay_ms=fill_delay_ms(cfg),
        randomized_fill_latency_ms=randomized_fill_latency_ms(cfg),
        max_tick_quote_wait_ms=max_tick_quote_wait_ms(cfg),
        server_side_protective_orders=bool(
            cfg.execution.get("server_side_protective_orders", False)
        ),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `guardrail_kwargs`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Resolve policy-specific hard/soft guardrails.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.guardrail_kwargs` · **Source:** [simulation/environment/trading_environment_factory.py:70](../../../../simulation/environment/trading_environment_factory.py#L70)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [production caller: `eval_guardrail_kwargs`](../../../../simulation/environment/trading_environment_factory.py#L120)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def eval_guardrail_kwargs(cfg: Any) -> dict[str, float]:
    kwargs = guardrail_kwargs(cfg)
    kwargs["trailing_dd_limit"] = 0.0
    kwargs["soft_trailing_dd_limit"] = 0.0
    return kwargs
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L601)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        bars=bars,
        features=features,
        obs_window=cfg.env.obs_window,
        initial_balance=cfg.account.initial_balance,
        cost_model=cost_model(cfg),
        guardrail_kwargs=guardrail_kwargs(cfg),
        risk_frac_range=risk_frac_range,
        rr_ratio_range=rr_ratio_range,
        swing_buffer_pts=cfg.risk.swing_buffer_pts,
        sl_mode=str(cfg.risk.get("sl_mode", "fixed")),
        tp_mode=str(cfg.risk.get("tp_mode", "fixed")),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `make_env`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Construct a configured trading environment and its feature/observation adapters.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.make_env` · **Source:** [simulation/environment/trading_environment_factory.py:541](../../../../simulation/environment/trading_environment_factory.py#L541)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars used by the simulation.
  features: Causal feature frame aligned with bars.
  cfg: Resolved run configuration.
  algo: Learning algorithm name used to select policy settings.
  reward: Reward implementation to construct.
  episodic: Whether episode boundaries reset account state.
  use_vae: Enable the configured VAE observation path.
  vae: Optional fitted VAE used by that path.
  pre_ny_by_date: Optional per-session pre-market context.
  obs_features_mmap: Optional memory-mapped observation feature file.
  tickbook: Optional tick-level execution data.
  arch: Optional encoder architecture identifier.
  ```

- **Returns:**

  ```text
  Configured Gymnasium trading environment.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = make_env(bars=..., features=..., cfg=..., algo=..., reward=..., episodic=..., use_vae=..., vae=..., pre_ny_by_date=..., obs_features_mmap=..., tickbook=..., arch=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `max_episode_steps`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Parse ``env.max_episode_steps``; YAML ``null`` → full-year episode.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.max_episode_steps` · **Source:** [simulation/environment/trading_environment_factory.py:126](../../../../simulation/environment/trading_environment_factory.py#L126)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Result of parse ``env.max_episode_steps``; YAML ``null`` → full-year episode.
  ```

**Observed usage:**

1. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L612)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        tp_reference=str(cfg.risk.get("tp_reference", "structural")),
        contract_size=cfg.account.contract_size,
        max_loss_per_trade_usd=max_loss_per_trade(cfg),
        lot_step=float(cfg.risk.get("lot_step", 0.01)),
        dsr_eta=cfg.env.reward_dsr_eta,
        max_episode_steps=max_episode_steps(cfg),
        episodic=episodic,
        continuous_actions=continuous_actions,
        use_sweep_reward=use_sweep_reward,
        strategy=strategy,
        strategy_actions=bool(cfg.env.get("strategy_actions", False)),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `max_loss_per_trade`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Static sizing ceiling; current-equity percentages are enforced at runtime.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.max_loss_per_trade` · **Source:** [simulation/environment/trading_environment_factory.py:53](../../../../simulation/environment/trading_environment_factory.py#L53)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``max_loss_per_trade``.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L270)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "swing_buffer_pts": cfg.risk.swing_buffer_pts,
        "contract_size": cfg.account.contract_size,
        "min_lot": float(cfg.risk.min_lot),
        "max_lot": float(cfg.risk.max_lot),
        "lot_step": float(cfg.risk.get("lot_step", 0.01)),
        "max_loss_per_trade_usd": max_loss_per_trade(cfg),
        "dsr_eta": cfg.env.reward_dsr_eta,
        "continuous_actions": (args.algo == "sac") if args is not None else False,
        "use_sweep_reward": (args.reward == "sweep") if args is not None else False,
        "block_overnight": bool(cfg.env.get("block_overnight", True)),
        "eod_risk": dict(cfg.env.get("eod_risk", {})),
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L609)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        swing_buffer_pts=cfg.risk.swing_buffer_pts,
        sl_mode=str(cfg.risk.get("sl_mode", "fixed")),
        tp_mode=str(cfg.risk.get("tp_mode", "fixed")),
        tp_reference=str(cfg.risk.get("tp_reference", "structural")),
        contract_size=cfg.account.contract_size,
        max_loss_per_trade_usd=max_loss_per_trade(cfg),
        lot_step=float(cfg.risk.get("lot_step", 0.01)),
        dsr_eta=cfg.env.reward_dsr_eta,
        max_episode_steps=max_episode_steps(cfg),
        episodic=episodic,
        continuous_actions=continuous_actions,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `max_tick_quote_wait_ms`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Maximum permitted delay from sampled arrival to the next tick quote.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.max_tick_quote_wait_ms` · **Source:** [simulation/environment/trading_environment_factory.py:449](../../../../simulation/environment/trading_environment_factory.py#L449)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``max_tick_quote_wait_ms``.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L314)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "direction_override_threshold": float(cfg.env.get("direction_override_threshold", 0.0)),
        "fill_delay_ms": fill_delay_ms(cfg),
        "randomized_fill_latency_ms": randomized_fill_latency_ms(cfg),
        "tick_fill_slippage_points": float(resolved_market_slippage),
        "tick_execution_required": tick_execution_required(cfg),
        "max_tick_quote_wait_ms": max_tick_quote_wait_ms(cfg),
        "server_side_protective_orders": bool(
            cfg.execution.get("server_side_protective_orders", False)
        ),
        "execution_seed": (
            int(getattr(args, "seed"))
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L663)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        risk_floor=float(cfg.env.get("risk_floor", 0.0005)),
        tickbook=configured_tickbook,
        tick_execution_required=tick_execution_required(cfg),
        fill_delay_ms=fill_delay_ms(cfg),
        randomized_fill_latency_ms=randomized_fill_latency_ms(cfg),
        max_tick_quote_wait_ms=max_tick_quote_wait_ms(cfg),
        server_side_protective_orders=bool(
            cfg.execution.get("server_side_protective_orders", False)
        ),
        tick_fill_slippage_points=cost_model(cfg).slippage_points,
        use_vae=use_vae,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `mtf_settings`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Enable multi-window observations for each architecture that consumes them.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.mtf_settings` · **Source:** [simulation/environment/trading_environment_factory.py:467](../../../../simulation/environment/trading_environment_factory.py#L467)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  arch: Arch used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether mtf settings meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L249)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    resolved_market_slippage = (
        resolved_cost_model.slippage_points
        if tick_fill_slippage_points is None
        else float(tick_fill_slippage_points)
    )
    use_mtf, mtf_windows = mtf_settings(cfg, arch)
    observation_schema_version = (
        "account-state-v3-repeated-payout"
        if policy.repeated_payout
        else str(cfg.env.get("observation_schema_version", "account-state-v1"))
    )
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L577)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    continuous_actions = algo == "sac"
    use_sweep_reward = reward == "sweep"
    use_mtf, mtf_windows = mtf_settings(cfg, arch)
    strategy, strategy_reward, strategy_weight = strategy_from_cfg(cfg)
    risk_frac_range, rr_ratio_range = strategy_risk_ranges(cfg)
    policy = resolve_trading_policy(cfg)
    observation_schema_version = (
        "account-state-v3-repeated-payout"
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `randomized_fill_latency_ms`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Maximum exclusive randomized tick latency; zero means immediate tick.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.randomized_fill_latency_ms` · **Source:** [simulation/environment/trading_environment_factory.py:394](../../../../simulation/environment/trading_environment_factory.py#L394)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``randomized_fill_latency_ms``.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L311)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "entry_intensity_threshold": float(cfg.env.get("entry_intensity_threshold", 0.0)),
        "peak_trailing_dd_limit": float(cfg.env.get("peak_trailing_dd_limit", 0.0)),
        "agent_direction_control": bool(cfg.env.get("agent_direction_control", False)),
        "direction_override_threshold": float(cfg.env.get("direction_override_threshold", 0.0)),
        "fill_delay_ms": fill_delay_ms(cfg),
        "randomized_fill_latency_ms": randomized_fill_latency_ms(cfg),
        "tick_fill_slippage_points": float(resolved_market_slippage),
        "tick_execution_required": tick_execution_required(cfg),
        "max_tick_quote_wait_ms": max_tick_quote_wait_ms(cfg),
        "server_side_protective_orders": bool(
            cfg.execution.get("server_side_protective_orders", False)
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L590)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    configured_tickbook = (
        tickbook
        if (
            tick_execution_required(cfg)
            or randomized_fill_latency_ms(cfg) > 0.0
            or bool(cfg.env.get("agent_entry_execution", False))
        )
        else None
    )
    return TradingEnv(
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `regime_observation_enabled`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Resolve the opt-in D1 branch and require its train-only source scaling.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.regime_observation_enabled` · **Source:** [simulation/environment/trading_environment_factory.py:425](../../../../simulation/environment/trading_environment_factory.py#L425)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Whether regime observation enabled meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L335)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "tp_mode_defer_threshold": float(cfg.env.get("tp_mode_defer_threshold", 0.1)),
        "tp_breakeven_alpha": float(cfg.env.get("tp_breakeven_alpha", 0.5)),
        "risk_floor": float(cfg.env.get("risk_floor", 0.0005)),
        "mtf": use_mtf,
        "mtf_windows": mtf_windows,
        "regime_observation": regime_observation_enabled(cfg),
        "target_timeframes": tuple(
            str(tf) for tf in cfg.risk.get("target_timeframes", ["M5", "M15", "H1"])
        ),
        "scheduled_session_closes": scheduled_session_closes(cfg),
        "session_start": str(cfg.session.get("start", "16:30")),
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L674)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        vae=vae,
        pre_ny_by_date=pre_ny_by_date,
        obs_features_mmap=obs_features_mmap,
        mtf=use_mtf,
        mtf_windows=mtf_windows,
        regime_observation=regime_observation_enabled(cfg),
        target_timeframes=tuple(
            str(tf) for tf in cfg.risk.get("target_timeframes", ["M5", "M15", "H1"])
        ),
        scheduled_session_closes=scheduled_session_closes(cfg),
        session_start=str(cfg.session.get("start", "16:30")),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `scheduled_session_closes`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Read the configured market-data session calendar.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.scheduled_session_closes` · **Source:** [simulation/environment/trading_environment_factory.py:500](../../../../simulation/environment/trading_environment_factory.py#L500)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``str`` values.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L339)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "mtf_windows": mtf_windows,
        "regime_observation": regime_observation_enabled(cfg),
        "target_timeframes": tuple(
            str(tf) for tf in cfg.risk.get("target_timeframes", ["M5", "M15", "H1"])
        ),
        "scheduled_session_closes": scheduled_session_closes(cfg),
        "session_start": str(cfg.session.get("start", "16:30")),
        "trading_policy": policy.to_dict(),
        "fill_latency_bars": fill_latency_bars(cfg),
        "limit_order_max_offset_atr": float(cfg.execution.get("limit_order_max_offset_atr", 1.0)),
        "limit_order_max_ttl_bars": int(cfg.execution.get("limit_order_max_ttl_bars", 60)),
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L678)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        mtf_windows=mtf_windows,
        regime_observation=regime_observation_enabled(cfg),
        target_timeframes=tuple(
            str(tf) for tf in cfg.risk.get("target_timeframes", ["M5", "M15", "H1"])
        ),
        scheduled_session_closes=scheduled_session_closes(cfg),
        session_start=str(cfg.session.get("start", "16:30")),
        trading_policy=policy.to_dict(),
        fill_latency_bars=fill_latency_bars(cfg),
        limit_order_max_offset_atr=float(cfg.execution.get("limit_order_max_offset_atr", 1.0)),
        limit_order_max_ttl_bars=int(cfg.execution.get("limit_order_max_ttl_bars", 60)),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `strategy_from_cfg`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Build (strategy, strategy_reward, strategy_weight) from merged config.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.strategy_from_cfg` · **Source:** [simulation/environment/trading_environment_factory.py:143](../../../../simulation/environment/trading_environment_factory.py#L143)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Values returned by ``strategy_from_cfg``, in the declared order.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L238)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    strategy, strategy_reward, strategy_weight = strategy_from_cfg(cfg)
    strategy_actions = bool(cfg.env.get("strategy_actions", False))
    sl_buffer_pts = float(cfg.env.get("sl_buffer_pts", 0.0))
    risk_frac_range, rr_ratio_range = strategy_risk_ranges(cfg)
    policy = resolve_trading_policy(cfg)
    resolved_cost_model = cost_model(cfg)
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L578)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    continuous_actions = algo == "sac"
    use_sweep_reward = reward == "sweep"
    use_mtf, mtf_windows = mtf_settings(cfg, arch)
    strategy, strategy_reward, strategy_weight = strategy_from_cfg(cfg)
    risk_frac_range, rr_ratio_range = strategy_risk_ranges(cfg)
    policy = resolve_trading_policy(cfg)
    observation_schema_version = (
        "account-state-v3-repeated-payout"
        if policy.repeated_payout
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `strategy_risk_ranges`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Risk/RR ranges for TradingEnv; repeated-payout owns the risk range.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.strategy_risk_ranges` · **Source:** [simulation/environment/trading_environment_factory.py:23](../../../../simulation/environment/trading_environment_factory.py#L23)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Values returned by ``strategy_risk_ranges``, in the declared order.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L241)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    strategy, strategy_reward, strategy_weight = strategy_from_cfg(cfg)
    strategy_actions = bool(cfg.env.get("strategy_actions", False))
    sl_buffer_pts = float(cfg.env.get("sl_buffer_pts", 0.0))
    risk_frac_range, rr_ratio_range = strategy_risk_ranges(cfg)
    policy = resolve_trading_policy(cfg)
    resolved_cost_model = cost_model(cfg)
    resolved_market_slippage = (
        resolved_cost_model.slippage_points
        if tick_fill_slippage_points is None
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L579)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    continuous_actions = algo == "sac"
    use_sweep_reward = reward == "sweep"
    use_mtf, mtf_windows = mtf_settings(cfg, arch)
    strategy, strategy_reward, strategy_weight = strategy_from_cfg(cfg)
    risk_frac_range, rr_ratio_range = strategy_risk_ranges(cfg)
    policy = resolve_trading_policy(cfg)
    observation_schema_version = (
        "account-state-v3-repeated-payout"
        if policy.repeated_payout
        else str(cfg.env.get("observation_schema_version", "account-state-v1"))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `tick_execution_required`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Whether the effective config forbids candle-priced execution fills.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.tick_execution_required` · **Source:** [simulation/environment/trading_environment_factory.py:412](../../../../simulation/environment/trading_environment_factory.py#L412)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Whether tick execution required meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L313)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "agent_direction_control": bool(cfg.env.get("agent_direction_control", False)),
        "direction_override_threshold": float(cfg.env.get("direction_override_threshold", 0.0)),
        "fill_delay_ms": fill_delay_ms(cfg),
        "randomized_fill_latency_ms": randomized_fill_latency_ms(cfg),
        "tick_fill_slippage_points": float(resolved_market_slippage),
        "tick_execution_required": tick_execution_required(cfg),
        "max_tick_quote_wait_ms": max_tick_quote_wait_ms(cfg),
        "server_side_protective_orders": bool(
            cfg.execution.get("server_side_protective_orders", False)
        ),
        "execution_seed": (
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L589)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        else str(cfg.env.get("observation_schema_version", "account-state-v1"))
    )
    configured_tickbook = (
        tickbook
        if (
            tick_execution_required(cfg)
            or randomized_fill_latency_ms(cfg) > 0.0
            or bool(cfg.env.get("agent_entry_execution", False))
        )
        else None
    )
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
