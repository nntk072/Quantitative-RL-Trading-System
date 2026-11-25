> **Current operating boundary (2026-11-21).** This is the sole active campaign plan. The canonical checkout is `/scratch/work/nguyenl37/Quantitative-RL-Trading-System`. Keep plans, agent logs, evidence, outputs, and recycle material inside that repository; role-owned agent logs belong under `logs/agents/<role_name>/`. Use `outputs/maintenance/recycle_bin/` for in-repository recycling. Bounded parallel reviews for the 2026-11-18 readiness plan have been user-authorized; keep independent work lanes and their evidence traceable. Preserve existing dirty work and Slurm jobs. Do not commit or push without explicit authorization.

# Canonical Quant Repository Cleanup, Refactor, and Thesis Research Campaign

## Mission

Turn the current Quant project into one coherent workspace with:

1. one canonical repository;
2. one active master plan;
3. consolidated valid historical evidence;
4. no scattered Quant-related working directories, stale scripts, finished plans, duplicate repositories, or unexplained external symlink targets;
5. a clean reusable research architecture;
6. one subsequently executed thesis research campaign;
7. a reproducible final thesis evidence package.

The execution order is strictly:

```text
Filesystem / disk investigation
        ↓
Filesystem cleanup and consolidation
        ↓
Plan + historical evidence investigation
        ↓
Plan/evidence cleanup and consolidation
        ↓
Repository foundation refactor
        ↓
Full thesis research campaign
        ↓
Thesis synthesis and final QA
```

Do not begin the definitive experimental campaign before the cleanup and repository-foundation stages are complete.

---

## PART 0 — SAFETY AND CANONICAL LOCATIONS

### Canonical repository

There must ultimately be exactly one active Quant repository:

```text
/scratch/work/nguyenl37/Quantitative-RL-Trading-System
```

No other Quant checkout should remain active after consolidation.

In particular:

```text
/scratch/work/nguyenl37/Quantitative-RL-Trading-System/outputs/historical/external_archive_snapshot_20261114
```

must be investigated for unique valid evidence or source material and then removed from active use.

If its useful contents are preserved elsewhere, move the repository directory itself to:

```text
outputs/maintenance/recycle_bin/repositories/
```

Do not leave a second quasi-authoritative Quant repository.

### Recycle root

Use:

```text
outputs/maintenance/recycle_bin/
```

with purpose-based subdirectories such as:

```text
outputs/maintenance/recycle_bin/
    plans/
    repositories/
    invalid_evidence/
    superseded_outputs/
    obsolete_scripts/
    obsolete_logs/
    duplicate_files/
    caches/
    temporary/
```

The recycle bin is not a second research archive.

Items placed there are considered non-authoritative.

### One-project rule

After cleanup, anything actively used by the Quant project should live underneath:

```text
/scratch/work/nguyenl37/Quantitative-RL-Trading-System/
```

This includes project-specific:

- outputs;
- experiment logs;
- campaign manifests;
- evidence;
- helper scripts that remain useful;
- current thesis source/handoff if the project needs it;
- project-specific caches where relocation is technically appropriate;
- current active plan/documentation.

Shared system infrastructure need not be moved merely for aesthetic reasons.

For example, do not move an unrelated system/tool cache if it is genuinely shared by other projects.

---

## PART 1 — DISK AND FILESYSTEM INVESTIGATION

### 1.1 Inventory before mutation

The initial completely read-only inventory of:

```text
/scratch/work/nguyenl37
```

has already been recorded under
`logs/agents/architect/20261114_canonical_cleanup_inventory/`. Treat it as the
baseline, not as current state. Refresh the in-repository inventory after each
completed migration and record current ownership, active use, and disposition
under `outputs/maintenance/storage_inventory/`. Do not create or move project
working files outside the canonical checkout.

For each still-unresolved Quant-related item, record:

```text
path
type
size
mtime
owner
symlink status
symlink target
git repository status
source SHA if repository
file count
relationship to Quant
relationship to thesis
known campaign/run identity
active process/job reference
recommended disposition
```

Write the inventory under the canonical repository, for example:

```text
outputs/maintenance/storage_inventory/
```

or another appropriate ignored maintenance location.

Do not begin moving files until the inventory is complete.

---

## 1.2 Explicitly exclude unrelated projects

The cleanup concerns Quant/thesis material.

Directories such as unrelated communications/medical/computer-vision projects must not be moved simply because they appear in the same home directory.

Examples from the current listing that require classification before any action include:

```text
5g-nr-channel-condition
cxr-frontal-lateral-conversion
home-data
```

If they are unrelated, leave them untouched.

---

## 1.3 Resolve every Quant-related symlink

Some current outputs are symlinks whose bytes live outside the repository.

Enumerate all symlinks related to the Quant project:

```bash
find /scratch/work/nguyenl37/Quantitative-RL-Trading-System \
  -type l -print
```

For every symlink record:

```text
link path
raw target
resolved target
target existence
target size
target filesystem
referencing manifests/configs
scientific role
```

Also inspect external directories that may contain symlinks pointing back into the repository.

Detect:

- broken links;
- links to old campaign roots;
- links to duplicate repositories;
- links to temporary directories;
- multiple links to the same bytes.

---

## 1.4 Detect active use before moving anything

Before moving any directory, determine whether it is referenced by:

```text
running Slurm jobs
pending jobs
tmux sessions
shell processes
Python processes
current working directories
open files
campaign supervisors
active symlinks
current manifests
```

An active path must not be relocated underneath a running process.

If necessary, defer its move until the corresponding job completes.

Do not cancel useful jobs merely to make cleanup easier.

---

## 1.5 Hash and deduplicate

For candidate duplicate material, compare:

```text
size
SHA-256
directory manifests
source SHA
config identity
```

Do not infer duplicates from similar filenames such as:

```text
uv-cache
uv_cache

apptainer-cache
apptainer_cache

*.log
*_final.log
*_final2.log
```

Determine whether the bytes actually differ.

---

## PART 2 — DISK CLEANUP AND CONSOLIDATION

### 2.1 Canonical categories inside the repo

Use existing repository conventions wherever possible.

Active material should converge toward categories such as:

```text
Quantitative-RL-Trading-System/
    evidence/
        research/
    outputs/
        runs/
        logs/
        historical/
        maintenance/
    config/
    scripts/
    tools/
    docs/
```

Do not create dozens of new top-level directories.

Large ignored run artifacts can remain gitignored while physically residing inside the repository.

---

## 2.2 Repository duplicates

Investigate:

```text
Quantitative-RL-Trading-System-research-archive
```

before moving it.

Compare against current main:

```text
Git history
commits
tracked files
untracked files
ignored files
evidence directories
outputs
research manifests
configs
scripts
documentation
```

Extract only genuinely unique useful material.

For every extracted artifact record:

```text
old path
new canonical path
SHA-256
reason retained
scientific status
source identity
```

Then move the old repository itself to:

```text
outputs/maintenance/recycle_bin/repositories/
```

There must not remain two authoritative Quant checkouts.

---

## 2.3 Root-level experiment/campaign directories

Investigate directories such as:

```text
luna6_campaigns
mtf_cd_benchmark_20261027
gh200_max_fps_arch_redesign_20261028
ci-public-api-audit-c56d3231750ba91c
devonly-audit-f5a37a8083d2
goal-snapshots
```

For each campaign determine:

```text
source SHA
protocol
configuration
data/cache identity
seed/arm
completion status
artifact hashes
scientific role
whether results were exposed
whether later bugs invalidate interpretation
whether unique evidence exists
```

Then classify it using the evidence rules below.

---

## 2.4 Root-level logs

The home directory contains many project-specific logs, for example:

```text
mtf-*.log
thesis-mtf-*.log
variant-d-*.log
entryidea_*.log
phase0-*.log
phase1_*.log
quant-ci-*.log
cigate*.log
training-smoke-*.log
```

Do not retain hundreds of disconnected root-level logs.

For each logical execution:

1. identify authoritative final log(s);
2. associate them with source SHA and task;
3. retain logs that establish useful provenance;
4. consolidate them under the relevant evidence/run directory;
5. move superseded/intermediate logs to `outputs/maintenance/recycle_bin/obsolete_logs`;
6. delete byte-identical disposable duplicates only after manifesting them.

A suffix such as:

```text
final
final2
retry
gate2
release
verified
```

is not itself proof of authority.

Determine authority from content and source identity.

---

## 2.5 One-off scripts

Investigate files such as:

```text
phase0_*.py
phase1_*.sh
inspect_*.py
debug_*.py
run_mtf_*.sh
thesis_mtf_*.py
wp01_remote_edits.py
prebuild_*.py
verify_p7_tick_cost_stress_20261022.py
```

Classify each as:

### Reusable project capability

Move/refactor into the proper package or:

```text
scripts/
tools/
```

with tests/documentation.

### Historical reproducibility helper

Preserve with the associated historical evidence if needed to rebuild that evidence.

### One-time completed helper

Move to:

```text
outputs/maintenance/recycle_bin/obsolete_scripts/
```

### Broken/unnecessary duplicate

Recycle and later delete if safely redundant.

No unexplained executable Quant scripts should remain in the canonical repository root; shared environment tools are classified separately.

---

## 2.6 Caches and environments

Investigate:

```text
apptainer-cache
apptainer_cache
apptainer_tmp

uv-cache
uv_cache
uv_tools
uv-aarch64

__pycache__
tmp
```

Also inventory:

```text
.venv*
```

Do not move/delete a virtual environment currently used by a job.

For project-specific caches:

- retain one canonical active cache when useful;
- remove duplicate cache trees after verifying active references;
- relocate project-local caches underneath the canonical workspace when technically safe;
- keep architecture-specific environments clearly named.

`__pycache__`, stale temp directories, byte-identical duplicate caches and reproducible download caches are disposable once confirmed unused.

Caches are not research evidence.

---

## 2.7 Current thesis/project documents

Investigate root documents such as:

```text
Agent_Implementation_Plan.md
ZERO_TRADE_PREVENTION_AGENT_PLAN.md
Idea 1_2.md
Idea 1_2.md.backup_2026-10-13
Idea_1_2_revised.md
Thesis_Alignment_PO3_IFVG.md
Thesis_Defense_PO3_IFVG.pdf
training_agent_prompt.txt
```

Determine whether each is:

```text
current thesis input
historical reasoning
completed plan
superseded draft
duplicate
unrelated
```

Current authoritative thesis source should have exactly one canonical location.

Superseded drafts should not remain mixed with active source.

---

## PART 3 — HISTORICAL EVIDENCE VALIDITY AUDIT

Historical evidence must be **filtered**, not simply accumulated.

Use three validity classes.

### 3.1 Class A — current scientifically usable evidence

An artifact may support current thesis findings only if its relevant identity can be reconstructed:

```text
source code identity
resolved configuration
data/cache identity
period role
seed
model/checkpoint identity
simulator/risk semantics
metric definition
artifact integrity
selection history
```

and no known subsequent bug invalidates the result.

Class A evidence is consolidated into the canonical repository and indexed as current usable evidence.

---

## 3.2 Class B — valid historical/diagnostic evidence

Some evidence remains historically valid but cannot support the present thesis claim.

Examples:

```text
exploratory exposed-period result
old performance benchmark
old simulator semantics
historical CI result
capacity benchmark
debugging result
withdrawn model-selection run
```

If it still documents a real historical event and has trustworthy provenance, preserve it.

Consolidate it under clearly historical evidence.

It must be labeled:

```text
historical
diagnostic
exploratory
withdrawn from current claim
```

Do not leave it fragmented merely because it cannot support final inference.

---

## 3.3 Class C — invalid / irrecoverable / useless

Move to:

```text
outputs/maintenance/recycle_bin/invalid_evidence/
```

when one or more of the following apply materially:

```text
unknown source identity
unknown config
unknown data identity
artifact corruption
contradictory unrecoverable provenance
known implementation bug invalidates result
essential output missing
duplicate with no additional provenance
temporary partial output superseded by complete authoritative output
failed/debug output with no remaining diagnostic value
```

Do not let Class C artifacts remain in the current evidence index.

---

## 3.4 Scientific validity differs from technical existence

A result does not become current scientific evidence merely because:

```text
the file exists
the run completed
the test passed
the model trained
the plot looks useful
```

Evaluate its scientific role.

Likewise, an old result need not be destroyed merely because it cannot support current claims.

It may still be valid historical evidence.

---

## PART 4 — EVIDENCE CONSOLIDATION

### 4.1 One historical evidence index

Create one machine-readable evidence register.

For each retained historical artifact include:

```text
evidence_id
campaign/study
old path
canonical path
source SHA
config identity
data identity
period role
seed/model/arm
artifact SHA-256
validity class
scientific usability
invalidation/scope note
related artifacts
```

Use stable semantic identifiers rather than filesystem chronology.

---

## 4.2 Consolidate fragmented campaigns

Where one campaign currently has:

```text
several directories
root-level logs
standalone JSON
standalone shell scripts
separate reports
symlinked output
```

bring the retained material together into one coherent campaign/evidence location.

Do not copy the same artifact to several locations.

Prefer:

```text
manifest
→ source artifacts
→ results
→ reports
```

with references rather than duplication.

---

## 4.3 Preserve hashes during migration

For every moved retained artifact:

```text
hash before
move
hash after
```

must agree.

Record the old-to-new mapping.

Do not silently alter historical evidence while "cleaning" it.

---

## 4.4 Repair references

After consolidation search for references to old paths in:

```text
YAML
JSON
Markdown
Python
shell scripts
manifests
symlinks
```

Update active references.

Historical manifests that intentionally record their old absolute path should not be falsified.

Instead add migration metadata or a mapping layer.

---

## PART 5 — PLAN INVESTIGATION

Only after storage/evidence inventory is understood should plans be cleaned.

Inventory:

```text
logs/agents/architect/plan_corpus_20261114/
logs/agents/architect/plan_corpus_20261114/root_plan_documents/Agent_Implementation_Plan.md
logs/agents/architect/plan_corpus_20261114/root_plan_documents/ZERO_TRADE_PREVENTION_AGENT_PLAN.md
```

plus plan-like Markdown/configs inside and outside the repository.

Also include:

```text
docs/operations/research_execution_plan.md
config/research/v3_full_todo_catalog.yaml
config/research/v3_remaining_execution.yaml
```

and any other file functioning as a task queue or campaign plan.

---

## 5.1 Build a plan lineage

For every plan identify:

```text
created date
supersedes
superseded by
source state
objective
completed tasks
uncompleted tasks
still-valid requirements
obsolete assumptions
scientific constraints
```

This prevents losing an unfinished requirement simply because its plan is old.

---

## 5.2 Finished plans

A plan is finished when:

```text
every actionable item was completed
or
its remaining items were explicitly superseded by a later plan
```

Move finished plans to:

```text
outputs/maintenance/recycle_bin/plans/
```

They do not remain active project instructions.

---

## 5.3 Superseded incomplete plans

Before recycling a superseded plan:

1. extract any still-valid unfinished requirement;
2. place that requirement into the new canonical master plan;
3. record which old plan it came from;
4. then recycle the old plan.

Never require future agents to read five historical plans to understand current work.

---

## 5.4 Delete unnecessary plan duplicates

Within `outputs/maintenance/recycle_bin/plans`, exact duplicates, auto-generated copies, backups whose contents are fully represented elsewhere, and clearly useless partial scratch plans may be deleted after:

```text
hash comparison
content comparison
dependency/reference check
```

The recycle bin should not become another uncontrolled archive.

Keep only enough old planning context to reconstruct important decisions.

---

## PART 6 — ONE CANONICAL ACTIVE PLAN

After plan consolidation there should be only one active master plan.

Its order is:

```text
A. storage cleanup complete
B. historical evidence consolidation complete
C. plan consolidation complete
D. repository foundation refactor
E. thesis research campaign
F. manuscript integration
G. final QA
```

Do not maintain parallel "V3", "V66", "Luna", "final", "new final", etc. active plans.

Historical labels may remain in historical evidence.

The active plan uses semantic names.

---

## PART 7 — CLEAN WORKSPACE ACCEPTANCE GATE

Before repository refactoring starts, require all of the following:

- exactly one active Quant repository;
- no second Quant research archive repository;
- no unexplained Quant-related root-level scripts;
- no unexplained Quant-related root-level logs;
- no active external Quant output symlink whose target has not been classified;
- current project outputs physically consolidated into the canonical workspace where feasible;
- all preserved evidence classified A or B;
- Class C evidence moved to recycle bin;
- completed plans moved to `outputs/maintenance/recycle_bin/plans`;
- one active plan;
- no active job broken by path migration;
- old→new path migration manifest complete;
- retained artifact hashes verified;
- `git status` understood;
- disk usage measured before and after cleanup.

Create a cleanup report containing:

```text
disk usage before
disk usage after
files moved
files consolidated
duplicates removed
caches removed
repositories retired
plans retired
valid evidence retained
invalid evidence recycled
unresolved items
```

If unresolved filesystem ambiguity can affect research provenance, resolve it before continuing.

---

## PART 8 — INTEGRATED REPOSITORY REFACTOR

After workspace cleanup, begin the repository foundation work.

Start only from latest `origin/main`.

Do not use the historical `chatgpt/final-research-cleanup` implementation as design input.

The objectives remain:

### Research architecture

Introduce reusable:

```text
experiment
component
variant
assembly
execution graph
result artifact
```

instead of experiment-specific duplicate runners.

### Purpose-based naming

Remove active architectural dependence on historical names such as:

```text
v3_*
phase1
phase2
part1
final2
```

where they represent current functionality rather than compatibility schemas.

### Unified result data

Normalize:

```text
source_commit
configuration_hash
data_identity
experiment
assembly
component
variant
seed
fold
run
command
execution_status
scientific_status
artifact
artifact_sha256
metric
value
```

### Explicit result artifacts

Do not guess the main result from filenames when the producer can declare it.

### DAG validation

Reject:

```text
unknown dependencies
self dependencies
cycles
incompatible assemblies
artifact collisions
```

### Reproducibility

Support:

```text
freeze
execute
resume
retry reviewed failure
hash verification
result consolidation
```

### B/C and A contracts

Make:

```text
B/C equality
A HTF isolation
```

machine-verifiable before training.

### 18-arm generation

Represent the:

```text
3 information contexts × G0–G5
```

screen through factors/configuration rather than 18 duplicated code paths.

### Preserve customer agent infrastructure

Maintain coherent:

```text
AGENTS.md
.agents/
.codex/
.claude/
```

but remove stale campaign-specific process instructions.

---

## PART 9 — REPOSITORY-WIDE VALIDATION

After refactor:

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy .
```

Run relevant behavioral tests during implementation.

The pretraining readiness runner must write to a fresh, Git-ignored leaf under
`outputs/pre_experiment_readiness/<RUN_ID>/execution/<attempt-id>`. Reject
outside paths, source-tree paths, existing targets, and symlink escapes. Runner
completion is implementation evidence only and never authorizes training.

Regenerate generated documentation.

Then execute:

```bash
./tools/check full
```

Verify the complete semantic CI surface:

```text
dependencies
security
quality
documentation
architecture
graph quality
contracts
unit
build
integration
coverage
parity
training smoke
```

Run an independent diff review.

No definitive research campaign begins before this is green.

---

## PART 10 — RESEARCH PROTOCOL RECONCILIATION

Now inspect the latest thesis PDF and LaTeX source.

The earlier integrated V3/v66 campaign remains the scientific starting point, but reconcile it against the actual latest manuscript.

Freeze a crosswalk:

```text
thesis claim
research question
experiment
metric
required evidence
table
figure
status
```

Keep distinct:

### Q0

```text
survival + value vs always-no-trade
```

### Primary representation question

```text
C − B
```

Do not silently replace one with the other.

---

## PART 11 — RESEARCH GATES

Run the scientific campaign in this order.

### Gate 0

Freeze:

```text
source
protocol
periods
A/B/C/D
18-arm factors
seeds
outcomes
invalidity rules
statistics
artifact schemas
```

### Gate I

Data and quote readiness.

### Gate II

Causal features, candidate identity, B/C equality, A isolation.

### Gate III

Simulator/account/risk/quote correctness.

### Gate IV

Policy/action/reward/training/measurement readiness.

### Gate V

End-to-end result/report pipeline and measured Triton capacity.

No expensive definitive training before Gates I–V pass.

---

## PART 12 — 18-ARM CONTROLS SCREEN

Freeze:

```text
3 contexts × 6 control rungs
```

before outcomes.

If capacity supports the registered design:

```text
3 contexts
× 6 rungs
× 3 seeds
= 54 fits
```

at the declared aggregate budget.

If it does not fit, register a bounded pilot before looking at performance.

Do not promote a one-seed pilot winner into confirmatory evidence.

---

## PART 13 — COMMON CONTROL FREEZE

Use development-only screen evidence to freeze:

```text
action interface
reward
risk
execution
control capability
training budget
checkpoint rule
architecture policy
```

for the main A/B/C/D comparison.

If no scientifically acceptable common configuration exists, issue a no-go.

---

## PART 14 — A/B/C/D MAIN STUDY

Use:

```text
A
B
C
D
```

with independent seeds:

```text
42
43
44
45
46
47
```

Base design:

```text
4 × 6 = 24 independent fits
```

Do not treat folds as independent seeds.

---

## PART 15 — CHRONOLOGICAL VALIDATION

Audit the planned:

```text
5 folds
60-bar purge
20-bar embargo
20% test fraction
```

against actual:

```text
maximum feature history
HTF lookback
candidate lifetime
order lifetime
label horizon
outcome horizon
```

before freezing.

Change these values only before outcomes and only when scientifically justified.

---

## PART 16 — PRIMARY INFERENCE

### Survival

A policy with any required hard breach fails survival qualification.

### Q0

Among qualified policies, compare economic value with always-no-trade.

### C − B

Primary thesis representation effect.

Pair by seed and matched evaluation cohort.

Report:

```text
per-seed effect
mean
median
dispersion
interval
registered paired statistical test
```

Do not choose test direction after seeing outcomes.

---

## PART 17 — SECONDARY INFERENCE

Evaluate:

```text
B − A
C − A
D − C
```

under frozen multiplicity and interpretation rules.

Do not call D−C geometry-only if other design factors changed.

---

## PART 18 — BASELINES AND ROBUSTNESS

Use appropriately matched:

```text
always-no-trade
random eligible
structure-priority rule
simple technical rule
```

where scientifically valid.

After finalist freeze test:

```text
account rule variants
spread
slippage
costs
quote availability
gap behavior
mask validity
candidate censoring
capacity/parameter sensitivity
no-trade collapse
```

Do not select models using robustness results.

---

## PART 19 — CONSOLIDATED RESEARCH DATASET

All research outputs flow into one normalized result dataset.

Do not return to fragmented directories as the analytical interface.

Preserve:

```text
positive
negative
null
breach
no-trade
invalid
incomplete
```

with distinct statuses.

Invalid runs must have explicit invalidity reasons.

---

## PART 20 — RESULTS AND DISCUSSION

Generate reproducible Markdown covering:

```text
Data
Environment
Agents / RL / controls
Selected models / trading
```

or the corresponding sections in the latest thesis.

Every table and figure derives from source-hashed evidence.

Avoid dozens of redundant plots.

---

## PART 21 — THESIS INTEGRATION

After evidence stabilizes:

1. update latest LaTeX source;
2. replace TBDs only with measured evidence;
3. update Results;
4. update Discussion;
5. update Limitations;
6. update Methods where the final protocol changed;
7. compile PDF;
8. inspect PDF visually;
9. extract PDF text;
10. search for unresolved placeholders and internal engineering text.

Do not place:

```text
source SHAs
filesystem paths
agent instructions
Slurm commands
internal code symbols
```

in committee-facing prose.

---

## PART 22 — FINAL INDEPENDENT QA

Independent reviewer checks:

```text
claim → evidence
table → data
figure → data
statistical claim → protocol
C−B interpretation
Q0 separation
breach retention
2026 exposure handling
negative result retention
artifact reproducibility
PDF consistency
```

Resolve material findings.

---

## PART 23 — TERMINAL OUTCOMES

Use exactly one final research disposition.

### Evidence-complete thesis package

The required scientific claims are supported by measured, reproducible evidence and the final PDF passes QA.

or

### Evidence-preserving no-go / deferred thesis

A scientific gate failed or necessary evidence could not validly be produced.

State:

```text
failed gate
tested hypothesis
evidence
root cause
scientific consequence
what remains valid
smallest valid next step
```

Never manufacture a positive conclusion merely to finish the thesis.

---

## FINAL MASTER DEPENDENCY CHAIN

```text
Use the refreshed in-repository workspace inventory under `outputs/maintenance/storage_inventory/`; the initial cross-root inventory is preserved under `logs/agents/architect/20261114_canonical_cleanup_inventory/`.
        ↓
Map Quant-related files, repos, symlinks, outputs, jobs
        ↓
Hash + classify filesystem content
        ↓
Filter historical evidence
        ↓
Consolidate valid evidence into canonical repo
        ↓
Move invalid/superseded material to `outputs/maintenance/recycle_bin/`
        ↓
Retire duplicate Quant repository
        ↓
Clean root logs/scripts/caches
        ↓
Inventory all plans
        ↓
Extract unfinished valid requirements
        ↓
Move completed/superseded plans to outputs/maintenance/recycle_bin/plans
        ↓
Establish ONE active master plan
        ↓
Filesystem/workspace acceptance gate
        ↓
Latest main
        ↓
Repository-wide architectural refactor
        ↓
Reusable experiments/components/variants/assemblies
        ↓
Unified execution/provenance/results
        ↓
B/C equality + A isolation contracts
        ↓
Full repo tests + ./tools/check full
        ↓
Clean research source identity
        ↓
Latest thesis PDF/LaTeX reconciliation
        ↓
Freeze research protocols
        ↓
Gate I — data / quotes
        ↓
Gate II — features / causality / opportunity matching
        ↓
Gate III — simulator / account / risk
        ↓
Gate IV — policy / controls / diagnostics
        ↓
Gate V — result pipeline / capacity
        ↓
18-arm controls screen
        ↓
Common-control freeze
        ↓
A/B/C/D × six seeds
        ↓
Walk-forward validation
        ↓
Q0 + C−B + secondary inference
        ↓
Robustness
        ↓
Consolidated result dataset
        ↓
Results + Discussion
        ↓
LaTeX integration
        ↓
PDF QA
        ↓
Independent scientific review
        ↓
Evidence-complete package OR explicit no-go
```

### Current implementation instruction

Continue from the verified inventory and migrations recorded in the in-repository
execution status. Resolve remaining filesystem and plan-lineage items first.

Do not modify the repository architecture yet.

Do not launch new thesis training.

Do not delete ambiguous research evidence.

Refresh the in-repository workspace inventory, resolve remaining Quant-related symlinks, identify active-job dependencies, classify historical evidence, logs, scripts, plans, caches, environments and campaign roots, and record the canonical or in-repository recycle disposition for every relevant item.

Then execute the safe consolidation, verify hashes and references, and pass the workspace acceptance gate.

Only after that begin the repository-refactor section of this plan.
