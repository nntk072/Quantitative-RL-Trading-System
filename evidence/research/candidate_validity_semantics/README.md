# Candidate signal validity semantics

This source review covers the 24 candidate tuples enabled by the registered
local profile: PO3 M1 long/short, IFVG retest M1 long/short, IFVG unretested M1
long/short, and standard-deviation retracement long/short on the nine configured
timeframes. It distinguishes producer signal lifetime from the hypothetical
proposal TTL used by the conditional outcome packet.

## Producer contracts

| Family | Active signal meaning and end condition | Identity and proposal implication |
|---|---|---|
| PO3 | A new accepted directional sweep replaces the prior setup. The candidate entry flag requires post-IFVG distribution and a currently active same-side IFVG zone. The IFVG source origin must be no more than `max_ifvg_age_bars` from the sweep; the active zone ends on an invalidating body close or its configured 50-bar lifetime. | The source-time key tracks the sweep/reclaim/IFVG origin. The flag cannot remain eligible after the zone disappears or a newer setup replaces it. |
| IFVG unretested | A confirmed inverse-gap close-through is an event row. Its source FVG must be no older than 50 bars and confirmation must follow the zone pass. The resulting zone remains active at most 50 bars after confirmation and ends on the configured directional body-close invalidation. | Confirmation time and FVG origin identify the event. The event flag is distinct from the later active-zone lifetime. |
| IFVG retest | The zone must first leave price, then be retested, and a later candle must close beyond the retest extreme with the configured reaction buffer. This is a confirmation event, distinct from the zone's active lifetime. | Confirmation time, FVG origin, and retest confirmation time are separate source fields. Repeated active-zone rows are not separate events. |
| Standard-deviation retracement | The latest confirmed pivot pair defines the leg. Its validity is latched off when the close leaves the 0-to-0.786 retracement envelope, until a different confirmed pivot pair appears. The entry signal is active only inside the 0.5-to-0.786 band. | Re-entry into the band can create a new contiguous signal episode with the same source-leg identity. The current proposal ledger emits at most one proposal per candidate/source-leg identity, so repeated episodes on one leg are intentionally collapsed for this conditional incidence analysis. |

## Proposal horizon and scope

The proposal ledger currently assigns a common 60-minute TTL after a valid
decision row. That is an analysis horizon, not a producer-derived event
lifetime. The replay models a fixed hypothetical market or zone-midpoint limit
order through that TTL and the observed quote/session cutoffs; it does not
recheck a producer signal to cancel a resting order after a PO3 replacement,
IFVG invalidation/expiry, or standard-deviation leg invalidation. Therefore its
fills and outcomes are conditional proposal outcomes, not evidence that a
closed-loop policy could still have submitted or kept that order live.

This closes the source-semantic classification for the enabled profile only.
It does not establish a universal executable validity rule, validate other
configurations, resolve tied-tick chronology, or close historical PPO action
linkage. The common TTL and lack of signal-driven order cancellation remain an
explicit no-go for interpreting this packet as policy execution evidence.

## Source and fixture map

- `features/context/entry_ideas.py`: candidate signal construction and PO3
  active-zone gating.
- `features/context/trade_setup_candidates.py`: candidate identity fields.
- `features/context/swing_retracement.py`: confirmed-leg validity and band.
- `features/po3/ifvg_detection.py`: 50-bar source-FVG age and confirmation.
- `features/po3/ifvg_state.py`: accepted sweep, replacement, and PO3 setup
  lifecycle.
- `features/po3/po3_phase_state.py`: active IFVG zone and retest lifecycle.
- `evaluation/candidate_proposals.py` and
  `scripts/research/analysis/evaluation/build_candidate_proposal_ledger.py`:
  fixed proposal validity and common TTL.
- `evaluation/candidate_execution.py`: replay through the proposal TTL without
  a producer-signal invalidation stream.
- Existing direct fixtures reviewed: `tests/unit/features/test_po3_ifvg_state.py`,
  `tests/unit/features/test_entry_ideas.py`,
  `tests/unit/features/test_trade_setup_candidate_events.py`, and
  `tests/research/test_candidate_geometry_support.py`. This source review does
  not claim those tests were run in this continuation or that they cover every
  configuration.
