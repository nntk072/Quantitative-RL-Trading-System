# Matched setup baseline evidence

This packet records Tier 0 accounting controls and one fixed Tier 1
structure-priority rule on the local 2025 development split. It is not a
promoted policy comparison: the random arm is one seeded reference with
unequal realized risk, and the historical RL checkpoint cannot be
independently replayed under this current execution path.

## Completed matched trajectory

[`matched_setup_baselines_19770241b07b5b5e/`](matched_setup_baselines_19770241b07b5b5e/)
contains three arms evaluated over 351,432 bars and 99,492 decisions each,
using the same bars, features, and TickBook inputs. All saved equity paths
have 99,493 points. The draft result manifest passed schema, cross-reference,
and artifact-hash verification with its packet root as the verifier root:

```bash
.venv/bin/python -m scripts.research.analysis.evidence.verify_result_manifest \
  evidence/research/matched_setup_baselines/matched_setup_baselines_19770241b07b5b5e/result_manifest.json \
  --repo-root evidence/research/matched_setup_baselines
```

The `always_no_trade` control made no entries or fills, ended at $100,000, and
had zero return, drawdown, and breaches. Its own confidence intervals are
zero (win rate is undefined). The `random_eligible_setup` arm completed 1,854
positions and 1,895 fills, ended at $89,840.15 (-10.16%), and recorded 25
breach events. The fixed `structure_priority` rule completed 1,169 positions
and 1,209 fills, ended at $89,965.10 (-10.03%), and also recorded 25 breach
events. Both trading arms failed the zero-breach survival gate. Each arm has
its own within-trajectory intervals; the flat arm's interval file and all
manifest comparison rows contain the corresponding arm's values. The paired
one-path comparisons are aligned by the exact shared environment-step
sequence because input hashes, step count, and evaluation bounds match.
Valuation timestamps remain separately recorded because fills can occur
within a bar. The paired structure-versus-random confidence intervals include
zero for mean bar return, Sharpe, Sortino, and drawdown difference.

These are negative Tier 0/Tier 1 reference results, not evidence of a viable
strategy, an RL ranking, between-seed uncertainty, equal realized-risk
comparison, or confirmatory out-of-sample performance. The independent-seed,
cost-stress, and untouched-holdout gates remain open or no-go.

## Superseded attempts

`matched_setup_baselines_18c585089f5e7857/` is the earlier completed flat-only
control. `matched_setup_baselines_8afa8f28a2342aa1/` and
`matched_setup_baselines_3142f2920f4bd0cd/` are preserved but superseded: the
writer copied the later random arm's confidence intervals into the flat arm.
`matched_setup_baselines_58323baeba0eb79f/` is a valid earlier two-arm bundle.
`matched_setup_baselines_571b404168826c0e/` has valid per-arm outputs, but its
flat-versus-random comparison included the structure rule's metrics; its
comparison metadata is superseded. The writer now limits comparison rows to
the declared run IDs, covered by a regression. Earlier protective-level
failures remain diagnostic only;
[`random_eligible_setup_execution_diagnostics.json`](random_eligible_setup_execution_diagnostics.json)
preserves their evidence and dispositions.

Provider/license and external calendar research were excluded by user
direction. The result uses only local data and makes no data-rights claim.
