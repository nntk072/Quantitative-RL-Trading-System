# IFVG distance when ATR is unavailable

`ifvg_bull_distance_atr` and `ifvg_bear_distance_atr` previously divided a
zone-edge distance by `1.0` when ATR was NaN or nonpositive. That produced a
price-unit value mislabeled as an ATR-normalized distance. The producer now
retains the explicit `5.0` missing-distance sentinel, matching the FVG
distance contract, and feature cache identity advances to
`v40-ifvg-missing-atr-distance`.

The focused regression injects unavailable ATR values and checks active bull
and bear zones. The complete PO3-state unit module passed 22 tests on the
existing GH200 allocation; scoped Ruff checks passed. Source hashes and the
captured validation output are included.

This verifies the missing-ATR fallback only. It does not rerun the all-profile
real-market prefix audit, establish external feature availability, or close
the broader Stage D feature-family gates. The prior all-profile report remains
bound to its recorded v39 source snapshot until a current-source run replaces
it.
