# Performance promotion matrix (PERFORMANCE-POLICY)

Work package: PERFORMANCE-POLICY (gate BENCH, offline part). Source of the
proposed thresholds: `planning/native_modernization/ARCHITECTURE_MODERNIZATION_PLAN.md`,
PERFORMANCE-POLICY section, Implement and Acceptance.

Machine checker: `research_tools/compute/benchmarks/performance_promotion.py`.
Command: `scripts/research/benchmarks/check_performance_promotion.py <trial_summary.json>`
prints the decision as JSON and writes nothing else.
Its typed `DEFAULT_MATRIX` is the single source of truth. The JSON block in
section 7 is checked against it by `tests/unit/research_tools/test_performance_promotion.py`.
Known-answer tests for every rule are in the same file.

## 1. Lead sign-off record

| Field | Record |
|---|---|
| Decision | ADOPTED as the initial promotion matrix (lead decision) |
| Date | 2026-11-27 |
| Scope | Candidate classes, correctness gates, metrics, thresholds, dispersion rule, Amdahl gate, regression limit and rejected-trial rule in this file |
| Reason | The plan requires promotion rules to be defined before tuning. The thresholds are planner proposals, not measured values. Each value is recorded in section 5 with its source and reason. Values marked `lead_default` have no planner number and are placeholders. |
| Owner approval | Not obtained and not claimed. |
| Measured status | No threshold is a measured fact. PERFORMANCE-BASELINE is blocked, so no baseline repeat, noise floor or stage fraction exists yet. |

Amendments follow the log in section 8. Before the first trial in a class,
a threshold may change only with a recorded reason. No amendment may relax a
correctness gate, the regression limit, or the rejected-trial rule. The plan
forbids weakening correctness (plan line 101).

## 2. Decision rules

The checker applies these rules in order. The first rule that fires decides.

1. A malformed trial summary raises an error. Malformed input is never evidence.
2. Any reported correctness gate with status `fail` rejects the trial.
3. Any required gate for the class not reported as `pass` gives `insufficient_evidence`.
   `not_run` is not evidence. `SCIENTIFIC_COMPARISON` is also required when
   `semantics_changed` is true.
4. Evidence sufficiency gives `insufficient_evidence` when any of these fails:
   at least 5 repeats per arm, relative spread at most 0.15 per arm, at least
   20 reliability attempts per arm, and a baseline `stage_fraction` for every
   primary speed measurement when the class has an Amdahl gate.
5. A regression rejects the trial. Any measurement, primary or guard, whose
   candidate/baseline median ratio breaches the 5% limit in the bad direction
   rejects it. Throughput regresses below 0.95. Time, memory and cost regress above 1.05.
6. A criterion passes when every primary measurement of that criterion meets its
   threshold. If any applicable criterion passes, the outcome is `promote`.
7. If no criterion passes and some applicable criterion has no measurement, the
   outcome is `insufficient_evidence`. A trial is decided only when every
   applicable criterion was measured.
8. If every applicable criterion was measured and none passes, the outcome is `reject`.

`promote` only makes a candidate eligible for a separately reviewed default
switch. The checker never switches a default. Its result always names the
baseline as `default_implementation`.

## 3. Dispersion rule and repeats

- Decide on medians of independent timed repeats, never on the best single run.
- Relative spread of an arm is `(max - min) / median`. Above 0.15 in either arm,
  the outcome is `insufficient_evidence`. A fast single run cannot promote a
  candidate on noisy repeats. A slow median cannot reject one either.
- Repeats must be independent runs. The plan asks for at least 5 timed repeats
  when feasible. Fewer repeats are reported as insufficient, with the count stated.
- Reliability is a success count over independent attempts per arm. The gain is
  candidate rate minus baseline rate. It needs at least 20 attempts per arm.
- Peak memory and resource cost use the same median and spread rules as speed.

## 4. Amdahl gate and end-to-end benefit

A stage speedup counts only when it projects to a material end-to-end gain:

- `f` is the baseline share of end-to-end wall time spent in the stage. It comes
  from PERFORMANCE-BASELINE.
- `s` is the measured stage median speedup.
- Projected end-to-end speedup = `1 / ((1 - f) + f / s)`.
- A stage speed criterion passes only when the projection is at least 1.05 on
  every primary workload. Otherwise the stage win is negligible end to end and
  does not promote, although a memory or reliability criterion may still promote.
- The integrated class is exempt. Its primary measurement is already end to end.

## 5. Candidate classes, gates and thresholds

Each class lists its plan packages, its required correctness gates and its
criteria. Speed is the median ratio on primary workloads. Memory, cost and
reliability are the thresholds shown. A cell marked `n/a` means the criterion
does not apply to that class.

| Class | Plan packages | Required gates | Speedup | Stretch (informational) | Memory reduction | Cost reduction | Reliability gain | Amdahl minimum |
|---|---|---|---|---|---|---|---|---|
| `feature_kernel` | FEATURE-KERNELS | `CAUSAL_PREFIX`, `FIT_SCOPE`, `ORACLE_EXACT`, `DETERMINISM` | 1.5 (planner) | n/a | 25% (planner) | n/a | 0.05 (lead_default) absolute | 1.05 (lead_default) |
| `native_environment` | NATIVE-ENVIRONMENT, NATIVE-EXECUTION, BATCHED-ENVIRONMENT | `ORACLE_EXACT`, `TAPE_REPLAY`, `BATCH_SINGLE`, `RISK_PRECISION`, `DETERMINISM` | 1.5 (planner) | 3 (planner) | 25% (planner) | n/a | 0.05 (lead_default) absolute | 1.05 (lead_default) |
| `learner_backend` | LEARNER-OPTIMIZATION, ROLLOUT-BUFFERS | `LEARNER_FIXED_BATCH`, `CHECKPOINT_COMPAT`, `RISK_PRECISION`, `DETERMINISM` | 1.5 (planner) | n/a | 25% (planner) | n/a | 0.05 (lead_default) absolute | 1.05 (lead_default) |
| `data_storage` | DATA-INGESTION, DATA-QUERY, SHARED-DATA-ABI | `ROUNDTRIP_RECONCILE`, `DETERMINISM`, `TRAIN_ONLY_WORKLOAD` | 1.5 (planner) | n/a | 25% (planner) | n/a | 0.05 (lead_default) absolute | 1.05 (lead_default) |
| `resource_runtime` | RESOURCE-RUNTIME, EXECUTION-DAG | `RESOURCE_BOUNDS`, `DETERMINISM`, `TRAIN_ONLY_WORKLOAD` | 1.5 (planner) | n/a | 25% (planner) | n/a | 0.05 (lead_default) absolute | 1.05 (lead_default) |
| `integrated_pipeline` | INTEGRATED-BENCHMARK | `ORACLE_EXACT`, `BATCH_SINGLE`, `LEARNER_FIXED_BATCH`, `CHECKPOINT_COMPAT`, `ROUNDTRIP_RECONCILE`, `RESOURCE_BOUNDS`, `RISK_PRECISION`, `DETERMINISM`, `TRAIN_ONLY_WORKLOAD` | 1.3 (planner) | n/a | n/a | 25% (planner) | 0.05 (lead_default) absolute | n/a |

### 5.1 Correctness gates

No speed, memory or reliability number counts for a trial whose required gate
is not `pass`. A reported `fail` rejects, whatever the speed.

| Gate | Definition |
|---|---|
| `ORACLE_EXACT` | Semantic-oracle parity. Integers, enums, timestamps, order, position and risk decisions are exact. Numeric fields match within a tolerance frozen per field before comparison. |
| `TAPE_REPLAY` | A fixed action tape reproduces the full event trace, including ordering keys. |
| `BATCH_SINGLE` | Batch and single outputs are equal under the same tape and seeds, and resets are independent across environments. |
| `CAUSAL_PREFIX` | Future-append and prefix invariance hold. Features at time t do not change when data after t is appended or perturbed. No incomplete higher-timeframe value is used. |
| `FIT_SCOPE` | A held-out perturbation leaves train-fitted state and normalization unchanged. |
| `ROUNDTRIP_RECONCILE` | Source and converted data reconcile row by row on counts, values, timestamps and identities. Every dropped or corrected record is explained. |
| `LEARNER_FIXED_BATCH` | Loss, gradient, mask, log-probability and value parity on a frozen batch fall within the declared tolerance. No NaN or Inf appears. |
| `CHECKPOINT_COMPAT` | A checkpoint round trip succeeds and retained checkpoints still infer. Incompatible formats are rejected, not loaded. |
| `RESOURCE_BOUNDS` | Workers and threads stay bounded. Admission refusal fixtures pass. No per-task scheduler fan-out occurs. |
| `DETERMINISM` | Repeated runs with the same seeds and inputs give identical outputs, or outputs within a declared numerical tolerance. |
| `RISK_PRECISION` | Hard-risk, account and ledger arithmetic is not reduced in precision, and fast-math is not enabled there. Risk decisions are exact. |
| `TRAIN_ONLY_WORKLOAD` | The benchmark workload uses train-only data. No locked or exposed 2026 reporting interval is read. |
| `SCIENTIFIC_COMPARISON` | Required only when semantics_changed is true. An independent scientific comparison on the registered design passed. |

### 5.2 Threshold register

Every value below is a proposed number. None is a measured fact. The `source`
column says where each value came from. `planner` means the value is stated in
the plan. `lead_default` means the plan gives no number and the value is a
placeholder to recalibrate before the first decision in the class.

| Threshold | Value | Source | Applies to | Reason |
|---|---|---|---|---|
| `min_repeats` | 5 | planner | all classes | PERFORMANCE-BASELINE asks for at least 5 independent timed repetitions when feasible. Fewer repeats cannot support a median or a dispersion bound. |
| `max_relative_spread` | 0.15 | lead_default | all classes | No measured noise floor exists because PERFORMANCE-BASELINE is blocked. Relative spread (max minus min, over the median) of 0.15 is a placeholder. Recalibrate from the first baseline repeats and record an amendment. |
| `min_reliability_attempts` | 20 | lead_default | all classes | No measured failure rate exists. 20 attempts per arm is a placeholder that prevents a success-rate gap from being decided on a handful of runs. |
| `max_regression` | 0.05 | planner | all measurements | Plan PERFORMANCE-POLICY: no unexplained regression above 5% on comparable required workloads. |
| `speedup` | 1.5 | planner | data_storage, feature_kernel, learner_backend, native_environment, resource_runtime | Plan PERFORMANCE-POLICY: target of at least 1.5x sustained improvement in the affected stage. |
| `memory_reduction` | 0.25 | planner | data_storage, feature_kernel, learner_backend, native_environment, resource_runtime | Plan PERFORMANCE-POLICY: at least 25% less peak memory is an alternative criterion. |
| `reliability_gain` | 0.05 | lead_default | data_storage, feature_kernel, integrated_pipeline, learner_backend, native_environment, resource_runtime | The plan says only 'meaningful measured reliability gain' with no number. A 5-point success-rate gain is a placeholder. No failure-rate baseline exists yet. |
| `amdahl_min_end_to_end` | 1.05 | lead_default | data_storage, feature_kernel, learner_backend, native_environment, resource_runtime | The plan says to discard complex changes with negligible end-to-end benefit but gives no number. 1.05 uses the same 5% scale as the regression limit. The projection uses Amdahl's law with the measured baseline stage fraction. |
| `stretch_speedup` | 3 | planner | native_environment | Plan PERFORMANCE-POLICY: native batch environment stretch target of at least 3x step throughput. Reported as stretch_met only. It does not gate promotion. |
| `speedup` | 1.3 | planner | integrated_pipeline | Plan PERFORMANCE-POLICY: integrated target of at least 1.3x wall-clock throughput. |
| `resource_cost_reduction` | 0.25 | planner | integrated_pipeline | Plan PERFORMANCE-POLICY: integrated alternative of at least 25% lower resource cost. |

## 6. Rejected-trial rule

- The selected implementation stays the default after any trial that does not
  promote. The checker has no write path. Its tests confirm that a rejected
  trial leaves the selected implementation tree byte-identical.
- No file of the selected implementation is edited, moved, deleted or regenerated
  because of a trial.
- Candidate code stays on its trial worktree or branch. It is not merged into
  the default path by the trial itself.
- A `reject` is recorded as `rejected_with_evidence` in the work-package ledger,
  with the trial id, the reasons, and the hash of the summary file.
- An `insufficient_evidence` outcome is not a rejection. It is recorded as
  pending or partial, and the open measurement is named.
- A rejected candidate may be retried only with a new trial id and a recorded
  reason. The thresholds and gates are not changed to rescue the rejected trial.

## 7. Machine-readable matrix

This block is the typed `DEFAULT_MATRIX` serialized by `matrix_to_jsonable`.
The test `test_markdown_matrix_block_equals_the_typed_matrix` compares it with
the constants. Edit the constants first, then regenerate this block.

```json
{
  "schema_version": 1,
  "min_repeats": {
    "value": 5.0,
    "source": "planner",
    "reason": "PERFORMANCE-BASELINE asks for at least 5 independent timed repetitions when feasible. Fewer repeats cannot support a median or a dispersion bound."
  },
  "max_relative_spread": {
    "value": 0.15,
    "source": "lead_default",
    "reason": "No measured noise floor exists because PERFORMANCE-BASELINE is blocked. Relative spread (max minus min, over the median) of 0.15 is a placeholder. Recalibrate from the first baseline repeats and record an amendment."
  },
  "min_reliability_attempts": {
    "value": 20.0,
    "source": "lead_default",
    "reason": "No measured failure rate exists. 20 attempts per arm is a placeholder that prevents a success-rate gap from being decided on a handful of runs."
  },
  "max_regression": {
    "value": 0.05,
    "source": "planner",
    "reason": "Plan PERFORMANCE-POLICY: no unexplained regression above 5% on comparable required workloads."
  },
  "scientific_gate": "SCIENTIFIC_COMPARISON",
  "gates": {
    "ORACLE_EXACT": "Semantic-oracle parity. Integers, enums, timestamps, order, position and risk decisions are exact. Numeric fields match within a tolerance frozen per field before comparison.",
    "TAPE_REPLAY": "A fixed action tape reproduces the full event trace, including ordering keys.",
    "BATCH_SINGLE": "Batch and single outputs are equal under the same tape and seeds, and resets are independent across environments.",
    "CAUSAL_PREFIX": "Future-append and prefix invariance hold. Features at time t do not change when data after t is appended or perturbed. No incomplete higher-timeframe value is used.",
    "FIT_SCOPE": "A held-out perturbation leaves train-fitted state and normalization unchanged.",
    "ROUNDTRIP_RECONCILE": "Source and converted data reconcile row by row on counts, values, timestamps and identities. Every dropped or corrected record is explained.",
    "LEARNER_FIXED_BATCH": "Loss, gradient, mask, log-probability and value parity on a frozen batch fall within the declared tolerance. No NaN or Inf appears.",
    "CHECKPOINT_COMPAT": "A checkpoint round trip succeeds and retained checkpoints still infer. Incompatible formats are rejected, not loaded.",
    "RESOURCE_BOUNDS": "Workers and threads stay bounded. Admission refusal fixtures pass. No per-task scheduler fan-out occurs.",
    "DETERMINISM": "Repeated runs with the same seeds and inputs give identical outputs, or outputs within a declared numerical tolerance.",
    "RISK_PRECISION": "Hard-risk, account and ledger arithmetic is not reduced in precision, and fast-math is not enabled there. Risk decisions are exact.",
    "TRAIN_ONLY_WORKLOAD": "The benchmark workload uses train-only data. No locked or exposed 2026 reporting interval is read.",
    "SCIENTIFIC_COMPARISON": "Required only when semantics_changed is true. An independent scientific comparison on the registered design passed."
  },
  "classes": {
    "feature_kernel": {
      "plan_packages": [
        "FEATURE-KERNELS"
      ],
      "required_gates": [
        "CAUSAL_PREFIX",
        "FIT_SCOPE",
        "ORACLE_EXACT",
        "DETERMINISM"
      ],
      "speedup": {
        "value": 1.5,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: target of at least 1.5x sustained improvement in the affected stage."
      },
      "stretch_speedup": null,
      "memory_reduction": {
        "value": 0.25,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: at least 25% less peak memory is an alternative criterion."
      },
      "resource_cost_reduction": null,
      "reliability_gain": {
        "value": 0.05,
        "source": "lead_default",
        "reason": "The plan says only 'meaningful measured reliability gain' with no number. A 5-point success-rate gain is a placeholder. No failure-rate baseline exists yet."
      },
      "amdahl_min_end_to_end": {
        "value": 1.05,
        "source": "lead_default",
        "reason": "The plan says to discard complex changes with negligible end-to-end benefit but gives no number. 1.05 uses the same 5% scale as the regression limit. The projection uses Amdahl's law with the measured baseline stage fraction."
      }
    },
    "native_environment": {
      "plan_packages": [
        "NATIVE-ENVIRONMENT",
        "NATIVE-EXECUTION",
        "BATCHED-ENVIRONMENT"
      ],
      "required_gates": [
        "ORACLE_EXACT",
        "TAPE_REPLAY",
        "BATCH_SINGLE",
        "RISK_PRECISION",
        "DETERMINISM"
      ],
      "speedup": {
        "value": 1.5,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: target of at least 1.5x sustained improvement in the affected stage."
      },
      "stretch_speedup": {
        "value": 3.0,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: native batch environment stretch target of at least 3x step throughput. Reported as stretch_met only. It does not gate promotion."
      },
      "memory_reduction": {
        "value": 0.25,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: at least 25% less peak memory is an alternative criterion."
      },
      "resource_cost_reduction": null,
      "reliability_gain": {
        "value": 0.05,
        "source": "lead_default",
        "reason": "The plan says only 'meaningful measured reliability gain' with no number. A 5-point success-rate gain is a placeholder. No failure-rate baseline exists yet."
      },
      "amdahl_min_end_to_end": {
        "value": 1.05,
        "source": "lead_default",
        "reason": "The plan says to discard complex changes with negligible end-to-end benefit but gives no number. 1.05 uses the same 5% scale as the regression limit. The projection uses Amdahl's law with the measured baseline stage fraction."
      }
    },
    "learner_backend": {
      "plan_packages": [
        "LEARNER-OPTIMIZATION",
        "ROLLOUT-BUFFERS"
      ],
      "required_gates": [
        "LEARNER_FIXED_BATCH",
        "CHECKPOINT_COMPAT",
        "RISK_PRECISION",
        "DETERMINISM"
      ],
      "speedup": {
        "value": 1.5,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: target of at least 1.5x sustained improvement in the affected stage."
      },
      "stretch_speedup": null,
      "memory_reduction": {
        "value": 0.25,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: at least 25% less peak memory is an alternative criterion."
      },
      "resource_cost_reduction": null,
      "reliability_gain": {
        "value": 0.05,
        "source": "lead_default",
        "reason": "The plan says only 'meaningful measured reliability gain' with no number. A 5-point success-rate gain is a placeholder. No failure-rate baseline exists yet."
      },
      "amdahl_min_end_to_end": {
        "value": 1.05,
        "source": "lead_default",
        "reason": "The plan says to discard complex changes with negligible end-to-end benefit but gives no number. 1.05 uses the same 5% scale as the regression limit. The projection uses Amdahl's law with the measured baseline stage fraction."
      }
    },
    "data_storage": {
      "plan_packages": [
        "DATA-INGESTION",
        "DATA-QUERY",
        "SHARED-DATA-ABI"
      ],
      "required_gates": [
        "ROUNDTRIP_RECONCILE",
        "DETERMINISM",
        "TRAIN_ONLY_WORKLOAD"
      ],
      "speedup": {
        "value": 1.5,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: target of at least 1.5x sustained improvement in the affected stage."
      },
      "stretch_speedup": null,
      "memory_reduction": {
        "value": 0.25,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: at least 25% less peak memory is an alternative criterion."
      },
      "resource_cost_reduction": null,
      "reliability_gain": {
        "value": 0.05,
        "source": "lead_default",
        "reason": "The plan says only 'meaningful measured reliability gain' with no number. A 5-point success-rate gain is a placeholder. No failure-rate baseline exists yet."
      },
      "amdahl_min_end_to_end": {
        "value": 1.05,
        "source": "lead_default",
        "reason": "The plan says to discard complex changes with negligible end-to-end benefit but gives no number. 1.05 uses the same 5% scale as the regression limit. The projection uses Amdahl's law with the measured baseline stage fraction."
      }
    },
    "resource_runtime": {
      "plan_packages": [
        "RESOURCE-RUNTIME",
        "EXECUTION-DAG"
      ],
      "required_gates": [
        "RESOURCE_BOUNDS",
        "DETERMINISM",
        "TRAIN_ONLY_WORKLOAD"
      ],
      "speedup": {
        "value": 1.5,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: target of at least 1.5x sustained improvement in the affected stage."
      },
      "stretch_speedup": null,
      "memory_reduction": {
        "value": 0.25,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: at least 25% less peak memory is an alternative criterion."
      },
      "resource_cost_reduction": null,
      "reliability_gain": {
        "value": 0.05,
        "source": "lead_default",
        "reason": "The plan says only 'meaningful measured reliability gain' with no number. A 5-point success-rate gain is a placeholder. No failure-rate baseline exists yet."
      },
      "amdahl_min_end_to_end": {
        "value": 1.05,
        "source": "lead_default",
        "reason": "The plan says to discard complex changes with negligible end-to-end benefit but gives no number. 1.05 uses the same 5% scale as the regression limit. The projection uses Amdahl's law with the measured baseline stage fraction."
      }
    },
    "integrated_pipeline": {
      "plan_packages": [
        "INTEGRATED-BENCHMARK"
      ],
      "required_gates": [
        "ORACLE_EXACT",
        "BATCH_SINGLE",
        "LEARNER_FIXED_BATCH",
        "CHECKPOINT_COMPAT",
        "ROUNDTRIP_RECONCILE",
        "RESOURCE_BOUNDS",
        "RISK_PRECISION",
        "DETERMINISM",
        "TRAIN_ONLY_WORKLOAD"
      ],
      "speedup": {
        "value": 1.3,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: integrated target of at least 1.3x wall-clock throughput."
      },
      "stretch_speedup": null,
      "memory_reduction": null,
      "resource_cost_reduction": {
        "value": 0.25,
        "source": "planner",
        "reason": "Plan PERFORMANCE-POLICY: integrated alternative of at least 25% lower resource cost."
      },
      "reliability_gain": {
        "value": 0.05,
        "source": "lead_default",
        "reason": "The plan says only 'meaningful measured reliability gain' with no number. A 5-point success-rate gain is a placeholder. No failure-rate baseline exists yet."
      },
      "amdahl_min_end_to_end": null
    }
  }
}
```

## 8. Amendment log

| ID | Date | Change | Reason |
|---|---|---|---|
| A0 | 2026-11-27 | Initial matrix adopted from the plan's proposed values, with `lead_default` placeholders where the plan gave no number. | The plan requires promotion rules before tuning. No measurement exists to calibrate them. |

## 9. Scope limits

- No candidate is required to reach any numeric speed. A class with no passing
  criterion is rejected, not forced to pass. The final report states results
  with dispersion, and a rejected candidate is a valid outcome.
- This matrix does not claim any speedup, profitability or broker equivalence.
- Measurements are not performed here. Section 10 names what each class needs.

## 10. Open measurements (not performed by this stream)

Each open item needs a measurement before a class can be decided. The ledger
entry `planning/native_modernization/ledger_entries/PERFORMANCE-POLICY.json`
gives the exact reason and allocation for each item.

- M1: calibrate `max_relative_spread`, `min_reliability_attempts` and the
  reliability gain from baseline repeats. Needs PERFORMANCE-BASELINE repeats.
- M2: measure the baseline stage fractions `f` for the Amdahl gate. Needs
  PERFORMANCE-BASELINE profiles on the frozen train-only workload.
- M3: decide each candidate class on repeated candidate and baseline
  measurements on the same allocation. Needs the candidate to exist and a named
  allocation for each class.
