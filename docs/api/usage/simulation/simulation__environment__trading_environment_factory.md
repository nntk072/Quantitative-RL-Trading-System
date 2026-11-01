# Simulation · `environment.trading_environment_factory`

This page contains 16 public callable records owned by `simulation.environment.trading_environment_factory`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_eval_common`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Kwargs shared by the in-loop dashboard slice and the final eval.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.build_eval_common` · **Source:** [simulation/environment/trading_environment_factory.py:220](../../../../simulation/environment/trading_environment_factory.py#L220)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  args: Parsed command-line arguments for this operation.
  env_vae: Env vae used by the operation described above.
  pre_ny_by_date: Key-value data used for the pre ny by date.
  arch: Arch used by the operation described above.
  tick_fill_slippage_points: Numeric value used for the tick fill slippage points.
  ```

- **Returns:**

  ```text
  Whether build eval common meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_eval_common(cfg=..., args=..., env_vae=..., pre_ny_by_date=..., arch=..., tick_fill_slippage_points=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `cost_model`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Build the broker ``CostModel`` from ``costs.*``.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.cost_model` · **Source:** [simulation/environment/trading_environment_factory.py:471](../../../../simulation/environment/trading_environment_factory.py#L471)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L255)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        else str(cfg.env.get("observation_schema_version", "account-state-v1"))
    )
    eval_common = {
        "obs_window": cfg.env.obs_window,
        "initial_balance": cfg.account.initial_balance,
        "cost_model": cost_model(cfg),
        "guardrail_kwargs": eval_guardrail_kwargs(cfg),
        "risk_frac_range": risk_frac_range,
        "rr_ratio_range": rr_ratio_range,
        "sl_mode": str(cfg.risk.get("sl_mode", "fixed")),
        "tp_mode": str(cfg.risk.get("tp_mode", "fixed")),
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L548)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    return TradingEnv(
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
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `eval_guardrail_kwargs`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** FTMO rules for train/test rollouts: daily $5k + max $10k from initial.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.eval_guardrail_kwargs` · **Source:** [simulation/environment/trading_environment_factory.py:115](../../../../simulation/environment/trading_environment_factory.py#L115)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L256)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    eval_common = {
        "obs_window": cfg.env.obs_window,
        "initial_balance": cfg.account.initial_balance,
        "cost_model": cost_model(cfg),
        "guardrail_kwargs": eval_guardrail_kwargs(cfg),
        "risk_frac_range": risk_frac_range,
        "rr_ratio_range": rr_ratio_range,
        "sl_mode": str(cfg.risk.get("sl_mode", "fixed")),
        "tp_mode": str(cfg.risk.get("tp_mode", "fixed")),
        "tp_reference": str(cfg.risk.get("tp_reference", "structural")),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `fill_delay_ms`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Milliseconds between the crossing tick and the SL/TP fill.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.fill_delay_ms` · **Source:** [simulation/environment/trading_environment_factory.py:334](../../../../simulation/environment/trading_environment_factory.py#L334)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L301)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "observation_age_scale_bars": float(cfg.env.get("observation_age_scale_bars", 60.0)),
        "entry_intensity_threshold": float(cfg.env.get("entry_intensity_threshold", 0.0)),
        "peak_trailing_dd_limit": float(cfg.env.get("peak_trailing_dd_limit", 0.0)),
        "agent_direction_control": bool(cfg.env.get("agent_direction_control", False)),
        "direction_override_threshold": float(cfg.env.get("direction_override_threshold", 0.0)),
        "fill_delay_ms": fill_delay_ms(cfg),
        "randomized_fill_latency_ms": randomized_fill_latency_ms(cfg),
        "tick_fill_slippage_points": float(tick_fill_slippage_points),
        "tick_execution_required": tick_execution_required(cfg),
        "max_tick_quote_wait_ms": max_tick_quote_wait_ms(cfg),
        "execution_seed": (
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L605)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ema_runner_fraction=float(cfg.env.get("ema_runner_fraction", 0.0)),
        tp_breakeven_alpha=float(cfg.env.get("tp_breakeven_alpha", 0.5)),
        risk_floor=float(cfg.env.get("risk_floor", 0.0005)),
        tickbook=tickbook,
        tick_execution_required=tick_execution_required(cfg),
        fill_delay_ms=fill_delay_ms(cfg),
        randomized_fill_latency_ms=randomized_fill_latency_ms(cfg),
        max_tick_quote_wait_ms=max_tick_quote_wait_ms(cfg),
        tick_fill_slippage_points=0.0,
        use_vae=use_vae,
        vae=vae,
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

1. [production caller: `eval_guardrail_kwargs`](../../../../simulation/environment/trading_environment_factory.py#L124)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def eval_guardrail_kwargs(cfg: Any) -> dict[str, float]:
    kwargs = guardrail_kwargs(cfg)
    kwargs["trailing_dd_limit"] = 0.0
    kwargs["soft_trailing_dd_limit"] = 0.0
    return kwargs
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L549)

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

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.make_env` · **Source:** [simulation/environment/trading_environment_factory.py:498](../../../../simulation/environment/trading_environment_factory.py#L498)

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

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.max_episode_steps` · **Source:** [simulation/environment/trading_environment_factory.py:130](../../../../simulation/environment/trading_environment_factory.py#L130)

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

1. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L559)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        tp_mode=str(cfg.risk.get("tp_mode", "fixed")),
        tp_reference=str(cfg.risk.get("tp_reference", "structural")),
        contract_size=cfg.account.contract_size,
        max_loss_per_trade_usd=max_loss_per_trade(cfg),
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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L264)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "sl_mode": str(cfg.risk.get("sl_mode", "fixed")),
        "tp_mode": str(cfg.risk.get("tp_mode", "fixed")),
        "tp_reference": str(cfg.risk.get("tp_reference", "structural")),
        "swing_buffer_pts": cfg.risk.swing_buffer_pts,
        "contract_size": cfg.account.contract_size,
        "max_loss_per_trade_usd": max_loss_per_trade(cfg),
        "dsr_eta": cfg.env.reward_dsr_eta,
        "continuous_actions": (args.algo == "sac") if args is not None else False,
        "use_sweep_reward": (args.reward == "sweep") if args is not None else False,
        "block_overnight": bool(cfg.env.get("block_overnight", True)),
        "eod_risk": dict(cfg.env.get("eod_risk", {})),
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L557)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        swing_buffer_pts=cfg.risk.swing_buffer_pts,
        sl_mode=str(cfg.risk.get("sl_mode", "fixed")),
        tp_mode=str(cfg.risk.get("tp_mode", "fixed")),
        tp_reference=str(cfg.risk.get("tp_reference", "structural")),
        contract_size=cfg.account.contract_size,
        max_loss_per_trade_usd=max_loss_per_trade(cfg),
        dsr_eta=cfg.env.reward_dsr_eta,
        max_episode_steps=max_episode_steps(cfg),
        episodic=episodic,
        continuous_actions=continuous_actions,
        use_sweep_reward=use_sweep_reward,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `max_tick_quote_wait_ms`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Maximum permitted delay from sampled arrival to the next tick quote.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.max_tick_quote_wait_ms` · **Source:** [simulation/environment/trading_environment_factory.py:407](../../../../simulation/environment/trading_environment_factory.py#L407)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L305)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "direction_override_threshold": float(cfg.env.get("direction_override_threshold", 0.0)),
        "fill_delay_ms": fill_delay_ms(cfg),
        "randomized_fill_latency_ms": randomized_fill_latency_ms(cfg),
        "tick_fill_slippage_points": float(tick_fill_slippage_points),
        "tick_execution_required": tick_execution_required(cfg),
        "max_tick_quote_wait_ms": max_tick_quote_wait_ms(cfg),
        "execution_seed": (
            int(getattr(args, "seed"))
            if args is not None and getattr(args, "seed", None) is not None
            else None
        ),
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L607)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        risk_floor=float(cfg.env.get("risk_floor", 0.0005)),
        tickbook=tickbook,
        tick_execution_required=tick_execution_required(cfg),
        fill_delay_ms=fill_delay_ms(cfg),
        randomized_fill_latency_ms=randomized_fill_latency_ms(cfg),
        max_tick_quote_wait_ms=max_tick_quote_wait_ms(cfg),
        tick_fill_slippage_points=0.0,
        use_vae=use_vae,
        vae=vae,
        pre_ny_by_date=pre_ny_by_date,
        obs_features_mmap=obs_features_mmap,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `mtf_settings`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Enable multi-window observations for each architecture that consumes them.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.mtf_settings` · **Source:** [simulation/environment/trading_environment_factory.py:425](../../../../simulation/environment/trading_environment_factory.py#L425)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L246)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    strategy, strategy_reward, strategy_weight = strategy_from_cfg(cfg)
    strategy_actions = bool(cfg.env.get("strategy_actions", False))
    sl_buffer_pts = float(cfg.env.get("sl_buffer_pts", 0.0))
    risk_frac_range, rr_ratio_range = strategy_risk_ranges(cfg)
    policy = resolve_trading_policy(cfg)
    use_mtf, mtf_windows = mtf_settings(cfg, arch)
    observation_schema_version = (
        "account-state-v3-repeated-payout"
        if policy.repeated_payout
        else str(cfg.env.get("observation_schema_version", "account-state-v1"))
    )
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L534)

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

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.randomized_fill_latency_ms` · **Source:** [simulation/environment/trading_environment_factory.py:352](../../../../simulation/environment/trading_environment_factory.py#L352)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L302)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "entry_intensity_threshold": float(cfg.env.get("entry_intensity_threshold", 0.0)),
        "peak_trailing_dd_limit": float(cfg.env.get("peak_trailing_dd_limit", 0.0)),
        "agent_direction_control": bool(cfg.env.get("agent_direction_control", False)),
        "direction_override_threshold": float(cfg.env.get("direction_override_threshold", 0.0)),
        "fill_delay_ms": fill_delay_ms(cfg),
        "randomized_fill_latency_ms": randomized_fill_latency_ms(cfg),
        "tick_fill_slippage_points": float(tick_fill_slippage_points),
        "tick_execution_required": tick_execution_required(cfg),
        "max_tick_quote_wait_ms": max_tick_quote_wait_ms(cfg),
        "execution_seed": (
            int(getattr(args, "seed"))
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L606)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        tp_breakeven_alpha=float(cfg.env.get("tp_breakeven_alpha", 0.5)),
        risk_floor=float(cfg.env.get("risk_floor", 0.0005)),
        tickbook=tickbook,
        tick_execution_required=tick_execution_required(cfg),
        fill_delay_ms=fill_delay_ms(cfg),
        randomized_fill_latency_ms=randomized_fill_latency_ms(cfg),
        max_tick_quote_wait_ms=max_tick_quote_wait_ms(cfg),
        tick_fill_slippage_points=0.0,
        use_vae=use_vae,
        vae=vae,
        pre_ny_by_date=pre_ny_by_date,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `regime_observation_enabled`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Resolve the opt-in D1 branch and require its train-only source scaling.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.regime_observation_enabled` · **Source:** [simulation/environment/trading_environment_factory.py:383](../../../../simulation/environment/trading_environment_factory.py#L383)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L323)

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

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L615)

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

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.scheduled_session_closes` · **Source:** [simulation/environment/trading_environment_factory.py:457](../../../../simulation/environment/trading_environment_factory.py#L457)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L327)

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
    }
    return eval_common, strategy, strategy_reward, strategy_weight, strategy_actions
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L619)

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
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `strategy_from_cfg`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.trading_environment_factory`

**Purpose:** Build (strategy, strategy_reward, strategy_weight) from merged config.

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.strategy_from_cfg` · **Source:** [simulation/environment/trading_environment_factory.py:147](../../../../simulation/environment/trading_environment_factory.py#L147)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L241)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    strategy, strategy_reward, strategy_weight = strategy_from_cfg(cfg)
    strategy_actions = bool(cfg.env.get("strategy_actions", False))
    sl_buffer_pts = float(cfg.env.get("sl_buffer_pts", 0.0))
    risk_frac_range, rr_ratio_range = strategy_risk_ranges(cfg)
    policy = resolve_trading_policy(cfg)
    use_mtf, mtf_windows = mtf_settings(cfg, arch)
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L535)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L244)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    strategy, strategy_reward, strategy_weight = strategy_from_cfg(cfg)
    strategy_actions = bool(cfg.env.get("strategy_actions", False))
    sl_buffer_pts = float(cfg.env.get("sl_buffer_pts", 0.0))
    risk_frac_range, rr_ratio_range = strategy_risk_ranges(cfg)
    policy = resolve_trading_policy(cfg)
    use_mtf, mtf_windows = mtf_settings(cfg, arch)
    observation_schema_version = (
        "account-state-v3-repeated-payout"
        if policy.repeated_payout
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L536)

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

**Exact API:** {py:obj}`simulation.environment.trading_environment_factory.tick_execution_required` · **Source:** [simulation/environment/trading_environment_factory.py:370](../../../../simulation/environment/trading_environment_factory.py#L370)

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

1. [production caller: `build_eval_common`](../../../../simulation/environment/trading_environment_factory.py#L304)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "agent_direction_control": bool(cfg.env.get("agent_direction_control", False)),
        "direction_override_threshold": float(cfg.env.get("direction_override_threshold", 0.0)),
        "fill_delay_ms": fill_delay_ms(cfg),
        "randomized_fill_latency_ms": randomized_fill_latency_ms(cfg),
        "tick_fill_slippage_points": float(tick_fill_slippage_points),
        "tick_execution_required": tick_execution_required(cfg),
        "max_tick_quote_wait_ms": max_tick_quote_wait_ms(cfg),
        "execution_seed": (
            int(getattr(args, "seed"))
            if args is not None and getattr(args, "seed", None) is not None
            else None
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L604)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        allow_ema_exit=bool(cfg.env.get("allow_ema_exit", True)),
        ema_runner_fraction=float(cfg.env.get("ema_runner_fraction", 0.0)),
        tp_breakeven_alpha=float(cfg.env.get("tp_breakeven_alpha", 0.5)),
        risk_floor=float(cfg.env.get("risk_floor", 0.0005)),
        tickbook=tickbook,
        tick_execution_required=tick_execution_required(cfg),
        fill_delay_ms=fill_delay_ms(cfg),
        randomized_fill_latency_ms=randomized_fill_latency_ms(cfg),
        max_tick_quote_wait_ms=max_tick_quote_wait_ms(cfg),
        tick_fill_slippage_points=0.0,
        use_vae=use_vae,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
