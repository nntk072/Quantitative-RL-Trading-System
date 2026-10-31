# Glossary

Use these terms consistently in documentation and reports.

| Term | Meaning |
|---|---|
| M1 / M3 / M5 | One-, three-, or five-minute bar timeframe. A bar's final values are available only after it closes. |
| Lower/higher timeframe | A timeframe shorter/longer than the policy's decision interval. Availability still follows source-bar close time. |
| PO3 | Power of Three market narrative: accumulation, manipulation, and distribution phases. A configured feature/idea, not a guaranteed market mechanism. |
| FVG | Fair-value gap: a three-candle price imbalance under the configured structural definition. |
| IFVG | Inverse fair-value gap: an imbalance whose role changes after the configured invalidation/close condition. |
| SMT | Smart Money Technique divergence: relative disagreement between related instruments under the configured comparison. |
| Order block | A candle/price region classified by a configured market-structure rule; the label alone does not imply predictive power. |
| Trade setup | A selected entry idea, setup timeframe, and direction with eligibility and structural context. Historical serialized `thesis_*` names may represent this same domain concept. |
| Entry idea | A rule family used to describe a potential trade rationale, such as a gap reaction or structure setup. |
| Entry state | The lifecycle state of a possible trade before and after an order opens. |
| Observation schema | Versioned contract describing model inputs, tensor layout, optional branches, and masks. |
| Action schema | Versioned contract describing policy outputs and their meaning. |
| Risk budget | A configured limit or allowance for risk exposure/cost; its units and equity base must be explicit. |
| R multiple | Trade outcome divided by the initial monetary risk assigned to that trade. |
| DSR | Differential Sharpe Ratio reward/update signal used by an existing reward mode. It is not the same as realized portfolio Sharpe. |
| Episode | A finite sequence of environment transitions with reset and termination/truncation semantics. |
| Rollout | A batch/sequence of environment transitions collected for policy learning or evaluation. |
| Checkpoint | Serialized model and policy state, often including constructor/schema metadata needed for reload. |
| Variant | A resolved set of experiment settings intended to represent one comparison arm. |
| Experiment run | One identifiable execution of configured variants, seeds, data, and training/evaluation procedure. |
| OOS | Out-of-sample data not used to fit, tune, or select the evaluated policy. Exposure during development removes confirmatory status. |
| Walk-forward | Chronological repeated fitting/evaluation procedure with training windows preceding their test windows. |
| Purge / embargo | Removal of overlapping label/look-ahead intervals and a separation gap around validation folds. |
| Artifact | A saved input, model, log, report, ledger, or manifest associated with a computation. |
| Lineage | Recorded relationship from source data/config/code through cache, run, checkpoint, and result. |
| Baseline | A declared control used to interpret a treatment under a specified comparison protocol. |
| Paper trading | Live-market observation and/or simulated order handling without submitting real broker orders. |
| Live trading | Order submission through a real broker account; it has separate operational and financial risks from historical simulation. |
