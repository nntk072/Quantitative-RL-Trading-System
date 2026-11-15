# QA for research findings and negative results

**Status:** Five source claims and eight register rows verified against the
2026-11-15 working tree at HEAD `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Source claims

1. `schemas/research_result_manifest_v2.schema.json` requires the finding ID,
   question, hypothesis, status, evidence grade, claims and artifact list.
2. The schema's run record requires its ID, variant, seed, role, status,
   identity and artifacts.
3. `scripts/research/analysis/evidence/verify_result_manifest.py` rejects
   unknown frozen-v2 run identities. It also requires a freeze timestamp
   and nonempty claims, comparisons and runs.
4. The prospective protocol blocks portfolio optimization after failed
   survival qualification. The validation protocol bounds negative survival
   and superiority conclusions by the prespecified safety and inference rules.
5. The result verifier checks claim-to-comparison and comparison-to-run
   references, then verifies artifact paths and SHA-256 when hash
   verification is enabled. This holds in the modified working-tree verifier.

## Document and notebook checks

The hub has 150 lines and all 11 required sections. Ten hub links, both
reference links and the hidden notebook target resolve. The reference's
reproduction levels match the result registry.

The notebook has matching title and first heading, Python 3 kernel, Tier A,
bundled synthetic data, CPU, subject, owner and under-60-seconds metadata,
and forced MyST execution. Schema and metadata checks accepted it. Its
assert-bearing code cell has count 1, one saved stdout output and no saved
errors. Saved cell timing is 0.006 seconds. It distinguishes the synthetic
breach, no-trade and missing paths, with the survival gate false.

## Findings register

All eight entries contain a prospective method, evidence availability and
missing provenance, with status **Not measured** and no assigned R level.
The data-quality row links the retained raw-data identity manifest, whose
38 file records and null campaign-audit references support the stated
identity-only scope. The remaining seven rows identify unavailable paths
and the records needed for a finding. The evidence report and result
registry support these dispositions. The seven register links resolve.

The eight methods cover data coverage, causal feature availability, replay
parity, candidate geometry, survival, the primary flat-control comparison,
secondary controls and finalist stress. Their scope agrees with the active
validation protocol and evaluation methodology. The register preserves the
exposed role of the 2026 report period.

QA inspected retained metadata and notebook output. Raw CSV byte
verification and research or notebook execution were outside this review.
