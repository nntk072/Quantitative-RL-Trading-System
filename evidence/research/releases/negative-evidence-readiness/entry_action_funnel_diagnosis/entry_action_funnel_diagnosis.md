# Entry action funnel diagnosis

## Scope

This report compares the frozen treatment/control training logs for the
selected single-seed policy pair. It reads only the 2025 training split.
The 2026 report split is not read. Campaign and per-arm log hashes are
recorded in the adjacent machine-readable report.

## Results

| Arm | Entry requests | Not armed | Not-armed share | Opened | Open rate | Candidates | Invalidated | Trigger requests refused |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| treatment | 47,706 | 42,126 | 88.3% | 987 | 2.07% | 1,969 | 978 | 4,593/5,785 (79.4%) |
| control | 52,282 | 47,612 | 91.1% | 825 | 1.58% | 2,412 | 1,582 | 3,845/9,172 (41.9%) |

| Arm | Cooldown | Invalid stop | Invalid reward/risk | Overnight boundary |
|---|---:|---:|---:|---:|
| treatment | 3,513 | 864 | 187 | 29 |
| control | 2,957 | 682 | 161 | 45 |

The largest recorded funnel loss is action requests made while the
entry-state machine was `FLAT` or `CANDIDATE`: 88.3% of treatment requests and 91.1% of control requests were rejected as `entry_state_not_armed`.
This is evidence of a policy/action-interface mismatch or frequent
unarmed requests, not evidence that the market supplied too few entry
candidates. Candidate invalidation and downstream SL/RR/cooldown
rejections are separate mechanisms and should remain separate in any
successor analysis.

## Claim boundary

Request and rejection counters localize action-funnel attrition. They do not establish why the policy requested entries while unarmed, prove candidate signal quality, or explain economic losses.
The counts do not support a performance claim or a causal explanation
for the losing equity path. Any action-mask or policy-interface change
would be a new experimental factor; do not apply it to the historical
checkpoint or treat this diagnosis as authorization to train.
