# Fair-value gaps and inverse-gap confirmation

## FVG detection

The current detector uses a three-bar imbalance rule, with the third bar as the
event bar:

- bullish: current bar low is above the first bar's high;
- bearish: current bar high is below the first bar's low.

The emitted zone boundaries are the two non-overlapping prices. A configured
minimum imbalance can suppress smaller gaps. A detected gap is a feature-zone
candidate; it is not an order or an assertion that price must return to it.

## IFVG confirmation

The stateful IFVG detector tracks active zones and pass-through price action.
Confirmation requires a zone pass, then a *later* close through the zone and
beyond the recorded passing-wick extreme. Optional fractional buffer settings
can require additional distance. The `inverse_opposing_fvg` flag selects
whether confirmation uses the opposing-orientation gap or retains the
historical same-orientation behavior. That compatibility option is part of the
feature configuration and cache identity.

Zones age out and can be invalidated; do not treat a once-detected gap as
permanently active. Higher-timeframe state is not visible until its source
candle completes.

Implementation: [`fvg_detection.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/features/po3/fvg_detection.py),
[`ifvg_detection.py`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/features/po3/ifvg_detection.py),
[PO3 feature guide](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/features/po3/README.md),
and the [configuration reference](../reference/configuration.md).
