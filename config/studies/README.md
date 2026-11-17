# Study configurations

Use `default.yaml` to enable or disable a workflow section, module, or individual
study. Its `runtime.config` points to the canonical runtime YAML read by
`qrl-train`; the workflow sections gate study planning. Each file under
`profiles/` owns the questions, source paths, config inputs, focused checks,
arms, and outputs for one repository module.

For example, a study can be disabled while leaving the rest of its module on:

```yaml
modules:
  features:
    enabled: true
    studies:
      features.causal_availability: false
```

```bash
qrl-study list
qrl-study validate
qrl-study plan
qrl-study check --dry-run
qrl-study check --module features
qrl-study check --study features.causal_availability
```

`plan` resolves source, config, API, and caller inputs and their content hashes.
It does not run checks, train a model, launch a scheduler job, or connect to a
broker. `check` runs only the pytest paths registered by selected enabled code
checks and audit studies. A passing audit study here means its declared tests
passed; it does not mean the data audit ran or that an evidence report was
generated. The result records audit tools as not executed. Run a package-owned
audit tool directly when its registered inputs are available and its research
run is authorized. `check` never runs empirical studies. Use `--dry-run` to
inspect its dependency order and blocked prerequisites; `--output-dir` writes a
new JSON report and refuses to overwrite one. No shell commands or arbitrary
plugin imports are accepted. On Triton, run multi-minute checks within an
existing CPU allocation as required by `.agents/rules/triton-slurm.md`.

Empirical definitions must list their registered arms and config files
explicitly; the framework does not construct Cartesian products.

The current measured questions are registered under `market_data`, `features`,
`simulation`, `training`, `evaluation`, and `trading`: source quality, prefix
causality, tick execution/accounting parity, survival qualification, candidate
geometry, primary and secondary comparisons, and finalist robustness. Their
arms name config inputs and changed factors; prerequisites gate downstream
questions. `qrl-study plan` resolves and hashes these definitions but does not
authorize or launch a run. Finalist robustness is conditional on a qualified
primary result.

`qrl-study validate` also fails when a source file, external API caller, or a
runtime config under `config/` has no owning study scope or inventory entry.
Add its paths to the owning profile as part of the same change. API and caller
inventories are checked against the repository's Python import graph.

Keep each question limited to one decision. If a setting affects more than one
module, list it in each affected study so the dependency remains visible. When
adding source or config files, extend the owning profile and its focused test
paths in the same change.
