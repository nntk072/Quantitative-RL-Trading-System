# Multi-timeframe encoder comparison

## Research question

Can the model process multiple timeframes with less computation while keeping
the same information, policy meaning, and PPO training geometry?

## Compared architectures

| Architecture | What it does | Information available |
|---|---|---|
| Independent temporal encoders | Uses a separate temporal network for each timeframe, then combines their representations | Full configured history for every timeframe |
| Shared temporal encoder | Reuses one temporal network across timeframes, with small timeframe-specific input adapters | Full configured history for every timeframe |
| History-aware higher-timeframe summaries | Uses the main temporal network for M1 and summarizes valid historical context from higher timeframes | M1 sequence plus history-aware summaries for higher timeframes |
| Latest-valid higher-timeframe state | Uses the main temporal network for M1 and the latest causally complete observation from each higher timeframe | M1 sequence plus each timeframe’s latest valid state |

## Bounded throughput result

The isolated comparison used the same GH200, data bundle, PPO geometry, and
eight parallel environments. It completed two repeats of 65,536 steps per
architecture. Results below are the mean and sample standard deviation across
those two repeats.

| Architecture | Parameters | PPO-core steps/second | Relative rate |
|---|---:|---:|---:|
| Independent temporal encoders | 8.87 million | 81.9 ± 2.4 | 1.00× |
| Shared temporal encoder | 1.33 million | 209.2 ± 1.0 | 2.55× |
| History-aware higher-timeframe summaries | 1.43 million | 184.8 ± 7.2 | 2.26× |
| Latest-valid higher-timeframe state | 1.43 million | 199.1 ± 10.0 | 2.43× |

The shared encoder had the highest measured throughput and lowest parameter
count. Its peak allocated GPU memory was higher than the other designs in this
measurement, though still small relative to the GH200’s available memory.

## Short policy screen

A separate 20,480-step pilot included the production preparation and callback
path, followed by a 5,293-decision prefix replay from the training year.

| Architecture | Executed trades in prefix | Ending prefix equity | No-trade action rate | Invalid thesis selections |
|---|---:|---:|---:|---:|
| Independent temporal encoders | 0 | Not reported | 53.8% | 0 |
| Shared temporal encoder | 275 | $98,089.60 | 74.6% | 0 |
| History-aware higher-timeframe summaries | 201 | $102,253.41 | 65.4% | 0 |
| Latest-valid higher-timeframe state | 176 | $111,270.66 | 67.0% | 0 |

Each architecture selected multiple thesis categories in this short screen.
These figures describe an exposed training-period prefix, not a full-year or
test result. They do not show that a faster architecture improves trading
performance.

## Conclusion

Sharing temporal computation materially increased measured PPO-core
throughput. The policy pilots are too short and too exposed to select a
trading model. No architecture has established full-period survival,
independent-seed robustness, or out-of-sample profitability. Treat this as an
engineering comparison that can guide future matched experiments, not as a
model ranking.
