# Configuration reference

This inventory is generated from [`config/base/default.yaml`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/config/base/default.yaml).
It lists leaf keys, their YAML defaults, inferred value types, and the owning
domain section. OmegaConf interpolation expressions are shown literally; their
resolved values depend on the referenced keys and run configuration.

The inventory describes defaults, not every valid override. Schema validation
lives in [`configuration/schema.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/configuration/schema.py); key
resolution and merging live in [`configuration/configuration_loader.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/configuration/configuration_loader.py).
The owner column groups consumers by domain; it does not imply that every key
is read by every listed package.

| Key path | Type | Default | Owning domain |
|---|---|---|---|
| `account.contract_size` | `number` | `1.0` | `trading/account` |
| `account.currency` | `string` | `"USD"` | `trading/account` |
| `account.initial_balance` | `number` | `100000.0` | `trading/account` |
| `account.leverage` | `integer` | `50` | `trading/account` |
| `account.margin_pct` | `number` | `0.02` | `trading/account` |
| `agent.arch` | `string` | `"tcn"` | `learning/rl` |
| `agent.head_arch.gru` | `array` | `[256,128]` | `learning/rl` |
| `agent.head_arch.lite_tcn` | `array` | `[128,64]` | `learning/rl` |
| `agent.head_arch.mtf` | `array` | `[256,128]` | `learning/rl` |
| `agent.head_arch.mtf_empty_stream_masked_v1` | `array` | `[256,128]` | `learning/rl` |
| `agent.head_arch.mtf_m1_tcn_htf_lite_reasoning` | `array` | `[256,128]` | `learning/rl` |
| `agent.head_arch.mtf_m1_tcn_htf_snapshot_reasoning` | `array` | `[256,128]` | `learning/rl` |
| `agent.head_arch.mtf_reasoning` | `array` | `[256,128]` | `learning/rl` |
| `agent.head_arch.mtf_shared_tcn_reasoning` | `array` | `[256,128]` | `learning/rl` |
| `agent.head_arch.tcn` | `array` | `[256,128]` | `learning/rl` |
| `agent.head_arch.transformer` | `array` | `[256,128]` | `learning/rl` |
| `agent.lite_tcn.channels` | `integer` | `96` | `learning/rl` |
| `agent.lite_tcn.dilations` | `array` | `[1,4,10]` | `learning/rl` |
| `agent.lite_tcn.dropout` | `number` | `0.1` | `learning/rl` |
| `agent.lite_tcn.kernel_size` | `integer` | `3` | `learning/rl` |
| `agent.lite_tcn.latent_dim` | `integer` | `128` | `learning/rl` |
| `agent.mtf_empty_stream_masked_v1.channels` | `array` | `[128,128,256,256]` | `learning/rl` |
| `agent.mtf_empty_stream_masked_v1.dropout` | `number` | `0.1` | `learning/rl` |
| `agent.mtf_empty_stream_masked_v1.kernel_size` | `integer` | `3` | `learning/rl` |
| `agent.mtf_empty_stream_masked_v1.latent_dim` | `integer` | `128` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_lite_reasoning.adapter_dim` | `integer` | `32` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_lite_reasoning.attention_heads` | `integer` | `4` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_lite_reasoning.channels` | `array` | `[128,128,256,256]` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_lite_reasoning.dropout` | `number` | `0.1` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_lite_reasoning.feedforward_dim` | `integer` | `256` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_lite_reasoning.kernel_size` | `integer` | `3` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_lite_reasoning.latent_dim` | `integer` | `128` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_snapshot_reasoning.adapter_dim` | `integer` | `32` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_snapshot_reasoning.attention_heads` | `integer` | `4` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_snapshot_reasoning.channels` | `array` | `[128,128,256,256]` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_snapshot_reasoning.dropout` | `number` | `0.1` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_snapshot_reasoning.feedforward_dim` | `integer` | `256` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_snapshot_reasoning.kernel_size` | `integer` | `3` | `learning/rl` |
| `agent.mtf_m1_tcn_htf_snapshot_reasoning.latent_dim` | `integer` | `128` | `learning/rl` |
| `agent.mtf_reasoning.attention_heads` | `integer` | `4` | `learning/rl` |
| `agent.mtf_reasoning.dropout` | `number` | `0.1` | `learning/rl` |
| `agent.mtf_reasoning.feedforward_dim` | `integer` | `256` | `learning/rl` |
| `agent.mtf_reasoning.latent_dim` | `integer` | `128` | `learning/rl` |
| `agent.mtf_shared_tcn_reasoning.adapter_dim` | `integer` | `64` | `learning/rl` |
| `agent.mtf_shared_tcn_reasoning.attention_heads` | `integer` | `4` | `learning/rl` |
| `agent.mtf_shared_tcn_reasoning.channels` | `array` | `[128,128,256,256]` | `learning/rl` |
| `agent.mtf_shared_tcn_reasoning.dropout` | `number` | `0.1` | `learning/rl` |
| `agent.mtf_shared_tcn_reasoning.feedforward_dim` | `integer` | `256` | `learning/rl` |
| `agent.mtf_shared_tcn_reasoning.kernel_size` | `integer` | `3` | `learning/rl` |
| `agent.mtf_shared_tcn_reasoning.latent_dim` | `integer` | `128` | `learning/rl` |
| `agent.type` | `string` | `"ppo"` | `learning/rl` |
| `agent.use_narrative` | `boolean` | `false` | `learning/rl` |
| `auxiliary.aux_weight` | `number` | `0.0` | `learning/supervised` |
| `auxiliary.grad_steps` | `integer` | `4` | `learning/supervised` |
| `auxiliary.lr` | `number` | `0.0001` | `learning/supervised` |
| `auxiliary.prediction_horizon` | `integer` | `5` | `learning/supervised` |
| `backtest.validation.include_costs_in_trade_risk` | `boolean` | `true` | `simulation/backtest` |
| `backtest.validation.max_loss_per_trade_usd` | `number` | `900.0` | `simulation/backtest` |
| `backtest.validation.take_profit_per_trade_usd` | `null` | `null` | `simulation/backtest` |
| `backtest.validation.validation_mode` | `boolean` | `false` | `simulation/backtest` |
| `compute.cudnn_benchmark` | `boolean` | `true` | `compute` |
| `constrained_rl.cost_discount_gamma` | `number` | `1.0` | `learning/rl` |
| `constrained_rl.dual_learning_rate` | `number` | `0.1` | `learning/rl` |
| `constrained_rl.enabled` | `boolean` | `false` | `learning/rl` |
| `constrained_rl.episode_cost_budget` | `number` | `1.0` | `learning/rl` |
| `constrained_rl.lambda_initial` | `number` | `0.0` | `learning/rl` |
| `constrained_rl.lambda_max` | `number` | `100.0` | `learning/rl` |
| `costs.commission_per_lot` | `number` | `0.0` | `trading/execution` |
| `costs.point_size` | `number` | `0.01` | `trading/execution` |
| `costs.slippage_points` | `number` | `5.0` | `trading/execution` |
| `costs.spread_us100` | `number` | `0.6` | `trading/execution` |
| `costs.spread_us500` | `number` | `1.53` | `trading/execution` |
| `costs.use_tick_execution` | `boolean` | `true` | `trading/execution` |
| `data.bar_timestamp_convention` | `string` | `"open"` | `market_data/configuration` |
| `data.cache_dir` | `string` | `"cache/train_test_2025_2026"` | `market_data/configuration` |
| `data.datasets.testing.m1_files.US100.cash` | `string` | `"US100.cash_M1_202412300105_202610162349.csv"` | `market_data/configuration` |
| `data.datasets.testing.m1_files.US500.cash` | `string` | `"US500.cash_M1_202412300105_202610162349.csv"` | `market_data/configuration` |
| `data.datasets.testing.raw_dir` | `string` | `"data/testing"` | `market_data/configuration` |
| `data.datasets.testing.tick_files.US100.cash` | `string` | `"US100.cash_202412300105_202610162349.csv"` | `market_data/configuration` |
| `data.datasets.testing.tick_files.US500.cash` | `string` | `"US500.cash_202412300105_202610162349.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.D1.US500.cash` | `string` | `"US500.cash_D1_202412300000_202610160000.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.H1.US100.cash` | `string` | `"US100.cash_H1_202412300100_202610162300.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.H1.US500.cash` | `string` | `"US500.cash_H1_202412300100_202610162300.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.H4.US100.cash` | `string` | `"US100.cash_H4_202412300000_202610162000.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.H4.US500.cash` | `string` | `"US500.cash_H4_202412300000_202610162000.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M10.US100.cash` | `string` | `"US100.cash_M10_202412300100_202610162340.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M10.US500.cash` | `string` | `"US500.cash_M10_202412300100_202610162340.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M15.US100.cash` | `string` | `"US100.cash_M15_202412300100_202610162345.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M15.US500.cash` | `string` | `"US500.cash_M15_202412300100_202610162345.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M3.US100.cash` | `string` | `"US100.cash_M3_202412300103_202610162348.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M3.US500.cash` | `string` | `"US500.cash_M3_202412300103_202610162348.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M30.US100.cash` | `string` | `"US100.cash_M30_202412300100_202610162330.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M30.US500.cash` | `string` | `"US500.cash_M30_202412300100_202610162330.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M5.US100.cash` | `string` | `"US100.cash_M5_202412300105_202610162345.csv"` | `market_data/configuration` |
| `data.datasets.testing.timeframe_files.M5.US500.cash` | `string` | `"US500.cash_M5_202412300105_202610162345.csv"` | `market_data/configuration` |
| `data.datasets.training.m1_files.US100.cash` | `string` | `"US100.cash_M1_202412300105_202610162349.csv"` | `market_data/configuration` |
| `data.datasets.training.m1_files.US500.cash` | `string` | `"US500.cash_M1_202412300105_202610162349.csv"` | `market_data/configuration` |
| `data.datasets.training.raw_dir` | `string` | `"data/training"` | `market_data/configuration` |
| `data.datasets.training.tick_files.US100.cash` | `string` | `"US100.cash_202412300105_202610162349.csv"` | `market_data/configuration` |
| `data.datasets.training.tick_files.US500.cash` | `string` | `"US500.cash_202412300105_202610162349.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.D1.US500.cash` | `string` | `"US500.cash_D1_202412300000_202610160000.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.H1.US100.cash` | `string` | `"US100.cash_H1_202412300100_202610162300.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.H1.US500.cash` | `string` | `"US500.cash_H1_202412300100_202610162300.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.H4.US100.cash` | `string` | `"US100.cash_H4_202412300000_202610162000.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.H4.US500.cash` | `string` | `"US500.cash_H4_202412300000_202610162000.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M10.US100.cash` | `string` | `"US100.cash_M10_202412300100_202610162340.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M10.US500.cash` | `string` | `"US500.cash_M10_202412300100_202610162340.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M15.US100.cash` | `string` | `"US100.cash_M15_202412300100_202610162345.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M15.US500.cash` | `string` | `"US500.cash_M15_202412300100_202610162345.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M3.US100.cash` | `string` | `"US100.cash_M3_202412300103_202610162348.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M3.US500.cash` | `string` | `"US500.cash_M3_202412300103_202610162348.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M30.US100.cash` | `string` | `"US100.cash_M30_202412300100_202610162330.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M30.US500.cash` | `string` | `"US500.cash_M30_202412300100_202610162330.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M5.US100.cash` | `string` | `"US100.cash_M5_202412300105_202610162345.csv"` | `market_data/configuration` |
| `data.datasets.training.timeframe_files.M5.US500.cash` | `string` | `"US500.cash_M5_202412300105_202610162345.csv"` | `market_data/configuration` |
| `data.derived_timeframes.US100.cash` | `array` | `["D1"]` | `market_data/configuration` |
| `data.prebuilt_feature_cache` | `null` | `null` | `market_data/configuration` |
| `data.price_discretization.enabled` | `boolean` | `false` | `market_data/configuration` |
| `data.price_discretization.increment` | `number` | `0.25` | `market_data/configuration` |
| `data.price_discretization.rounding` | `string` | `"nearest_half_away_from_zero"` | `market_data/configuration` |
| `data.primary` | `string` | `"US100.cash"` | `market_data/configuration` |
| `data.raw_dir` | `string` | `"data"` | `market_data/configuration` |
| `data.require_native_timeframes` | `boolean` | `true` | `market_data/configuration` |
| `data.secondary` | `string` | `"US500.cash"` | `market_data/configuration` |
| `data.session_schedule_file` | `string` | `"config/ny_session_schedule.csv"` | `market_data/configuration` |
| `data.split.test_start` | `string` | `"2026-01-01"` | `market_data/configuration` |
| `data.split.train_end` | `string` | `"2025-12-31"` | `market_data/configuration` |
| `data.split.train_start` | `string` | `"2024-12-30"` | `market_data/configuration` |
| `data.symbols` | `array` | `["US100.cash","US500.cash"]` | `market_data/configuration` |
| `data.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `market_data/configuration` |
| `data.timestamp_clock` | `string` | `"ftmo_mt5_us_dst"` | `market_data/configuration` |
| `data.tz` | `string` | `"Etc/GMT-3"` | `market_data/configuration` |
| `device` | `string` | `"auto"` | `compute/environment` |
| `encoder.windows.d1` | `integer` | `5` | `models/encoders` |
| `encoder.windows.h1` | `integer` | `12` | `models/encoders` |
| `encoder.windows.h4` | `integer` | `6` | `models/encoders` |
| `encoder.windows.m10` | `integer` | `12` | `models/encoders` |
| `encoder.windows.m15` | `integer` | `16` | `models/encoders` |
| `encoder.windows.m3` | `integer` | `20` | `models/encoders` |
| `encoder.windows.m30` | `integer` | `8` | `models/encoders` |
| `encoder.windows.m5` | `integer` | `24` | `models/encoders` |
| `env.action_type` | `string` | `"discrete"` | `simulation/environment and decisioning` |
| `env.agent_direction_control` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.agent_entry_execution` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.allow_agent_sl_mode` | `boolean` | `true` | `simulation/environment and decisioning` |
| `env.allow_agent_tp_mode` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.allow_ema_exit` | `boolean` | `true` | `simulation/environment and decisioning` |
| `env.allow_multi_tp` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.allow_simplex` | `boolean` | `true` | `simulation/environment and decisioning` |
| `env.arm_requires_retest` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.block_overnight` | `boolean` | `true` | `simulation/environment and decisioning` |
| `env.candidate_max_age_bars` | `integer` | `5` | `simulation/environment and decisioning` |
| `env.data_source` | `string` | `"frames"` | `simulation/environment and decisioning` |
| `env.direction_override_threshold` | `number` | `0.0` | `simulation/environment and decisioning` |
| `env.ema_runner_fraction` | `number` | `0.25` | `simulation/environment and decisioning` |
| `env.entry_cooldown_bars` | `integer` | `0` | `simulation/environment and decisioning` |
| `env.entry_intensity_threshold` | `number` | `0.0` | `simulation/environment and decisioning` |
| `env.entry_state_machine` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.entry_state_observation` | `boolean` | `true` | `simulation/environment and decisioning` |
| `env.eod_risk.breakeven_buffer_pts` | `number` | `2.0` | `simulation/environment and decisioning` |
| `env.eod_risk.breakeven_trigger_r` | `number` | `1.0` | `simulation/environment and decisioning` |
| `env.eod_risk.max_age_hours` | `integer` | `8` | `simulation/environment and decisioning` |
| `env.eod_risk.max_loss_usd` | `number` | `1100.0` | `simulation/environment and decisioning` |
| `env.eod_risk.peak_trailing_dd_limit_usd` | `number` | `0.0` | `simulation/environment and decisioning` |
| `env.eod_risk.planned_risk_mult` | `number` | `1.1` | `simulation/environment and decisioning` |
| `env.eod_risk.progress_threshold_atr` | `number` | `0.25` | `simulation/environment and decisioning` |
| `env.eod_risk.respect_planned_risk` | `boolean` | `true` | `simulation/environment and decisioning` |
| `env.eod_risk.stale_bars` | `integer` | `60` | `simulation/environment and decisioning` |
| `env.equity_log_growth_scale` | `number` | `100.0` | `simulation/environment and decisioning` |
| `env.feature_validity_channels` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.fixed_risk_usd` | `number` | `0.0` | `simulation/environment and decisioning` |
| `env.max_entries_per_session` | `integer` | `0` | `simulation/environment and decisioning` |
| `env.max_episode_steps` | `null` | `null` | `simulation/environment and decisioning` |
| `env.n_envs` | `integer` | `8` | `simulation/environment and decisioning` |
| `env.obs_window` | `integer` | `60` | `simulation/environment and decisioning` |
| `env.observation_age_scale_bars` | `integer` | `60` | `simulation/environment and decisioning` |
| `env.observation_schema_version` | `string` | `"account-state-v2"` | `simulation/environment and decisioning` |
| `env.open_manipulation_bars` | `integer` | `10` | `simulation/environment and decisioning` |
| `env.peak_trailing_dd_limit` | `number` | `0.0` | `simulation/environment and decisioning` |
| `env.reachable_r_validity_mask` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.regime_observation` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.reward_dsr_eta` | `number` | `0.01` | `simulation/environment and decisioning` |
| `env.reward_mode` | `string` | `"dsr"` | `simulation/environment and decisioning` |
| `env.risk_band_hold_below_usd` | `number` | `0.0` | `simulation/environment and decisioning` |
| `env.risk_band_max_usd` | `number` | `0.0` | `simulation/environment and decisioning` |
| `env.risk_floor` | `number` | `0.0005` | `simulation/environment and decisioning` |
| `env.risk_mode` | `string` | `"dynamic"` | `simulation/environment and decisioning` |
| `env.sl_buffer_pts` | `number` | `0.0` | `simulation/environment and decisioning` |
| `env.sl_mode_defer_threshold` | `number` | `0.1` | `simulation/environment and decisioning` |
| `env.strategy_actions` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.strict_research_eligibility` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.tp_breakeven_alpha` | `number` | `0.5` | `simulation/environment and decisioning` |
| `env.tp_mode_defer_threshold` | `number` | `0.1` | `simulation/environment and decisioning` |
| `env.trade_setup_actions` | `boolean` | `false` | `simulation/environment and decisioning` |
| `env.vector_backend` | `string` | `"subproc"` | `simulation/environment and decisioning` |
| `env.vector_shards` | `integer` | `0` | `simulation/environment and decisioning` |
| `evaluation.annualization_convention` | `string` | `"252 sessions/year x 390 NY-session M1 bars/session"` | `evaluation` |
| `evaluation.deterministic` | `boolean` | `false` | `evaluation` |
| `evaluation.periods_per_year` | `integer` | `98280` | `evaluation` |
| `evaluation.trade_idea_plots.fvg_retest.enabled` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.fvg_retest.show_fvg` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.fvg_retest.show_ifvg` | `boolean` | `false` | `evaluation` |
| `evaluation.trade_idea_plots.fvg_retest.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `evaluation` |
| `evaluation.trade_idea_plots.ifvg_retest.enabled` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.ifvg_retest.show_ifvg` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.ifvg_retest.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `evaluation` |
| `evaluation.trade_idea_plots.ifvg_unretested.enabled` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.ifvg_unretested.show_ifvg` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.ifvg_unretested.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `evaluation` |
| `evaluation.trade_idea_plots.order_block.enabled` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.order_block.show_zone` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.order_block.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `evaluation` |
| `evaluation.trade_idea_plots.po3.enabled` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.po3.show_distribution` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.po3.show_fvg` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.po3.show_ifvg` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.po3.show_manipulation` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.po3.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `evaluation` |
| `evaluation.trade_idea_plots.standard_deviation.enabled` | `boolean` | `true` | `evaluation` |
| `evaluation.trade_idea_plots.standard_deviation.levels` | `string` | `"${features.entry_ideas.levels}"` | `evaluation` |
| `evaluation.trade_idea_plots.standard_deviation.max_chart_range_fraction` | `number` | `0.15` | `evaluation` |
| `evaluation.trade_idea_plots.standard_deviation.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `evaluation` |
| `execution.fill_delay_ms` | `integer` | `0` | `trading/execution and simulation` |
| `execution.fill_latency_bars` | `integer` | `0` | `trading/execution and simulation` |
| `execution.limit_order_max_offset_atr` | `number` | `1.0` | `trading/execution and simulation` |
| `execution.limit_order_max_ttl_bars` | `integer` | `60` | `trading/execution and simulation` |
| `execution.limit_order_require_trade_through` | `boolean` | `false` | `trading/execution and simulation` |
| `execution.max_tick_quote_wait_ms` | `integer` | `60000` | `trading/execution and simulation` |
| `execution.randomized_fill_latency_ms` | `number` | `0.0` | `trading/execution and simulation` |
| `features.adx_period` | `integer` | `14` | `features` |
| `features.atr_period` | `integer` | `14` | `features` |
| `features.bb_period` | `integer` | `20` | `features` |
| `features.bb_std` | `number` | `2.0` | `features` |
| `features.ema_periods` | `array` | `[9,21,50,200]` | `features` |
| `features.entry_ideas.enabled` | `boolean` | `false` | `features` |
| `features.entry_ideas.levels` | `array` | `[1.0,0.786,0.707,0.5,0.0,-0.5,-1.0,-1.5,-2.0,-2.25,-2.5,-3.0,-4.0,-6.0,-8.0]` | `features` |
| `features.entry_ideas.retracement_high` | `number` | `0.786` | `features` |
| `features.entry_ideas.retracement_low` | `number` | `0.5` | `features` |
| `features.entry_ideas.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.gap_reaction_buffer_enabled` | `boolean` | `true` | `features` |
| `features.gap_reaction_buffer_fraction` | `number` | `0.1` | `features` |
| `features.htf_timeframes` | `array` | `["M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.ifvg_mtf.enabled` | `boolean` | `false` | `features` |
| `features.ifvg_mtf.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.include_fvg_ifvg` | `boolean` | `false` | `features` |
| `features.include_pd_context` | `boolean` | `false` | `features` |
| `features.include_po3` | `boolean` | `false` | `features` |
| `features.include_po3_full` | `boolean` | `false` | `features` |
| `features.include_previous_session_pd` | `boolean` | `false` | `features` |
| `features.include_session_ohlc` | `boolean` | `false` | `features` |
| `features.include_strategy_state` | `boolean` | `false` | `features` |
| `features.liquidity.enabled` | `boolean` | `false` | `features` |
| `features.liquidity.timeframes` | `array` | `["M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.macd_fast` | `integer` | `12` | `features` |
| `features.macd_signal` | `integer` | `9` | `features` |
| `features.macd_slow` | `integer` | `26` | `features` |
| `features.normalize_d1_technical_on_source` | `boolean` | `false` | `features` |
| `features.order_blocks.enabled` | `boolean` | `false` | `features` |
| `features.order_blocks.impulse_atr` | `number` | `0.5` | `features` |
| `features.order_blocks.max_age_bars` | `integer` | `240` | `features` |
| `features.order_blocks.search_bars` | `integer` | `10` | `features` |
| `features.order_blocks.swing_period` | `integer` | `5` | `features` |
| `features.order_blocks.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.po3_htf` | `string` | `"M15"` | `features` |
| `features.po3_ltf` | `string` | `"M5"` | `features` |
| `features.po3_phase_mode` | `string` | `"legacy"` | `features` |
| `features.po3_reference_mode` | `string` | `"m1_legacy"` | `features` |
| `features.po3_reference_timeframes` | `array` | `["M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.po3_state_mtf.enabled` | `boolean` | `false` | `features` |
| `features.po3_state_mtf.timeframes` | `array` | `["M1","M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.realized_vol_period` | `integer` | `20` | `features` |
| `features.return_horizons` | `array` | `[1,5,15,30]` | `features` |
| `features.rsi_period` | `integer` | `14` | `features` |
| `features.sessions.asian.end` | `string` | `"23:00"` | `features` |
| `features.sessions.asian.start` | `string` | `"19:00"` | `features` |
| `features.sessions.london.end` | `string` | `"05:00"` | `features` |
| `features.sessions.london.start` | `string` | `"02:00"` | `features` |
| `features.sessions.ny.end` | `string` | `"15:00"` | `features` |
| `features.sessions.ny.start` | `string` | `"08:30"` | `features` |
| `features.sessions.quadrant_ranges` | `array` | `["yesterday","lastweek"]` | `features` |
| `features.sessions.tz` | `string` | `"America/Chicago"` | `features` |
| `features.sessions.week_start` | `string` | `"MON"` | `features` |
| `features.smt.enabled` | `boolean` | `false` | `features` |
| `features.smt.timeframes` | `array` | `["M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.smt_corr_window` | `integer` | `20` | `features` |
| `features.smt_swing_period` | `integer` | `5` | `features` |
| `features.stoch_d` | `integer` | `3` | `features` |
| `features.stoch_k` | `integer` | `14` | `features` |
| `features.structure.candidate_price_increment` | `null` | `null` | `features` |
| `features.structure.enabled` | `boolean` | `true` | `features` |
| `features.structure.swing_candidate_count` | `integer` | `1` | `features` |
| `features.structure.timeframes` | `array` | `["M3","M5","M10","M15","M30","H1","H4","D1"]` | `features` |
| `features.vwap_session` | `boolean` | `true` | `features` |
| `features.window` | `integer` | `60` | `features` |
| `features.zscore_window` | `integer` | `252` | `features` |
| `ftmo.daily_loss_limit_pct` | `number` | `0.05` | `trading/risk` |
| `ftmo.limit_value_mode` | `string` | `"percent_equity"` | `trading/risk` |
| `ftmo.max_drawdown_mode` | `string` | `"static"` | `trading/risk` |
| `ftmo.max_loss_limit_initial_pct` | `number` | `0.1` | `trading/risk` |
| `ftmo.profit_target` | `number` | `10000.0` | `trading/risk` |
| `ftmo.risk_per_trade_limit` | `number` | `1000.0` | `trading/risk` |
| `ftmo.risk_per_trade_limit_pct` | `number` | `0.01` | `trading/risk` |
| `ftmo.risk_sizing_limit_usd` | `number` | `900.0` | `trading/risk` |
| `ftmo.soft_daily_loss_limit_pct` | `number` | `0.05` | `trading/risk` |
| `ftmo.soft_max_loss_limit_initial_pct` | `number` | `0.1` | `trading/risk` |
| `ftmo.soft_trailing_dd_limit` | `number` | `0.0` | `trading/risk` |
| `ftmo.trailing_dd_limit` | `number` | `0.0` | `trading/risk` |
| `live_risk_overrides.interval_minutes` | `integer` | `1` | `live and integrations/mt5` |
| `live_risk_overrides.max_total_risk` | `number` | `0.02` | `live and integrations/mt5` |
| `live_risk_overrides.risk_per_symbol` | `number` | `0.01` | `live and integrations/mt5` |
| `live_risk_overrides.stop_loss_pips` | `number` | `50.0` | `live and integrations/mt5` |
| `output.candle_tf` | `string` | `"15min"` | `artifacts and evaluation/reporting` |
| `output.dir` | `string` | `"outputs"` | `artifacts and evaluation/reporting` |
| `output.dpi` | `integer` | `150` | `artifacts and evaluation/reporting` |
| `output.max_order_charts` | `integer` | `0` | `artifacts and evaluation/reporting` |
| `output.price_plot_max_points` | `integer` | `3000` | `artifacts and evaluation/reporting` |
| `output.report_profile` | `string` | `"full"` | `artifacts and evaluation/reporting` |
| `output.save_csv` | `boolean` | `true` | `artifacts and evaluation/reporting` |
| `output.save_html` | `boolean` | `false` | `artifacts and evaluation/reporting` |
| `output.save_plots` | `boolean` | `true` | `artifacts and evaluation/reporting` |
| `output.trade_chart_show_mae_mfe` | `boolean` | `true` | `artifacts and evaluation/reporting` |
| `output.trade_chart_show_sl_tp` | `boolean` | `true` | `artifacts and evaluation/reporting` |
| `ppo.actor_arch` | `string` | `"shared"` | `learning/rl` |
| `ppo.batch_size` | `integer` | `512` | `learning/rl` |
| `ppo.checkpoint_freq` | `integer` | `1000000` | `learning/rl` |
| `ppo.clip_range` | `number` | `0.2` | `learning/rl` |
| `ppo.ent_coef` | `number` | `0.01` | `learning/rl` |
| `ppo.ent_coef_continuous` | `number` | `0.001` | `learning/rl` |
| `ppo.gae_lambda` | `number` | `0.95` | `learning/rl` |
| `ppo.gamma` | `number` | `0.99` | `learning/rl` |
| `ppo.learning_rate` | `number` | `0.0003` | `learning/rl` |
| `ppo.log_std_init` | `number` | `0.0` | `learning/rl` |
| `ppo.log_std_max` | `number` | `0.0` | `learning/rl` |
| `ppo.log_std_min` | `number` | `-0.7` | `learning/rl` |
| `ppo.mode_prior_coef` | `number` | `0.001` | `learning/rl` |
| `ppo.n_epochs` | `integer` | `15` | `learning/rl` |
| `ppo.n_steps` | `integer` | `2048` | `learning/rl` |
| `ppo.policy_distribution` | `string` | `"clamped_diagonal_gaussian"` | `learning/rl` |
| `ppo.rollout_buffer_on_device` | `boolean` | `true` | `learning/rl` |
| `ppo.semantic_head_width` | `integer` | `64` | `learning/rl` |
| `ppo.total_timesteps` | `integer` | `20000000` | `learning/rl` |
| `ppo.trade_setup_conditioned.embedding_dim` | `integer` | `32` | `learning/rl` |
| `ppo.trade_setup_conditioned.execution_hidden_dim` | `integer` | `128` | `learning/rl` |
| `quality_diagnostics.enabled` | `boolean` | `false` | `training and evaluation` |
| `quality_execution.effective_n_envs` | `null` | `null` | `trading/risk and simulation` |
| `quality_execution.exact_n_envs` | `boolean` | `false` | `trading/risk and simulation` |
| `quality_execution.requested_n_envs` | `null` | `null` | `trading/risk and simulation` |
| `risk.default_risk_frac` | `number` | `0.01` | `trading/risk` |
| `risk.lot_step` | `number` | `0.01` | `trading/risk` |
| `risk.max_lot` | `number` | `100.0` | `trading/risk` |
| `risk.min_lot` | `number` | `0.01` | `trading/risk` |
| `risk.min_sl_atr_mult` | `number` | `0.5` | `trading/risk` |
| `risk.min_sl_points` | `number` | `0.0` | `trading/risk` |
| `risk.rr_ratio_default` | `number` | `2.0` | `trading/risk` |
| `risk.sl_mode` | `string` | `"fixed"` | `trading/risk` |
| `risk.swing_buffer_pts` | `number` | `1.0` | `trading/risk` |
| `risk.target_timeframes` | `array` | `["M3","M5","M10","M15","M30","H1","H4","D1"]` | `trading/risk` |
| `risk.tp_mode` | `string` | `"fixed"` | `trading/risk` |
| `risk.tp_reference` | `string` | `"structural"` | `trading/risk` |
| `sac.batch_size` | `integer` | `512` | `learning/rl` |
| `sac.buffer_size` | `integer` | `100000` | `learning/rl` |
| `sac.ent_coef` | `number` | `0.01` | `learning/rl` |
| `sac.gamma` | `number` | `0.99` | `learning/rl` |
| `sac.gradient_steps` | `integer` | `1` | `learning/rl` |
| `sac.learning_rate` | `number` | `0.0003` | `learning/rl` |
| `sac.learning_starts` | `integer` | `500` | `learning/rl` |
| `sac.tau` | `number` | `0.005` | `learning/rl` |
| `sac.train_freq` | `integer` | `1` | `learning/rl` |
| `session.dst_flag` | `boolean` | `true` | `market_data and features` |
| `session.end` | `string` | `"23:00"` | `market_data and features` |
| `session.start` | `string` | `"16:30"` | `market_data and features` |
| `session.tz` | `string` | `"Etc/GMT-3"` | `market_data and features` |
| `strategy.batch_windows` | `integer` | `256` | `trading/strategies` |
| `strategy.entry.enforce_gate` | `boolean` | `false` | `trading/strategies` |
| `strategy.entry.mode` | `string` | `"legacy"` | `trading/strategies` |
| `strategy.entry.previous_session_pd_gate` | `boolean` | `false` | `trading/strategies` |
| `strategy.ifvg.close_through_threshold` | `number` | `0.1` | `trading/strategies` |
| `strategy.ifvg.enabled` | `boolean` | `true` | `trading/strategies` |
| `strategy.ifvg.max_age_bars` | `integer` | `50` | `trading/strategies` |
| `strategy.ifvg.require_opposing_fvg` | `boolean` | `false` | `trading/strategies` |
| `strategy.ifvg.require_price_retest` | `boolean` | `true` | `trading/strategies` |
| `strategy.liquidity.max_age_bars` | `integer` | `120` | `trading/strategies` |
| `strategy.liquidity.require_reclaim` | `boolean` | `true` | `trading/strategies` |
| `strategy.liquidity.swing_period` | `integer` | `5` | `trading/strategies` |
| `strategy.manipulation_filter` | `string` | `"against"` | `trading/strategies` |
| `strategy.name` | `string` | `"po3_ifvg"` | `trading/strategies` |
| `strategy.po3.require_distribution_confirmation` | `boolean` | `true` | `trading/strategies` |
| `strategy.po3.require_manipulation_sweep` | `boolean` | `true` | `trading/strategies` |
| `strategy.reward.distribution_bonus` | `number` | `0.005` | `trading/strategies` |
| `strategy.reward.entry_bonus` | `number` | `0.01` | `trading/strategies` |
| `strategy.reward.invalid_ifvg_penalty` | `number` | `0.01` | `trading/strategies` |
| `strategy.reward.manipulation_penalty` | `number` | `0.02` | `trading/strategies` |
| `strategy.reward.strategy_weight` | `number` | `0.01` | `trading/strategies` |
| `strategy.reward.sweep_penalty` | `number` | `0.02` | `trading/strategies` |
| `strategy.risk.risk_frac_range` | `array` | `[0.0,0.01]` | `trading/strategies` |
| `strategy.risk.rr_range` | `array` | `[1.5,5.0]` | `trading/strategies` |
| `strategy.risk.sl_buffer_pts` | `number` | `1.0` | `trading/strategies` |
| `strategy.risk.sl_mode` | `string` | `"fixed"` | `trading/strategies` |
| `strategy.risk.tp_mode` | `string` | `"fixed"` | `trading/strategies` |
| `strategy.risk.tp_reference` | `string` | `"structural"` | `trading/strategies` |
| `strategy.session.timezone` | `string` | `"Etc/GMT-3"` | `trading/strategies` |
| `strategy.tp.allowed_targets` | `array` | `["rr","buyside_liquidity","sellside_liquidity","previous_day_high_low"]` | `trading/strategies` |
| `strategy.tp.invalid_target_policy` | `string` | `"rr_fallback"` | `trading/strategies` |
| `strategy.tp.mode` | `string` | `"agent"` | `trading/strategies` |
| `strategy.variant_id` | `null` | `null` | `trading/strategies` |
| `trading_policy.daily_loss_includes_open_pnl` | `boolean` | `true` | `trading/policy` |
| `trading_policy.daily_loss_reset_source` | `string` | `"supplied_session_id_transition"` | `trading/policy` |
| `trading_policy.daily_pnl_basis` | `string` | `"session_net_equity"` | `trading/policy` |
| `trading_policy.mode` | `string` | `"legacy"` | `trading/policy` |
| `trading_policy.repeated_payout.agent_risk_max_frac` | `number` | `0.009` | `trading/policy` |
| `trading_policy.repeated_payout.agent_risk_min_frac` | `number` | `0.0` | `trading/policy` |
| `trading_policy.repeated_payout.continue_after_payout` | `boolean` | `true` | `trading/policy` |
| `trading_policy.repeated_payout.daily_loss_limit_pct` | `number` | `0.05` | `trading/policy` |
| `trading_policy.repeated_payout.enforce_remaining_account_capacity` | `boolean` | `true` | `trading/policy` |
| `trading_policy.repeated_payout.enforce_remaining_daily_capacity` | `boolean` | `true` | `trading/policy` |
| `trading_policy.repeated_payout.execution_reserve_usd` | `null` | `null` | `trading/policy` |
| `trading_policy.repeated_payout.max_agent_risk_frac` | `null` | `null` | `trading/policy` |
| `trading_policy.repeated_payout.max_loss_limit_initial_pct` | `number` | `0.1` | `trading/policy` |
| `trading_policy.repeated_payout.min_agent_risk_frac` | `null` | `null` | `trading/policy` |
| `trading_policy.repeated_payout.operating_balance` | `number` | `100000.0` | `trading/policy` |
| `trading_policy.repeated_payout.payout_target_balance` | `number` | `110000.0` | `trading/policy` |
| `trading_policy.repeated_payout.payout_trigger` | `string` | `"realized_balance_flat"` | `trading/policy` |
| `trading_policy.repeated_payout.repeated_eval` | `boolean` | `true` | `trading/policy` |
| `trading_policy.repeated_payout.reserve_cost_buffer_usd` | `number` | `0.0` | `trading/policy` |
| `trading_policy.repeated_payout.risk_floor` | `number` | `0.0` | `trading/policy` |
| `trading_policy.repeated_payout.trailing_dd_limit` | `number` | `0.0` | `trading/policy` |
| `training.dashboard.diversity.action_std` | `number` | `0.05` | `training` |
| `training.dashboard.diversity.direction_min_share` | `number` | `0.9` | `training` |
| `training.dashboard.diversity.ema_hi` | `number` | `0.98` | `training` |
| `training.dashboard.diversity.ema_lo` | `number` | `0.02` | `training` |
| `training.dashboard.diversity.min_prior_direction_choices` | `integer` | `30` | `training` |
| `training.dashboard.diversity.min_prior_risk_steps` | `integer` | `1000` | `training` |
| `training.dashboard.diversity.min_prior_sl_choices` | `integer` | `30` | `training` |
| `training.dashboard.diversity.min_prior_tp_choices` | `integer` | `30` | `training` |
| `training.dashboard.diversity.min_prior_trades` | `integer` | `50` | `training` |
| `training.dashboard.diversity.rank_edge` | `number` | `0.05` | `training` |
| `training.dashboard.diversity.risk_u_max` | `number` | `0.05` | `training` |
| `training.dashboard.diversity.rr_p75` | `number` | `1.25` | `training` |
| `training.dashboard.diversity.sl_top_share` | `number` | `0.8` | `training` |
| `training.dashboard.diversity.tp_top_share` | `number` | `0.8` | `training` |
| `training.dashboard.enabled` | `boolean` | `true` | `training` |
| `training.dashboard.eval_bars` | `integer` | `20000` | `training` |
| `training.dashboard.eval_every` | `integer` | `100000` | `training` |
| `training.dashboard.isolate_eval_rng` | `boolean` | `false` | `training` |
| `training.dashboard.log_every` | `integer` | `100000` | `training` |
| `training.dashboard.prior_every` | `integer` | `100000` | `training` |
| `training.debug.corr_floor` | `number` | `0.3` | `training` |
| `training.debug.corr_windows` | `integer` | `3` | `training` |
| `training.debug.enabled` | `boolean` | `true` | `training` |
| `training.debug.ev_floor` | `number` | `0.2` | `training` |
| `training.debug.ev_windows` | `integer` | `5` | `training` |
| `training.debug.part_vs_pnl` | `number` | `10.0` | `training` |
| `training.debug.ring_size` | `integer` | `5` | `training` |
| `training.debug.std_max` | `number` | `1.0` | `training` |
| `training.debug.std_min` | `number` | `0.497` | `training` |
| `training.early_abort.enabled` | `boolean` | `true` | `training` |
| `training.early_abort.min_timesteps` | `integer` | `5000000` | `training` |
| `training.early_abort.stop_on_equity_gate` | `boolean` | `false` | `training` |
| `training.early_abort.stop_on_no_trades` | `boolean` | `false` | `training` |
| `training.early_abort.stop_on_nonfinite` | `boolean` | `true` | `training` |
| `training.early_abort.window` | `integer` | `4` | `training` |
| `training.episode_mode` | `string` | `"full_split"` | `training` |
| `training.max_days` | `null` | `null` | `training` |
| `training.mode` | `string` | `"full"` | `training` |
| `training.primary_only` | `boolean` | `false` | `training` |
| `training.progress_log_every` | `integer` | `0` | `training` |
| `training.survival_gate_manifest` | `null` | `null` | `training` |
| `training.total_timesteps_mvp` | `integer` | `8192` | `training` |
| `training.use_m1_only` | `boolean` | `false` | `training` |
