# Evaluate a checkpoint

Evaluation replays a saved policy with a declared observation/action schema,
market interval, execution model, and account configuration. It does not train
or update the checkpoint.

## Procedure

1. Identify the exact checkpoint and its run manifest. Verify the algorithm,
   encoder, schema versions, feature-cache identity, and source revision.
2. Resolve the evaluation period and its scientific role. A period already used
   to select settings is exploratory, even if it is named “test”.
3. Confirm that evaluation costs, quote source, fill timing, and risk limits
   match the intended comparison.
4. Run the existing evaluation command and preserve its ledgers, metrics,
   plots, and provenance together.

```bash
uv run qrl-evaluate reanalyze --help
uv run qrl-evaluate reanalyze --run outputs/<run-directory>
```

Use `--checkpoint` only when selecting a checkpoint other than the run's
default. Consult [checkpoint compatibility](../reference/checkpoint_compatibility.md)
before replaying a legacy artifact.

## Review before interpreting

Check that the replay covers the declared interval, does not stop at a training
constraint unless the evaluation policy requires that behavior, and reports
trade/equity ledgers consistent with the summary metrics. Inspect rejection
reasons, execution costs, account-limit events, and trade-level exits. A plot
or a single aggregate return does not establish generalization.
