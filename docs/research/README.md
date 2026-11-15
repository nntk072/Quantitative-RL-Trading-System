# Research

This section documents research methods and validity constraints. Historical run outputs and data-derived evidence were removed during the
2026-11-15 clean restart; their numerical findings are not current results and
must not be cited as evidence for the refreshed dataset.

The retained local source identity is recorded in
[`raw_data_manifest.json`](../../evidence/research/data_identity/raw_data_manifest.json).
It hashes the canonical full-period CSVs and records the registered training
and exposed reporting windows. Training and testing select dates from those
same source files. The manifest does not validate feature-cache compatibility
or establish any scientific result. Its reproducible file list is
[`raw_source_inventory.json`](../../evidence/research/data_identity/raw_source_inventory.json).
The former partition-file manifest is
preserved as
[`raw_data_manifest_partitioned_20261115.json`](../../evidence/research/data_identity/raw_data_manifest_partitioned_20261115.json)
for migration provenance.

Use the remaining pages for methodological background. Regenerate all empirical
artifacts from the retained raw CSVs and current source before making claims.

```{toctree}
:hidden:

references
multitimeframe_data_alignment
feature_causality_and_availability
candidate_geometry_feature_contract
mt5_ftmo_execution_fidelity
result_identity_and_evidence
research_evidence_report
validation_protocol
evaluation_methodology
findings_register
limitations
../research_reference
```
