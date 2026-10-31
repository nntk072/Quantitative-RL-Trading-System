# Observation schemas

An observation is the complete input supplied to a policy at one decision
point. The environment returns a mapping of named arrays; a checkpoint is
compatible only when both coordinate values and their meanings match. Equal
array widths do not establish compatibility.

## Observation branches

The common observation contains:

| Key | Shape | Meaning |
|---|---|---|
| `seq` | `(obs_window, feature_count)` | M1 feature history visible to the policy. Rows are left-padded when the session has fewer than `obs_window` observations. |
| `seq_mask` | `(obs_window,)` | `1` marks a real row; `0` marks left padding. |
| `account` | `(account_width,)` | Versioned account and position state described below. |

Options add branches only when enabled by configuration:

| Key(s) | Meaning |
|---|---|
| `seq_m3`, `seq_m5`, `seq_m10`, `seq_m15`, `seq_m30`, `seq_h1`, `seq_h4`, `seq_d1` | Per-timeframe windows of completed, causally visible feature rows when MTF observation is enabled. Their lengths are configured independently. |
| `mask_m3` … `mask_d1` | Real-row masks for each enabled MTF sequence window. |
| `regime` | Compact completed-D1 regime feature vector when regime observation is enabled. |
| `regime_mask` | Per-coordinate validity mask for `regime`; missing values are zero-filled and marked invalid. |
| `thesis_mask` | Legacy serialized name for the optional setup-candidate eligibility mask. `1` means eligible; the no-trade category remains eligible. |
| `vae_z` | Optional latent branch when VAE context is enabled. |

The exact available MTF branches are defined by the environment schema and
configuration. The table lists the current supported timeframe set; a model
may use only a subset.

## Account-state versions

The account branch is described by `env.observation_schema_version`. The
schema version must be stored with a checkpoint and compared during evaluation
or resume.

### `account-state-v1`

The legacy six-coordinate vector is ordered as follows:

| Index | Coordinate | Meaning |
|---:|---|---|
| 0 | `log_equity_over_initial` | Natural logarithm of equity divided by initial balance, or zero if the initial balance is invalid. |
| 1 | `position_direction` | `-1`, `0`, or `1` for short, flat, or long. |
| 2 | `open_pnl_over_initial` | Unrealized PnL divided by initial balance. |
| 3 | `unrealized_r_legacy` | `open_pnl / equity * 100` when equity is positive. This differs from v2 planned-risk normalization. |
| 4 | `initial_stop_width_over_price` | Entry-to-stop distance divided by current price. |
| 5 | `trailing_drawdown_pct` | Drawdown from the account high-water mark as a fraction. |

When `entry_state_visibility` is enabled, the configured entry-state one-hot
coordinates are appended. This changes the width and is therefore part of the
checkpoint schema.

### `account-state-v2` and `account-state-v3-repeated-payout`

These versions use the ordered 28-coordinate base vector below. Entry-state
one-hot coordinates may be appended. V3 retains the coordinate layout but uses
the repeated-payout account policy when calculating canonical daily loss; it is
not interchangeable with v2 merely because the coordinate names and widths
match.

| Index | Coordinate | Meaning |
|---:|---|---|
| 0 | `log_equity_over_initial` | `log(equity / initial_balance)` when both are positive; otherwise zero. |
| 1 | `position_direction` | Short `-1`, flat `0`, long `1`. |
| 2 | `open_pnl_over_initial` | Unrealized PnL divided by initial balance. |
| 3 | `unrealized_r` | Open PnL divided by planned dollar risk while a position is open. |
| 4 | `trailing_drawdown_over_limit` | Current peak-equity drawdown fraction divided by configured trailing limit. |
| 5 | `daily_loss_over_limit` | Policy-canonical daily loss divided by daily limit. Daily-loss meaning follows the selected account policy. |
| 6 | `remaining_daily_loss_budget_over_limit` | One minus coordinate 5 when a positive daily limit is configured; otherwise zero. |
| 7 | `loss_from_initial_over_limit` | Current absolute loss from initial balance divided by the maximum-loss limit. |
| 8 | `remaining_max_loss_budget_over_limit` | One minus coordinate 7 when a positive maximum-loss limit is configured; otherwise zero. |
| 9 | `planned_risk_over_limit` | Planned position risk divided by the per-trade risk limit while a position is open. |
| 10 | `initial_stop_distance_over_price` | Initial entry-to-stop distance divided by current price. |
| 11 | `active_sl_headroom_over_initial_risk` | Signed distance from current price to active stop, in initial-risk units; positive means the price is on the safe side. |
| 12 | `remaining_size_fraction` | Remaining position size divided by initial size. |
| 13 | `position_age_over_scale` | Position age in bars divided by the configured age scale. |
| 14–16 | `tp1_hit`, `tp2_hit`, `tp3_hit` | Binary flags indicating which configured partial targets have filled. |
| 17–19 | `distance_to_tp1_over_initial_risk`, `distance_to_tp2_over_initial_risk`, `distance_to_tp3_over_initial_risk` | Signed target distance from current price in initial-risk units; zero when not applicable. |
| 20–22 | `sl_mode_fixed`, `sl_mode_breakeven`, `sl_mode_trailing` | One-hot stop-management mode while a position is open; all zero while flat. |
| 23–25 | `tp_mode_fixed`, `tp_mode_breakeven`, `tp_mode_trailing` | One-hot target-management mode while a position is open; all zero while flat. |
| 26–27 | `exit_mode_structural`, `exit_mode_ema` | One-hot exit mode while a position is open; all zero while flat. |

## Causal visibility

The primary sequence is clipped to the current session and contains rows up to
the current decision index, then is left-padded. In MTF mode, each higher
timeframe branch is built from completed timeframe rows visible at that
decision index. Its mask distinguishes valid rows from padding. Regime context
uses the last completed D1 value aligned to the decision row. These rules are
part of the observation semantics and are protected by causal-feature tests.

## Eligibility mask compatibility name

The current setup-conditioned policy schema was serialized with names such as
`thesis_mask` and `thesis-observation-v1`. These are historical wire
identifiers for a categorical setup candidate, not academic claims. Do not
rename them in an artifact or silently change mask ordering. A future
canonical rename must translate old checkpoint metadata explicitly and
preserve category meanings.

## Checkpoint validation

Evaluation and resume should compare version, width, coordinate order, and
optional-branch configuration. Do not infer semantics from a tensor shape.
See [action schemas](action_schemas.md) and the
[checkpoint compatibility reference](checkpoint_compatibility.md).

## Code navigation

The implementation contract is owned by `decisioning/observations.py`,
`decisioning/regime_observations.py`, and the environment observation
composition in `simulation/environment/`. These paths help locate details;
the behavior described above is the public meaning.
