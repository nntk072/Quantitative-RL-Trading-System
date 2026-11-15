# QA for experiment design, controls and ablations

**Status:** Five source claims verified against the 2026-11-15 working tree at
HEAD `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Source claims

1. `config/research/prospective_research_protocol.yaml::primary_statistics`
   declares always-no-trade as the primary comparator and places survival
   first.
2. `evaluation/metrics/matched_comparison.py::compare_matched_returns`
   rejects missing or mismatched required provenance and enforces equal,
   ordered, unique timestamp indexes matching the declared endpoints.
3. The matcher permits one declared intervention, chosen from feature,
   reward, environment, cost or policy identity. Each arm needs a distinct
   nonempty value for that field. Other required match fields must agree.
4. `evaluation/rollout/matched_setup_baselines.py::evaluate_tier0_setup_baselines`
   gives each arm the shared bars, features, tickbook and common settings
   with a fresh environment.
5. Non-synthetic setup baseline roles require a finite positive absolute
   dollar ceiling. The helper applies it to the requested risk band.

## Document and notebook checks

The corrected hub has 152 lines and all 11 required sections. Eight hub
links, the reference link and the hidden notebook target resolve. The hub
and reference now point to the integration tests that directly exercise
`compare_matched_returns`. The cited unit tests cover paired equity
intervals and report records.

The notebook has matching title and first heading, Python 3 kernel, Tier A,
bundled synthetic data, CPU, subject, owner and under-60-seconds metadata,
and forced MyST execution. Schema and metadata checks accepted it. Its
assert-bearing code cell has count 1, one saved stdout output and no saved
errors. Saved cell timing is 1.710 seconds. It shows a 1.00% matched
difference and rejects the second change to `costs_sha256`.

## Evidence limit

The fixture uses synthetic returns and placeholder provenance strings.
QA inspected the saved state. Matched empirical ablations remain
unmeasured in the findings register.
