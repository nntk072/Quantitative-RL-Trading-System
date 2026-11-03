# Meaning of representative missing observation values

This source review classifies representative high-frequency nonfinite values
from `column_warmup.csv`. It supplements the measured counts; it does not claim
that every feature or stream has been semantically reconciled.

## Findings

| Feature group | Measured example | Producer behavior and available signal | Disposition |
|---|---|---|---|
| Day-of-week sine/cosine | Before the normalization correction, M1 `dow_sin` and `dow_cos` were nonfinite on 286,423 and 298,973 of 351,432 rows. Their source function returns finite values for every timestamp. | `time_features()` emits finite cyclical coordinates. Rolling z-score used a 252-row window and turned finite inputs into NaN whenever fitted variance was zero. | Corrected: zero-variance windows now map finite inputs to zero; unavailable fit statistics and missing source values remain nonfinite. The packet was regenerated. |
| Sweep ages | M1 `sweep_high_age` and `sweep_low_age` are nonfinite on 76.8% and 79.4% of rows; both collide with genuine finite zero ages. | `detect_liquidity_sweeps()` documents NaN when no sweep is active. Finite `sweep_high`/`sweep_low` flags mark the event bar, while `*_reclaimed` flags mark reclamation. | These NaNs encode conditional event state, not just startup warmup. The event flags provide context, but the value-to-mask contract across all nine streams still needs explicit acceptance. |
| Standard-deviation level distances | Each M1 level distance is nonfinite on 59.6% of rows; the 0.5-level distance has 528 genuine finite zeros. | `build_swing_retracement_features()` emits distances only while `standard_deviation_leg_valid` is true. That validity feature is present and finite in the observation packet. | Source has an explicit validity feature; verify that downstream model input and every timeframe preserve the intended interpretation. |
| BOS/MSS distance | M1 `bos_up_dist_atr` and `bos_down_dist_atr` are nonfinite on 77.1% and 80.8% of rows; MSS distances are nonfinite on 98.5%. | Distances are calculated from nullable structure levels. The corresponding BOS/MSS event flags are finite for every row. | Conditional event values have companion flags; their observation-level contract still needs to be included in the complete feature-family review. |
| Initial London context | London distance and sweep-velocity examples have 475 leading missing rows and no interior missing rows. | Values become available after the first required session context is formed. | Leading context warmup; distinguish from recurrent event-inactive missingness. |
| Tick quote context | 23 M1 rows lack bid/ask offsets, quote age, and spread; `tick_quote_available` remains finite and identifies those rows. | Policy market context explicitly masks absent quotes with `tick_quote_available`. | Missing quote values have an explicit validity signal in this stream. |

## Remaining validity gate

The corrected audit still measures 4.99% nonfinite M1 feature cells and
14.19%–21.22% in the sampled higher-timeframe streams. It finds nonfinite
values in 85 M1 features and 54 features in each HTF stream. The review above
classifies representative causes, but does not reconcile every missing cell to
a feature-specific validity signal. The sequence timestep mask still indicates
bar availability rather than per-feature availability. Do not treat this
packet as acceptance of the full observation-validity contract or as evidence
of learned-policy/economic behavior.

## Source references

- `features/technical/indicators.py::time_features`
- `features/pipeline/normalization.py::rolling_zscore`
- `features/context/liquidity.py::detect_liquidity_sweeps`
- `features/context/swing_retracement.py::build_swing_retracement_features`
- `features/pipeline/feature_matrix_builder.py` (BOS/MSS distances)
- `features/context/policy_market.py::attach_policy_market_context`
- `simulation/environment/observations.py` and
  `simulation/environment/observation_runtime.py` (nonfinite values are
  converted to zero during observation construction)
