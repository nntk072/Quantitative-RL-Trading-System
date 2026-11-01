# Sequence models and multi-timeframe encoders

Sequence encoders transform recent feature windows into a representation used
by policy and value networks. They are representations of the supplied data,
not separate trading rules.

## Architectural choices

| Family | Core operation | Typical advantage | Cost or caution |
|---|---|---|---|
| TCN | Causal convolutions with expanding receptive field | Parallel sequence processing and local temporal structure | Receptive field depends on depth, kernel, and dilation. |
| Lite TCN | Smaller configured causal convolution stack | Lower parameter/compute budget for bounded comparisons | Smaller capacity is not evidence of better generalization. |
| GRU | Recurrent gated state update | Compact sequential summary | Sequential dependency can limit parallelism; hidden state is learned. |
| Transformer | Attention over a finite sequence | Flexible relations between positions | Attention is not automatically causal; input construction and masking must enforce time boundaries. |
| MTF | Encodes multiple aligned timeframe windows | Combines local and slower context | Alignment and completed-bar timing are essential; more scales add compute. |

The registry is in the [`models/encoders` package guide](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/models/encoders/README.md), and
the exact selectable names and configuration are in the
[model architecture reference](../reference/model_architectures.md). The
current `build_agent` dispatches `tcn`, `transformer`, `gru`, `mtf`, and
additional named variants. Some MTF variants require `mtf=True`; regime-aware
TCN requires the versioned regime observation. Check builder validation
before copying an architecture name from a historical experiment.

## Causality is a data contract

The model receives an already constructed sequence. Causal convolutions alone
cannot repair a future-leaking feature, a higher-timeframe candle exposed
before close, or a train/test normalization leak. The complete path is:

```text
timestamped bars → completed-bar alignment → causal features → fit-scope
normalization → validity masks → sequence window → encoder
```

See [causality](causality.md),
[multi-timeframe tutorial](../learn/tutorials/advanced/multi_timeframe_features.ipynb),
and [architecture comparisons](../research/encoder_architecture_comparison.md).

## Comparing encoders fairly

Hold data partitions, feature cache identity, action schema, policy budget,
seed protocol, evaluator, and resource limits fixed unless one is the declared
factor. Record the resolved config and actual rollout geometry. Do not tune on
the locked holdout. A throughput difference is an engineering result; a return
difference needs a research protocol and uncertainty analysis.

The historical encoder comparison is a bounded engineering and short-policy
screen, not evidence that one architecture is economically superior. See its
[status and limits](../research/encoder_architecture_comparison.md).
