# Training configuration

`training/configuration/` parses training CLI arguments, resolves experiment
variants, loads quality settings, and applies variant-specific configuration
overrides. `config/` remains the single source of truth for runtime settings;
this package validates and resolves those settings for a run.

Resolved configuration should make effective defaults and overrides explicit
in the run artifacts. Keep variant identity and resource assumptions aligned
with the experiment catalog. Focused checks are in `tests/unit/training/` and
`tests/unit/configuration/`.
