# Normal price data

`training/` and `testing/` are local links to the shared raw inputs under
`data/training/` and `data/testing/`. The normal profile leaves prices
continuous and writes derived caches to `cache/data_modes/normal/`.

Run `bash scripts/data/setup_mode_dirs.sh` after placing the shared raw inputs
in their canonical folders. Raw source files are not copied or modified.
