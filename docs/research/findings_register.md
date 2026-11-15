# Research findings register

- **Evidence snapshot:** 2026-11-15
- **Owner:** `evidence_reporting_engineer`

The current research evidence directory retains a
[raw-data identity manifest](../../evidence/research/data_identity/raw_data_manifest.json).
It records local CSV file identity. The campaign input audit references are
empty. The [research evidence report](research_evidence_report.md) records
the removal of historical run outputs and derived evidence at the clean
restart. This register describes the evidence available for the refreshed
dataset and implementation.

## Current measurements

Methods below describe the checks required to support each result. The
evidence-path column describes the currently available record and the
specific provenance needed when the measurement is produced.

| Question | Status | Method | Evidence path and missing provenance | R1–R4 |
|---|---|---|---|---|
| Do the retained inputs meet the refreshed data quality and coverage requirements? | Not measured | Audit configured bar and quote intervals by symbol and session, including missing, duplicate and uncovered intervals. | [Raw CSV identity](../../evidence/research/data_identity/raw_data_manifest.json) is available. No current data-quality evidence path. The current source/config binding, split-specific denominator, quote coverage and audited output checksums are missing. | Unassigned |
| Are the configured observations, eligibility and event times causal and reproducible? | Not measured | Compare observations computed from truncated prefixes against matching full-history rows. Verify closed-bar availability and train-only fitted state. | No current feature-audit evidence path. Missing source, profile and cache identity, sampled row and family coverage, and checksummed prefix and availability reports tied to the retained inputs. | Unassigned |
| Do policy decisions and account transitions reconcile across execution paths? | Not measured | Match decisions, fills, charges, equity, loss limits and terminal states under common rules in environment rollout and event-driven backtest. | No current simulator reconciliation evidence path. Missing the matched replay config and period, quote inputs, order/fill and account ledgers, replay identities and checksummed reconciliation. | Unassigned |
| Is candidate price geometry supported by valid outcomes? | Not measured | Audit causal candidate proposals, quote-supported labels, censoring and chronological purge before a geometry ablation. | No current candidate audit or geometry comparison evidence path. Missing proposal, outcome and censoring ledgers, matching coverage, split and config identity, and any checksummed matched-ablation result. | Unassigned |
| Does a candidate complete every required hard-risk path? | Not measured | Apply the full-path survival gate to the prospectively fixed development and validation paths and paired seeds. | No current qualification evidence path. Missing frozen seed and path ledger, checkpoints, risk configuration and complete account traces with breach and terminal dispositions. | Unassigned |
| Does a qualified policy add value over always-no-trade? | Not measured | After survival, use the registered one-sided paired sign-flip test and paired seed bootstrap for full-path payout-aware return. | No current primary comparison evidence path. Missing qualified treatment and matched flat baseline runs, per-seed account metrics, pairing provenance and checksummed inference output. | Unassigned |
| How do separately declared random, rule, supervised or representation controls compare? | Not measured | Replay matched controls or run the registered one-dimension ablation, preserving period and trial roles. | No current secondary comparison evidence path. Missing trial family and settings, registered arms and paired seed/period identities, ledgers and any prespecified corrected inference. | Unassigned |
| How sensitive is a frozen finalist to modeled costs or missing quotes? | Not measured | Replay predefined quote and cost scenarios and reconcile fill costs and account feasibility per scenario. | No current stress result evidence path. Missing finalist checkpoint and freeze record, scenario configs, quote source, order/fill/account ledgers and checksummed stress outputs. | Unassigned |

These entries follow the [validation protocol](validation_protocol.md) and
[evaluation methodology](evaluation_methodology.md). The 2026 report
interval is exposed and remains excluded from selection and calibration.
The current local evidence does not establish an untouched evaluation period.

## Register a measured result

Record one identified question and method, frozen comparison and period
roles, resolved configuration, source state, data and cache identities, run
IDs and artifact paths with checksums. Link the supporting
[result manifest](result_identity_and_evidence.md) and use the
[reproduction levels](../reproduce/result_registry.md) for the available
verification route. A software trace or pilot remains labeled by its scope.

Preserve attempted runs and report observed breach, no-trade, invalid,
censored and incomplete outcomes with their acquisition and disposition
records. A bounded negative result requires evidence for the tested paths
and the specific criterion they failed. The current register leaves these
outcomes unassigned pending measurements.
