# Model and Experiment Variant Catalog

Generated from `config/variant_catalog.yaml` and resolved experiment settings.
Regenerate with `qrl-experiment catalog --write`; validate with `--check`.
Settings stay in their source YAML files; A/B labels are local to each family.

## Policy algorithms

| ID | Algorithm | Description |
|---|---|---|
| `ppo` | Proximal Policy Optimization | On-policy policy-gradient algorithm. |
| `sac` | Soft Actor-Critic | Off-policy maximum-entropy actor-critic algorithm. |

## Encoder architectures

Algorithm/encoder pairs below are shown only when a selectable variant uses them.
A registered encoder with no listed pair currently has no matrix variant.

| Encoder ID | Architecture | Description | Configured algorithms | Selectable variant count |
|---|---|---|---|---|
| `tcn` | Temporal Convolutional Network | Convolutional encoder for a single ordered market sequence. | ppo, sac | 36 |
| `tcn_regime` | Regime-conditioned TCN | TCN encoder with explicit market-regime context. | ppo | 1 |
| `lite_tcn` | Lightweight TCN | Compact temporal convolutional encoder. | — | 0 |
| `gru` | Gated Recurrent Unit | Recurrent encoder for ordered market observations. | ppo, sac | 3 |
| `transformer` | Transformer encoder | Attention-based encoder for ordered market observations. | ppo | 1 |
| `mtf` | Multi-timeframe encoder | Encodes correlated observations from multiple timeframes. | ppo | 1 |
| `mtf_reasoning` | Multi-timeframe reasoning encoder | Multi-timeframe encoder with cross-timeframe reasoning. | ppo | 1 |
| `mtf_shared_tcn_reasoning` | Shared-TCN multi-timeframe reasoning | Shares temporal convolutional processing across timeframes. | — | 0 |
| `mtf_m1_tcn_htf_lite_reasoning` | M1 TCN with lightweight higher-timeframe reasoning | Uses a dedicated M1 TCN and a compact higher-timeframe path. | — | 0 |
| `mtf_m1_tcn_htf_snapshot_reasoning` | M1 TCN with higher-timeframe snapshots | Combines M1 temporal features with higher-timeframe snapshots. | — | 0 |

## Core policy capability ladder

**Family:** `policy_ladder`

**Research question:** What does each added trading-control capability change from the baseline?

**Comparison type:** `ladder`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | `ladder_a0_flat` | Selectable | reference | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Baseline action behavior without learned stop selection. Changes: None declared. | — |
| A1 | `ladder_a1_sl` | Selectable | rung | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Adds agent-selected stop-loss behavior. Changes: agent stop selection. | — |
| A2 | `ladder_a2_tp` | Selectable | rung | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Adds agent-selected take-profit behavior. Changes: agent take-profit selection. | — |
| A3 | `ladder_a3_multi_tp` | Selectable | rung | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Adds multiple partial take-profit levels. Changes: multiple take-profit levels. | — |
| A4b | `ladder_a4b_entry_fsm` | Selectable | rung | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Adds an observed entry-state machine. Changes: entry-state machine, observed entry state. | — |
| A4a | `ladder_a4a_entry_fsm_hidden` | Selectable | rung | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Adds an entry-state machine with latent state. Changes: entry-state machine, hidden entry state. | — |

## Quarter-point price grid with observed entry state

**Family:** `price_grid_a4b`

**Research question:** Does quarter-point price discretization change the A4b policy result?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `ladder_a4b_entry_fsm` | Selectable | control | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Continuous-price A4b reference. Changes: None declared. | — |
| B | `ladder_a4b_entry_fsm_qgrid025` | Selectable | treatment | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | A4b with quarter-point price discretization. Changes: quarter-point price grid. | — |

## Quarter-point price grid with hidden entry state

**Family:** `price_grid_a4a`

**Research question:** Does quarter-point price discretization change the A4a policy result?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `ladder_a4a_entry_fsm_hidden` | Selectable | control | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Continuous-price A4a reference. Changes: None declared. | — |
| B | `ladder_a4a_entry_fsm_hidden_qgrid025` | Selectable | treatment | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | A4a with quarter-point price discretization. Changes: quarter-point price grid. | — |

## Dollar-band risk constraint

**Family:** `dollar_band_q5`

**Research question:** Does the learned Q5 constraint help with dollar-band risk sizing?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `ladder_a4a_dollar_band_q5_off` | Selectable | control | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Dollar-band sizing with Q5 disabled. Changes: None declared. | — |
| B | `ladder_a4a_dollar_band_q5_on` | Selectable | treatment | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Same dollar-band sizing with Q5 enabled. Changes: Q5 constrained learning. | — |

## Single-timeframe versus multi-timeframe encoder

**Family:** `mtf_encoder`

**Research question:** Does the multi-timeframe encoder improve on the matched TCN control?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `rq_mtf_control_tcn` | Selectable | control | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Single-window TCN control. Changes: None declared. | — |
| B | `rq_mtf_treatment_mtf` | Selectable | treatment | `ppo` | `mtf` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Correlated multi-timeframe encoder treatment. Changes: encoder architecture. | — |

## Core, multi-timeframe, and thesis-reasoning PPO models

**Family:** `mtf_reasoning_models`

**Research question:** How do the matched core TCN, multi-timeframe encoder, and thesis-conditioned reasoning policies compare?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `rq_mtf_control_tcn` | Selectable | control | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Core PPO with the single-window TCN and shared dollar-band controls. Changes: None declared. | — |
| B | `rq_mtf_treatment_mtf` | Selectable | treatment | `ppo` | `mtf` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PPO with correlated multi-timeframe encoding. Changes: multi-timeframe encoder. | — |
| C | `rq_mtf_treatment_reasoning` | Selectable | treatment | `ppo` | `mtf_reasoning` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PPO with multi-timeframe thesis reasoning and a thesis-aware action distribution. Changes: multi-timeframe reasoning encoder, thesis selection, thesis-aware action distribution. | — |

## A4b strategy overlays

**Family:** `a4b_strategy_overlay`

**Research question:** How do the configured strategy overlays behave under the A4b policy?

**Comparison type:** `descriptive`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `ladder_a4b_po3_ifvg` | Selectable | candidate | `ppo` | `tcn` | `pnl` | `po3_ifvg` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | A4b with the PO3 and IFVG strategy overlay. Changes: PO3 and IFVG strategy. | — |
| B | `ladder_a4b_distribution` | Selectable | candidate | `ppo` | `tcn` | `pnl` | `distribution` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | A4b with the distribution strategy overlay. Changes: distribution strategy. | — |

## PO3 strategy capability ladder

**Family:** `po3_policy_ladder`

**Research question:** What does each added action capability change with the PO3 strategy?

**Comparison type:** `ladder`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | `ladder_a0_flat_po3` | Selectable | reference | `ppo` | `tcn` | `pnl` | `po3_ifvg` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PO3 strategy with the baseline action capability. Changes: PO3 strategy. | — |
| A1 | `ladder_a1_sl_po3` | Selectable | rung | `ppo` | `tcn` | `pnl` | `po3_ifvg` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PO3 strategy with agent-selected stops. Changes: agent stop selection. | — |
| A2 | `ladder_a2_tp_po3` | Selectable | rung | `ppo` | `tcn` | `pnl` | `po3_ifvg` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PO3 strategy with agent-selected stops and targets. Changes: agent take-profit selection. | — |
| A3 | `ladder_a3_multi_tp_po3` | Selectable | rung | `ppo` | `tcn` | `pnl` | `po3_ifvg` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PO3 strategy with multiple take-profit levels. Changes: multiple take-profit levels. | — |
| A4a | `ladder_a4a_entry_fsm_hidden_po3` | Selectable | rung | `ppo` | `tcn` | `pnl` | `po3_ifvg` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PO3 strategy with hidden entry-state-machine state. Changes: entry-state machine. | — |

## Distribution strategy capability ladder

**Family:** `distribution_policy_ladder`

**Research question:** What does each added action capability change with the distribution strategy?

**Comparison type:** `ladder`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A0 | `ladder_a0_flat_dist` | Selectable | reference | `ppo` | `tcn` | `pnl` | `distribution` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Distribution strategy with the baseline action capability. Changes: distribution strategy. | — |
| A1 | `ladder_a1_sl_dist` | Selectable | rung | `ppo` | `tcn` | `pnl` | `distribution` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Distribution strategy with agent-selected stops. Changes: agent stop selection. | — |
| A2 | `ladder_a2_tp_dist` | Selectable | rung | `ppo` | `tcn` | `pnl` | `distribution` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Distribution strategy with agent-selected stops and targets. Changes: agent take-profit selection. | — |
| A3 | `ladder_a3_multi_tp_dist` | Selectable | rung | `ppo` | `tcn` | `pnl` | `distribution` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Distribution strategy with multiple take-profit levels. Changes: multiple take-profit levels. | — |
| A4a | `ladder_a4a_entry_fsm_hidden_dist` | Selectable | rung | `ppo` | `tcn` | `pnl` | `distribution` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Distribution strategy with hidden entry-state-machine state. Changes: entry-state machine. | — |

## Entry retest setting

**Family:** `entry_retest_control`

**Research question:** What changes when the entry retest requirement is enabled?

**Comparison type:** `descriptive`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| B | `knob_retest_true` | Selectable | candidate | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Enables the entry retest requirement. Changes: entry retest. | — |

## Entry candidate lifetime

**Family:** `entry_candidate_age`

**Research question:** How does the configured candidate age affect entry behavior?

**Comparison type:** `descriptive`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `knob_age_20` | Selectable | candidate | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Uses a 20-bar candidate lifetime. Changes: candidate maximum age. | — |
| B | `knob_age_60` | Selectable | candidate | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Uses a 60-bar candidate lifetime. Changes: candidate maximum age. | — |

## Existing model and policy ablations

**Family:** `model_and_policy_ablations`

**Research question:** How do the recorded architecture and policy ablations differ from the reference?

**Comparison type:** `screening`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `ablation_baseline_unconditional` | Selectable | reference | `ppo` | `gru` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Unconditional baseline reference. Changes: None declared. | — |
| B | `ablation_conditional_narrative` | Selectable | candidate | `ppo` | `gru` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Conditional narrative input variant. Changes: conditional narrative input. | — |
| C | `ablation_transformer_encoder` | Selectable | candidate | `ppo` | `transformer` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Transformer encoder variant. Changes: encoder architecture. | — |
| D | `ablation_sac_agent` | Selectable | candidate | `sac` | `gru` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | SAC algorithm variant. Changes: policy algorithm. | — |
| E | `ablation_discrete_actions` | Selectable | candidate | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Discrete action representation variant. Changes: action representation. | — |
| F | `ablation_pd_context` | Selectable | candidate | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Premium/discount context variant. Changes: premium/discount context. | — |
| G | `ablation_po3_ifvg` | Selectable | candidate | `ppo` | `tcn` | `pnl` | `po3_ifvg` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PO3 and IFVG strategy variant. Changes: PO3 and IFVG strategy. | — |
| H | `ablation_distribution` | Selectable | candidate | `ppo` | `tcn` | `pnl` | `distribution` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Distribution strategy variant. Changes: distribution strategy. | — |

## Sustainable growth reward objective

**Family:** `sustainable_growth_reward`

**Research question:** Does log-equity growth reward improve on the DSR objective?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `sustainable_growth_ppo_dsr` | Selectable | control | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PPO with the DSR objective. Changes: None declared. | — |
| B | `sustainable_growth_ppo_log` | Selectable | treatment | `ppo` | `tcn` | `equity_log_growth` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PPO with the log-equity-growth objective. Changes: reward objective. | — |

## Regime context

**Family:** `regime_context`

**Research question:** Does the regime-conditioned TCN change results versus the TCN control?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `regime_d1_norm_tcn_control` | Selectable | control | `ppo` | `tcn` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | TCN control without the regime treatment. Changes: None declared. | — |
| B | `regime_d1_norm_tcn_regime` | Selectable | treatment | `ppo` | `tcn_regime` | `dsr` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | TCN with daily-normalized regime context. Changes: regime context. | — |

## EOD drawdown policy

**Family:** `log_growth_eod_drawdown`

**Research question:** What changes when a 10,000 EOD trailing drawdown policy is enabled?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `sustainable_growth_ppo_log` | Selectable | control | `ppo` | `tcn` | `equity_log_growth` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Log-growth PPO with peak trailing drawdown disabled. Changes: None declared. | — |
| B | `sustainable_growth_ppo_log_eod_dd10k` | Selectable | treatment | `ppo` | `tcn` | `equity_log_growth` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Log-growth PPO with the 10,000 EOD drawdown policy. Changes: EOD trailing drawdown policy. | — |

## Log-growth Q5 constraint

**Family:** `log_growth_q5_constraint`

**Research question:** Does Q5 constrained learning change the log-growth PPO result?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `sustainable_growth_ppo_log` | Selectable | control | `ppo` | `tcn` | `equity_log_growth` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Log-growth PPO with Q5 disabled. Changes: None declared. | — |
| B | `sustainable_growth_ppo_log_q5` | Selectable | treatment | `ppo` | `tcn` | `equity_log_growth` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | Log-growth PPO with Q5 enabled. Changes: Q5 constrained learning. | — |

## Log-growth policy algorithm

**Family:** `log_growth_algorithm`

**Research question:** Does SAC change the result relative to PPO under log-growth reward?

**Comparison type:** `matched`

| Arm | Variant | Status | Role | Algorithm | Encoder | Reward | Strategy | Risk policy | Description / changed factors | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| A | `sustainable_growth_ppo_log` | Selectable | control | `ppo` | `tcn` | `equity_log_growth` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | PPO with log-equity-growth reward. Changes: None declared. | — |
| B | `sustainable_growth_sac_log` | Selectable | treatment | `sac` | `tcn` | `equity_log_growth` | `baseline` | fixed_usd; trade $1,000; daily $5,000; max $10,000; size cap $900 | SAC with log-equity-growth reward. Changes: policy algorithm. | — |

No retired variant IDs were found in the preserved frozen run configurations.
Retired rows require a non-selectable variant and a verifiable source record.
