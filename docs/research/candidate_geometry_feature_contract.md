# Candidate geometry feature contract

Schema `candidate-geometry-observation-v3` uses 217 stable slots: slot 0 is
no-trade, and each executable setup has one market and one limit hypothesis.
Feature values are computed at the completed-bar decision boundary. Price
distances use the current ATR; the mask is boolean, and a proposal with missing
or invalid required geometry is ineligible. No feature uses future fills,
protective triggers, candidate outcomes, or realized returns.

| Feature | Formula and unit | Causal source | Missingness and eligibility |
| --- | --- | --- | --- |
| `direction` | Setup direction, `+1` long or `-1` short | Frozen setup catalog | Required; unsupported setup is masked |
| `entry_type_limit` | `1` for limit, `0` for market | Fixed slot semantics | Always defined for executable slots |
| `entry_price_offset_atr` | `(proposed entry - bar close) / ATR`, ATR units | Current bid/ask for market; current zone midpoint rounded to tick for limit | Required; invalid quote, ATR, or limit placement masks the slot |
| `source_zone_low_offset_atr` | `(zone low - bar close) / ATR`, ATR units | Current feature row and causal entry-idea zone builder | Required; missing or inverted zone masks both slots |
| `source_zone_high_offset_atr` | `(zone high - bar close) / ATR`, ATR units | Current feature row and causal entry-idea zone builder | Required; missing or inverted zone masks both slots |
| `atr_over_reference_price` | `ATR / bar close`, dimensionless | Current feature row and current completed bar | Required; nonpositive ATR or close masks all executable slots |
| `spread_atr` | `(ask - bid) / ATR`, ATR units | Last quote in the completed bar, with the configured bar quote fallback | Required; invalid quote masks all executable slots |
| `round_trip_cost_atr` | `(spread + 2 × slippage + 2 × commission / (contract size × point value)) / ATR`, ATR units | Current spread, configured adverse slippage, commission, account contract size, and cost-model point value | Required; invalid or negative cost inputs mask all executable slots |
| `minimum_stop_distance_atr` | Minimum absolute entry-to-stop distance divided by ATR | Existing structural stop menu for this setup and proposed entry | Required; empty or nonpositive menu masks the slot |
| `maximum_stop_distance_atr` | Maximum absolute entry-to-stop distance divided by ATR | Existing structural stop menu for this setup and proposed entry | Required; empty or nonpositive menu masks the slot |
| `minimum_target_distance_atr` | Minimum absolute entry-to-target distance divided by ATR | Existing structural target menu for this setup and proposed entry | Required; empty or nonpositive menu masks the slot |
| `maximum_target_distance_atr` | Maximum absolute entry-to-target distance divided by ATR | Existing structural target menu for this setup and proposed entry | Required; empty or nonpositive menu masks the slot |
| `limit_ttl_fraction` | `min(configured maximum TTL, bars from the decision timestamp to scheduled session close) / maximum TTL`, dimensionless; market slots use zero | Completed-bar decision timestamp, configured local session open/close, configured M1 TTL | Missing/elapsed session schedule masks executable slots; limit TTL is at least one bar |
| `candidate_age_fraction` | Bars since the newest identified source event divided by configured maximum candidate age, clipped to `[0, 1]` | Current decision time, source-event timestamps, and configured age limit | Missing identity, future source timestamp, or expired age masks both slots |
| `session_close_time_fraction` | Seconds from the completed-bar decision timestamp to configured local session close divided by configured session duration, clipped to `[0, 1]` | Completed-bar decision timestamp and configured local session open/close | Missing/elapsed schedule masks executable slots |
| `source_zone_width_atr` | `(zone high - zone low) / ATR`, ATR units | Same causal source zone used by the proposal | Required; missing, inverted, or nonfinite zone masks both slots |

Slot 0 remains eligible even when every executable proposal is invalid. The
217-way eligibility mask is the authority for policy sampling; each executable
slot is considered only when its corresponding setup is eligible under the
existing 109-way setup mask and the proposal geometry passes these checks.
The checkpoint schema records the allowed setup timeframes and eligible
candidate IDs. Ineligible timeframe IDs are zeroed in the fixed-width ID array.
