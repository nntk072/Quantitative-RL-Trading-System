# Matched setup baseline CLI contract

This packet verifies the opt-in `--include-structure-priority` CLI switch. Its
six focused tests cover default-off parsing, explicit opt-in parsing, and
construction of the structure-priority arm with its declared rule metadata.
The runner and test pass touched-path Ruff check and format checks.

Reproduce from the repository root:

```bash
.venv-x86/bin/python -m pytest tests/unit/evaluation/test_matched_setup_baseline_cli.py -q
.venv-x86/bin/ruff check scripts/research/analysis/evaluation/run_matched_setup_baselines.py tests/unit/evaluation/test_matched_setup_baseline_cli.py
.venv-x86/bin/ruff format --check scripts/research/analysis/evaluation/run_matched_setup_baselines.py tests/unit/evaluation/test_matched_setup_baseline_cli.py
```

This is a CLI and policy-registration contract check. It does not run the
baseline on market data or establish a performance comparison. Those runs
remain gated on the local data, feature-causality, and simulator/accounting
gates.
