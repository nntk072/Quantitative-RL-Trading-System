# Training throughput: findings and limits

## Question

Can the current GH200 training path complete the planned PPO work within the
available allocation, and which part of the path limits speed?

## What was measured

Matched PPO runs used eight environments, the same aggregate rollout geometry,
and the same training data bundle. Repeated 100,000-step screens completed
about 100,000 transitions per arm. Across repeats, PPO-core throughput ranged
from roughly 75 to 96 environment steps per second. Deferred dashboard
evaluation improved some repeats, but the measurements varied enough that one
fast run should not be treated as a guaranteed rate.

Separate encoder experiments found that a shared temporal encoder and two
lightweight multi-timeframe alternatives ran faster in isolation than nine
independent temporal encoders. The largest measured gain was about 2.6 times
PPO-core throughput. That is a bounded engineering result, not evidence of
better trading behavior or a direct estimate of full-run duration.

## Bottlenecks observed

- CPU-side rollout, vector-environment dispatch, and reporting consumed more
  time than the PPO update in the measured configuration.
- GPU utilization was low on average and did not show that GPU memory capacity
  was the limiting resource.
- Small, variable-shape temporal convolutions and environment/IPC work can
  leave the GPU waiting for the next batch.
- Adding more workers is not automatically faster; worker count, CPU capacity,
  memory use, and IPC must be measured together.
- A complete run also needs data preparation, checkpoint handling, full-period
  train evaluation, test/report evaluation, and report generation. PPO-core
  throughput alone understates end-to-end time.

## Decision and limits

The throughput screens demonstrated that the implementation can learn at a
useful bounded rate, but they did not establish reliable full-run timing. More
importantly, the matched policies failed the account-survival screen in the
full training-period replay. A faster implementation does not resolve that
economic failure, and throughput evidence alone is not a reason to start a
longer training run.

These measurements apply to the tested model, environment geometry, software,
and GH200 setup. They are not a hardware-wide guarantee. The original detailed
profile and attempt notes are retained in the external research archive; this
page keeps the conclusion and measured ranges for readers.
