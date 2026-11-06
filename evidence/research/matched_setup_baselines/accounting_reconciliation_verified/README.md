# Matched setup baseline accounting reconciliation

This independently checks the preserved matched-baseline result bundle's decision-to-open links, candidate eligibility, event chronology, position cashflows, equity summary, and breach counts. It validates accounting and telemetry consistency for these recorded runs; it does not validate broker fills, establish a historical policy replay, or make an economic-edge claim.

- Bundle: `matched_setup_policy_evaluation`
- Initial balance: $100,000.00
- Verifier status: **passed**

| Arm | Status | Decisions | Opens | Realized net PnL | Ending equity | Breaches |
|---|---:|---:|---:|---:|---:|---:|
| always_no_trade | passed | 99492 | 0 | 0.000000 | 100000.0 | 0 |
| random_eligible_setup | passed | 99492 | 1854 | -10159.848495 | 89840.15150531461 | 25 |
| structure_priority | passed | 99492 | 1169 | -10034.896372 | 89965.10362806503 | 25 |

Reproduce from the repository root inside a compatible Python environment:

```bash
.venv/bin/python -m scripts.research.analysis.evaluation.verify_matched_setup_baseline_accounting \
  --bundle-dir /scratch/work/nguyenl37/Quantitative-RL-Trading-System/evidence/research/matched_setup_baselines/matched_setup_baselines_19770241b07b5b5e \
  --output-dir /scratch/work/nguyenl37/Quantitative-RL-Trading-System/evidence/research/matched_setup_baselines/accounting_reconciliation_verified
```
