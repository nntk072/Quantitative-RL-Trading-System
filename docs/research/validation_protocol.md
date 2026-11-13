# Validation protocol

An evaluation result is interpretable only when its data role, model identity,
action meaning, execution assumptions, and selection history are explicit.
This protocol applies to training, model selection, exploratory analysis, and
final reporting.

## Period roles

| Role | Permitted use |
|---|---|
| Training | Fit policy parameters and transformations that are declared train-fitted. |
| Validation or walk-forward folds | Select configurations under a predeclared procedure. Purge outcome overlap and apply the configured embargo. |
| Exposed exploratory period | Diagnose or develop after prior inspection. It cannot support a fresh confirmatory claim. |
| Locked final period | Final reporting only while it remains uninspected and unused for model or analysis decisions. |

Assign period roles before interpreting outcomes. Re-running an exposed period
does not restore its status as untouched. Record prior exposure, selection
permissions, and period boundaries in the experiment and evaluation manifests.
Do not change a locked period as an informal way to recover a holdout.

## Research questions and prospective selection contract

The retained 2025 campaign and the inspected 2026 report period are historical
development evidence. They did not follow this prospective contract and must
not be relabeled as preregistered or confirmatory. The local study is limited to
the configured market data and simulator; it makes no claim about broker fills,
provider rights, or an untouched external period.

The remaining research questions are:

1. **Representation validity:** are the active features, setup eligibility,
   observation masks, and candidate event times causal and reproducible on the
   configured decision timeline?
2. **Decision and execution validity:** does each eligible action map to a
   legal, timestamped order and reproducible fill, with account equity,
   charges, realized PnL, unrealized PnL, daily loss, and terminal state
   reconciling across environment and event backtest?
3. **Decision value:** after questions 1 and 2 pass, does a setup-conditioned
   policy improve account-level net outcomes over matched flat, random, and
   justified rule baselines under the same information, costs, and risk limits?
4. **Price geometry:** only after the candidate proposal, outcome, censoring,
   and purge contracts pass, does explicit candidate price geometry add useful
   decision information beyond the existing setup-class representation?

Questions 3 and 4 are gated. The first two questions do not establish economic
value, and an invalid or unsupported stage is a no-go for training or selection
that depends on it.

### Outcome and acceptance rules

- **Lexicographic priority — survival before portfolio performance:** first
  determine whether each policy survives every predeclared development and
  validation path across the required seeds. Survival means completing each
  full path with zero daily-loss, static/EOD/intraday-trailing maximum-loss, or
  other hard account breaches, with no trading after a breach. Any breached
  development or validation path makes that candidate infeasible for selection;
  returns, Sharpe, drawdown recovery, or payouts cannot compensate for it.
  Training and reward design must preserve this priority: a hard account breach
  is a terminal feasibility failure and cannot be offset by accumulated profit
  reward. Optimize portfolio performance only after identifying policies that
  meet the predeclared survival gate; do not invent a numeric breach penalty as
  a substitute for the gate. Existing reward modes still use their configured
  portfolio reward and a fixed `-10` breach term. An opt-in `survival` mode now
  emits only `+1` for completing the full local split without a breach and `-1`
  after any hard breach, with no intermediate portfolio reward. It requires
  full-split training and undiscounted returns. Its implementation tests and
  training behavior remain unverified; keep training blocked until the
  consolidated implementation gate passes. Survival qualification must use
  `account-state-v2`, whose policy observations include remaining daily-loss
  and maximum-loss budgets. The environment applies those same configured
  account rules during training; evaluation measures whether the learned policy
  avoids breaches. New configurations default to v2, and the gate rejects any
  v1 run because those budgets are hidden from the policy.
  Only candidates that pass every such path may be compared on portfolio
  outcomes. The existing minimum of six paired training seeds remains; all
  required treatment paths must pass. If no treatment passes, report the bounded
  negative result and do not optimize profit among failed policies. A locked
  final-period survival failure blocks a positive readiness verdict, but that
  period remains report-only: it cannot be used to select another candidate or
  trigger retuning. An already exposed period retains its exploratory role.
- **Primary account outcome:** net return on initial operating equity over the
  full declared development path, defined as ending retained equity plus
  cumulative payouts minus initial operating equity, divided by initial
  operating equity. Include all modeled transaction charges. Report ending
  retained balance and cumulative payouts separately so withdrawals cannot be
  mistaken for trading profit. A payout is a realized, flat-account withdrawal
  of balance above the initial operating balance; initial capital and losses
  are not withdrawable.
- **Hard safety gate:** zero daily-loss and maximum-loss breaches in every
  evaluated path. Equality at a floor is allowed; a value below it fails the
  full evaluation. A breach cannot be removed from survival statistics by
  resuming on the next session. This gate is evaluated before the primary
  account outcome and is never traded against expected return. Final-period
  breaches are reported as a readiness failure, not used for model selection.
- **Matched comparison:** treatment and each baseline must share the exact
  source/data split, feature and observation information, eligible decision
  rows, execution and quote rules, costs, risk limits, starting equity,
  evaluation dates, and per-seed environment seeds. Any mismatch makes the
  comparison descriptive.
- **Policy-selection evidence:** require at least six paired independent
  training seeds on the same declared development protocol. Six is a minimum
  resolution floor, not a power guarantee; a prospective power analysis must
  set the larger fixed seed count, if needed, before training. Every treatment
  arm's fixed count can be planned with
  `scripts/research/analysis/evidence/plan_paired_seed_count.py`, using a
  justified minimum effect and paired-seed standard deviation. Its noncentral-t
  result is an explicitly approximate planning calculation, not the exact
  power of the confirmatory sign-flip test; record the input provenance and
  freeze the count before inspecting confirmatory outcomes. The tool never
  launches or authorizes a campaign. Every treatment
  path must pass the hard safety gate. The primary contrast is treatment versus
  always-no-trade, which tests whether trading adds value over retaining the
  initial operating balance. Random-eligible-action, rule, and supervised
  policies, including RL-versus-supervised comparisons, are secondary. For each
  seed, compute full-path net return on initial operating equity as ending
  retained equity plus cumulative payouts minus initial operating equity,
  divided by initial operating equity. Form one paired treatment-minus-control
  difference per independent seed. Trades and sessions within a seed path are
  not independent replication units. Test the one-sided null of a non-positive
  paired effect with a one-sided paired sign-flip test at alpha 0.05. Enumerate
  all sign assignments exactly for up to 15 pairs; if the prospectively powered
  fixed count exceeds 15, use 100,000 Monte Carlo sign assignments with RNG
  seed 42. The chosen method follows the seed count frozen before outcomes.
  Compute a paired 95% percentile bootstrap interval over seed pairs using
  10,000 draws and RNG seed 42. Do not resample trades or session blocks for the
  primary interval. The interval does not estimate breach probability or replace the
  full-path safety gate. Select a treatment only if every treatment path passes
  the safety gate, the sign-flip test rejects, and the interval's lower bound is
  above zero. Otherwise conclude that no model has demonstrated economic
  superiority.
- **Multiplicity and tuning:** name one primary treatment-baseline contrast
  before any new outcomes are inspected. All other architecture, reward,
  threshold, and subgroup results are exploratory unless a multiplicity
  correction and selection procedure were frozen in advance. Do not use the
  exposed 2026 dates for selection, calibration, or a new holdout claim.
- **Stopping rule:** if causal data, executable parity, candidate labels, or
  required baseline matching fails, stop downstream model selection and record
  the specific no-go evidence. Do not compensate by adding steps, seeds, or
  architectures.

This is a prospective rule for work that has not yet been run; it does not
retroactively upgrade any historical result. Because the currently inspected
2026 period is exposed and no untouched local holdout has been established, the
strongest possible conclusion from the present data is development evidence,
including a bounded negative result.

## Data and model controls

- Build features causally: a decision at time *t* may use only information
  available by *t*. Higher-timeframe values become available only after their
  source bars close.
- Fit normalization and other learned preprocessing on training data only.
  Reuse the last training-fitted state for later periods.
- Keep bars in the feature timeline. Session eligibility is a mask or input,
  not a reason to delete observations.
- Match the comparison's data, split, action schema, reward, risk settings,
  costs, execution model, training budget, random seeds, and evaluation window.
  Document every difference that could affect outcomes.
- Verify dataset, source, resolved configuration, cache, and checkpoint
  identities from manifests before comparing runs.

## Evaluation and claims

Declare whether a result comes from a `TradingEnv` rollout or the
event-driven backtest. They answer related but different questions and their
outputs must not be treated as interchangeable. State the action mode and seed,
execution and fill assumptions, risk termination rules, and report interval.

Report account survival and breaches, equity and drawdown, realized trades,
costs, action behavior, and meaningful inactive or zero-trade outcomes. Include
uncertainty and matched comparisons when making claims beyond description.
Separate the measured result from possible explanations; a single interval,
seed, or simulator configuration does not establish generalization or live
profitability.

For the current period exposure and research-specific gate, see the
[research execution plan](workflow.md). For the
implementation boundary between environment and backtest, see the
[simulation guide](../modules/simulation.md) and
[evaluation guide](../modules/evaluation.md).
