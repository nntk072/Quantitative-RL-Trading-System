# Documentation coverage audit

This reviewed matrix records reader paths that help someone **learn** a
subject, **use** it, and **verify** exact behavior. A link alone does not mean
the subject is fully explained. `●` means a maintained, subject-specific page
exists; `◒` means coverage relies on a broad/shared guide or has known limits;
`—` means no dedicated path was identified in the review. Research and
reproduction cells indicate evidence relevance, not evidence strength.

| Subject | Concept | Architecture | Tutorial | How-to | Reference/API | Troubleshooting | Research | Reproduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Product overview | ● | ● | ◒ | ◒ | ◒ | — | ◒ | — |
| Market data and sessions | ◒ | ● | ● | ● | ● | ◒ | ◒ | ● |
| Ticks and resampling | ◒ | ◒ | ● | ◒ | ● | ◒ | ◒ | ◒ |
| Splits and walk-forward | ● | ● | ● | ◒ | ● | ◒ | ● | ◒ |
| Feature causality/normalization | ● | ● | ● | ● | ● | ◒ | ◒ | ● |
| Cache identity | ◒ | ◒ | ◒ | ● | ● | ● | ◒ | ◒ |
| Technical indicators | ◒ | ● | ● | ● | ● | ◒ | ◒ | ◒ |
| Swings, liquidity, SMT, PO3, FVG/IFVG | ● | ◒ | ◒ | ◒ | ● | ◒ | ● | ◒ |
| Order blocks and premium/discount | ◒ | ◒ | ◒ | ◒ | ● | ◒ | ● | ◒ |
| Trade setups | ● | ◒ | ◒ | ◒ | ● | ● | ● | ● |
| Observations and masks | ● | ● | ● | ◒ | ● | ◒ | ◒ | ● |
| Action schemas and parameterization | ● | ◒ | ● | ● | ● | ◒ | ◒ | ● |
| MDP/POMDP | ● | ◒ | ◒ | — | ◒ | — | ◒ | — |
| PPO and rollout geometry | ● | ● | ● | ● | ● | ◒ | ● | ◒ |
| SAC | ● | ◒ | ● | ◒ | ● | ◒ | ◒ | ◒ |
| Constrained RL | ● | ◒ | ● | ◒ | ◒ | ◒ | ◒ | ◒ |
| TCN/GRU/Transformer/MTF | ● | ● | ● | ● | ● | ◒ | ● | ◒ |
| Stops, targets, multi-TP, exits | ● | ● | ● | ◒ | ● | ● | ● | ● |
| Account state, risk, prop constraints | ● | ◒ | ● | ◒ | ● | ● | ◒ | ◒ |
| Execution, fills, costs | ● | ● | ● | ◒ | ● | ● | ● | ● |
| Reward and attribution | ● | ◒ | ◒ | ● | ● | ◒ | ● | ● |
| Training, seeds, resume, checkpoints | ◒ | ● | ◒ | ● | ● | ● | ◒ | ◒ |
| Evaluation metrics and inference | ● | ● | ● | ● | ● | ◒ | ● | ● |
| Multiple testing and cost stress | ● | ◒ | ◒ | ◒ | ◒ | — | ● | ◒ |
| Experiment design, controls, ablations | ● | ● | ◒ | ● | ● | ◒ | ● | ◒ |
| Artifacts and evidence lineage | ● | ● | ◒ | ● | ● | ◒ | ● | ● |
| Research findings and negative results | ◒ | ◒ | — | — | ◒ | — | ● | ● |
| Live/paper and MetaTrader | ◒ | ● | ◒ | ● | ● | ◒ | — | ◒ |
| Triton, Slurm, hardware, performance | ◒ | ● | ◒ | ● | ◒ | ● | ● | ◒ |
| Security and dependency handling | ◒ | ◒ | — | ● | ● | ◒ | — | — |
| Extension development and tests | ◒ | ● | ◒ | ● | ● | ◒ | — | ◒ |

## Coverage interpretation and remaining work

- The site has dedicated curated API domains and generated AutoAPI. API
  existence does not replace concept explanations or executable examples.
- The beginner and advanced notebooks provide focused runnable examples for
  core workflow and algorithm concepts. Notebook links should remain bounded
  and labeled by evidence tier.
- Several research pages explain exploratory/negative findings. Those pages
  do not imply that all planned research questions have results.
- Troubleshooting is now consolidated by symptom; subsystem package guides
  remain the source for deeper diagnostics.
- `◒` and `—` entries are intentional gap markers, not a completion claim.
  Update this table with evidence links when a dimension becomes dedicated.

The [page inventory](../documentation_inventory.json) validates page
navigation/orphans; this subject matrix is a separate, human-reviewed
completeness measure.
