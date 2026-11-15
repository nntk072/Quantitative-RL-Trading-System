# Market data

Keep one full-period source CSV per symbol and timeframe in this directory.
The configured training and testing datasets read those same files and select
their inclusive date windows from `config/base/default.yaml`. The source
filename records the export's covered dates; it does not define the active
research split.

`examples/` contains small versioned inputs for documentation and tests.
Generated bars, features, and tick books belong under the ignored `cache/`
directory. Cache identities include the source hash and selected date window.
Confirm each cache manifest against the raw input hashes before using it for
an experiment.
