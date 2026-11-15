# Performance engineering

Measure the complete pipeline before optimizing. A GPU can be underused when
environment transitions, pandas operations, feature preparation, Python
workers, storage, host-to-device copies, or logging dominate elapsed time.

## Profile stages separately

Record wall time and throughput for:

1. data loading/cache validation;
2. feature construction, if performed in the run;
3. environment stepping;
4. policy inference and update;
5. rollout transfer and replay sampling;
6. evaluation, reporting, and artifact writes.

Training steps per second are not trading performance. Record the hardware,
software versions, environment count, observation size, algorithm, batch/rollout
geometry, data source, and warm-up policy with each benchmark. Compare the
same workload and report variability.

## When a GPU is not the bottleneck

- Low GPU utilization with high CPU use suggests Python/environment or input
  bottlenecks; inspect per-process CPU, worker count, and environment latency.
- Low GPU and low CPU use can indicate storage waits, synchronization, or
  oversized logging/checkpoint intervals; inspect stage timing and I/O.
- High GPU utilization with poor throughput can indicate excessive sequence
  length, small batches, memory pressure, or costly host/device transfers.
- More vector environments may improve throughput while changing memory use
  and rollout sampling geometry. Keep fixed geometry when comparing research
  treatments.

## Record current measurements

Use the architecture-matched environment and a current allocation. Record the
workload, rollout geometry, device, CPU and memory use, evaluation cost, and
checkpoint/report time. A measured run describes only that source, data, and
resource setup; old throughput figures are not a forecast.

For node-specific environment instructions, see the
[hardware matrix](hardware.md) and [Triton guide](triton.md).
