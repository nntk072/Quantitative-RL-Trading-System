# Current scope correction

This packet preserves its original market-only source review and source
hashes. `SOURCE_SHA256SUMS` fingerprints the source files inspected when this
packet was created; several paths have since changed, so those historical
hashes are not expected to match the current checkout. The current
market/limit execution path and current source hashes are recorded separately
in `../learned_market_limit_execution_path/`.
