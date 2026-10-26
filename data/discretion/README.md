# Discretion price data

`training/` and `testing/` are local links to the shared raw inputs under
`data/training/` and `data/testing/`. The discretion profile applies the
configured quarter-point price grid during preprocessing and writes separate
derived caches to `cache/data_modes/discretion/`. Raw source files are not
copied or modified.

Run `bash scripts/data/setup_mode_dirs.sh` after placing the shared raw inputs
in their canonical folders.
