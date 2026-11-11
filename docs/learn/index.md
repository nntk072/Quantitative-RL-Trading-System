# Learn Quant

Move through the framework in the same order a run uses: inspect bars, build causal features, decide risk, step the environment, and evaluate outcomes.

Begin with [quantitative trading and RL foundations](foundations.md) if you
are new to the problem or the algorithms.

## Beginner tutorials

The [foundations guide](foundations.md) explains the problem, observation,
algorithms, action path, and evidence levels used by these notebooks.

```{toctree}
:maxdepth: 1
:caption: Beginner

foundations
tutorials/01_market_data.ipynb
tutorials/02_causal_features.ipynb
tutorials/03_trading_and_risk.ipynb
tutorials/04_environment.ipynb
tutorials/05_evaluation.ipynb
tutorials/06_walk_forward_validation.ipynb
tutorials/07_action_schema_contract.ipynb
```

The earlier command-line overview remains available in [Tutorials](../tutorials/README).
For one joined walkthrough across these notebooks, see the
[end-to-end learning path](../tutorials/end_to_end_path.md).

## Advanced tutorials

```{toctree}
:maxdepth: 1
:caption: Advanced

tutorials/advanced/multi_timeframe_features.ipynb
tutorials/advanced/trade_setup_policy.ipynb
tutorials/advanced/tick_execution.ipynb
tutorials/advanced/custom_encoder.ipynb
tutorials/advanced/experiment_comparison.ipynb
tutorials/advanced/ppo_rollout_geometry.ipynb
tutorials/advanced/sac_continuous_policy.ipynb
tutorials/advanced/constrained_reward_signals.ipynb
```

## Bounded training demonstration

The [first reproducible run](../tutorials/first_reproducible_run.md) explains the small software workflow and its evidence limits. Its output is not a research result.
