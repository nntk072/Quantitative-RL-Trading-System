# PO3 phase state

The project implements a causal state machine for accumulation context,
liquidity sweep, manipulation, and distribution. In the long-side path, an
eligible sell-side sweep starts a manipulation leg and tracks its running
high/low. A later close above the prior manipulation high marks the end of
manipulation and starts the distribution state with positive direction. The
short side mirrors the rule. A fresh same-side sweep resets the manipulation
range; an opposite-side sweep re-arms the mirrored direction. Distribution
retains the frozen manipulation levels for downstream structural stop
placement.

PO3 outputs are causal features. Their presence does not imply a policy chose
the associated setup. Active entry ideas additionally combine configured
FVG/IFVG, retest, timeframe, and trigger evidence. Keep those mechanisms
separate when explaining a result.

See [`po3_phase_state.py`](../../features/po3/po3_phase_state.py),
[`trigger_rules.py`](../../features/po3/trigger_rules.py),
[PO3/IFVG decisions](../decisions/po3_ifvg_decisions.md), and
[focused state tests](../../tests/unit/features/test_po3_state.py).
