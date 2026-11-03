# Focused history and action-mask behavior tests

These tests were run in the existing GH200 allocation `21367992` on
`gpuarm2`, using the repository's ARM64 `.venv` through `python -m pytest`.
All three passed in 19.82 seconds. The exact test output is preserved in
`pytest_output.txt`; test and implementation details are in `run_metadata.json`.

The history test changes an earlier valid M5 observation while holding the
latest observations fixed and confirms that the MTF reasoning latent changes.
The actor tests confirm row-wise invalid setup choices have zero probability,
sampled setup IDs stay within each row's mask, and the conditioned execution
output changes with the selected setup ID. The selector itself takes only the
market latent.

These are synthetic/configured implementation behavior checks. They do not
verify every historical checkpoint, candidate-specific price geometry,
training quality, or economic performance.

Reproduce from the repository root on the matched ARM64 environment:

```bash
.venv/bin/python -m pytest -q \
  tests/unit/models/test_encoders.py::test_mtf_reasoning_encoder_uses_earlier_history_with_latest_candle_fixed \
  tests/unit/models/test_hybrid_actor.py::test_trade_setup_hybrid_distribution_samples_only_each_rows_valid_candidates \
  tests/unit/models/test_hybrid_actor.py::test_trade_setup_conditioned_distribution_masks_and_conditions_execution
```
