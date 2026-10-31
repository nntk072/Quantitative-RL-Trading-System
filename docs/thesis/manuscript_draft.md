# Entry-State Observability in Intraday Reinforcement-Learning Trading

**Working results draft — viability result reported; the paired-seed comparison remains gated**

**Status:** not final. The corrected two-million-step, single-seed run completed on the 2025 training partition, but the selected pair did not pass its hard-loss gate: the visible-state control breached the $90,000 floor and the hidden-state treatment survived while losing 2.15%. Per-trade net expectancy over each arm's available training window was near zero, positive in 2025 Q1, and negative afterwards. This is in-sample evidence and does not establish generalization or viability. Earlier single-seed and paired-seed estimates from superseded transition rules remain historical only. The reproducible monthly policy, non-PPO control, and entry/exit ledgers are linked in Section 6. This Markdown file remains the requested deliverable; no full thesis, LaTeX document, supervisor PDF, or faculty-submission artifact is required.

## Abstract

This study evaluates whether exposing a simulator's causal entry-lifecycle state to a PPO trading policy changes simulated net returns. In the corrected two-million-step seed-50 training run, mean net R per trade was -0.0122 for the hidden-state treatment and -0.0315 for the visible-state control over their available windows. Both were positive in 2025 Q1 (+0.2343 and +0.1977 R) and negative over the later training months (-0.0957 and -0.1299 R). The hidden-state arm completed the training year but lost 2.15%; the visible-state arm breached the $90,000 hard floor in October. This is an unsuccessful in-sample viability result, not evidence of generalization or comparative efficacy. The previous 2026 report interval was inspected and remains exploratory rather than fresh holdout evidence.

## 1. Introduction and research question

Intraday reinforcement-learning experiments require a policy to act on a time-ordered market state while trades pass through execution and risk rules that affect their outcomes. In this study, a trade opportunity also follows a causal lifecycle: a setup becomes a candidate, may become armed, and can then be entered. The primary question is whether exposing that lifecycle state changes the policy's net simulated return; entry activity and lifecycle counts describe how its behavior differs under the specified simulator.

The planned comparison holds the PPO algorithm, TCN encoder, reward and risk configuration, market inputs, lifecycle logic, requested training budget, and evaluation procedure fixed. Its declared configuration difference is `env.entry_state_observation`: the visible-state control includes four one-hot coordinates in the order `FLAT`, `CANDIDATE`, `ARMED`, `IN_POSITION`; the hidden-state treatment omits them. The pair's account observation therefore has widths 10 and 6, respectively. The estimand is limited to this observation change under the saved configurations and simulation protocol. The study does not compare algorithms or establish general profitability. Prior work motivates the method components but does not establish performance of this configuration.

The selected pair remains frozen: the visible-state control exposes the lifecycle state, while the hidden-state treatment omits it. The corrective development iteration is terminal and exploratory. The latest two-million-step, single-seed result is reported below: both arms lost net equity, and the visible-state control breached the hard floor. Earlier seed-50 viability and five-seed comparison estimates from superseded transition rules remain historical only. The 2026 interval remains exposed exploratory evidence.

The primary outcome is total net return over the configured 2026 report interval. The interval has been inspected previously, so this paired estimate is exploratory and cannot provide fresh confirmatory out-of-sample evidence. This report makes no efficacy claim and does not ask whether the PO3/IFVG rules are profitable generally or whether simulated fills establish live-market profitability.

## 2. Data and temporal protocol

The training interval is 30 December 2024 through 31 December 2025. The report-only interval is 1 January through 16 October 2026; the supplied M1 data contain no bars on 1 January, so the first test-session observations begin on 2 January. The 2026 interval has been inspected previously and is classified as exposed exploratory evidence. It is not a fresh or confirmatory holdout and is not used to select variants, change the pair, or tune the method.

The selected-pair runs use the US100 cash-index feed. The split contains 351,432 M1 training bars and 279,355 M1 report bars. The configured date boundary and the first supplied report bar differ because no bar exists on 1 January. All ten terminal run manifests record matching train/report inputs across each same-seed pair, including bars, features, secondary data, and bid/ask ticks.

| Partition | Configured date window | M1 rows | Role |
|---|---|---:|---|
| Training | 2024-12-30–2025-12-31 | 351,432 | Policy learning and training-only viability checks |
| Report | 2026-01-01–2026-10-16 | 279,355 | Exposed, report-only evaluation; no model or pair selection |

All supplied observations remain in their chronological partition, including bars from short sessions. Scheduled early closes are provided to the policy as date-level context before that date begins, so the policy does not need to infer them from price movement. The schedule contains 16 dates. In 2025, ten substantially shorter observed New York sessions per symbol (about 206–225 M1 bars rather than 391) overlap scheduled dates. Several nearly full sessions contain a few missing minute labels; the audit cannot distinguish provider feed gaps from an alternate calendar, so those days remain unclassified. No bars are removed. The configured schedule is available in [the session calendar](../../config/ny_session_schedule.csv).

M1 is the only policy timestep. Supplied M3, M5, M10, M15, M30, H1, H4, and D1 bars are retained for multi-timeframe feature construction and aligned to the M1 decision index only after their source bars close; they do not create additional policy decision timelines. Configured schedule dates are marked from the first bar; the flags describe the declared calendar, not a classification inferred from observed row counts. Bid/ask tick data drive simulated execution. The declared fill protocol draws a seeded arrival delay from the configured 0–30 millisecond interval and uses the first eligible bid/ask tick at or after order arrival. The configuration also declares 5.0 points of slippage, but the strict tick-fill path currently executes at the selected raw bid/ask and does not apply this extra slippage. Thus the viability pilot run tests viability under tick quotes and randomized latency, not under the configured extra slippage. This is a reproducible simulator assumption; it does not model queue position, market impact, or all broker execution effects.

## 3. Policy and intervention

The candidate policies use PPO with a TCN encoder and the pair-specific saved effective configurations. Each run requests 20 million environment steps. The corrective screen uses seed 50 for one run per each of 18 variants; it is a repair and viability iteration, not the final paired-seed analysis. After the selected pair passed the viability screen, the predeclared paired-seed evaluation started both arms from scratch under a new run identity, with matched seeds 101–105 and identical seed assignment in both arms. A separate earlier experiment run using two of these seed IDs was interrupted under the defective implementation and is ineligible; none of its checkpoints were reused. A resumed run continues only from its own saved checkpoint.

All ten terminal paired-seed comparison manifests record the same training settings across both arms: a shared actor with a TCN encoder using channels `[128, 128, 256, 256]`, dilations `[1, 2, 4, 8]`, kernel size 3, and latent width 128; and a policy head with widths `[256, 128]`. PPO uses 64 logical environments, 128 steps per environment per rollout (8,192 transitions), minibatches of 4,096, 15 epochs, learning rate `3×10⁻⁴`, discount `γ=0.99`, GAE `λ=0.95`, clip range 0.2, and entropy coefficient 0.001. This gives two minibatches per epoch and 30 per rollout. The reward is differential Sharpe with `η=0.01`; continuous actions use a clamped diagonal Gaussian. The visible-state and hidden-state policies have 1,438,051 and 1,437,919 parameters, respectively; this count difference follows from the four additional observed state coordinates. Each arm completed at least 20 million training steps, with checkpoint integrity verified by the run records.

The entry-state machine represents a causal opportunity lifecycle: a qualifying setup creates a candidate, subsequent evidence may arm it, and an eligible policy action can trigger entry. The intervention changes whether the policy observation exposes the machine state. It does not change the market data, entry evidence, execution protocol, or risk rules. The frozen configuration audit records `env.entry_state_observation` as the sole difference; the terminal resolved configurations and manifests confirm this for all five pairs.

The development screen trains each of the 18 registered variants once with seed 50 and a 20-million-step budget. It is a repair and viability screen, not the selected-pair estimate. The development screen corrective iteration is terminal and is classified as exploratory because it resumed warm-start checkpoints under an explicit approved resume override. The completed viability pilot started both frozen pair arms from scratch with seed 50 and the same 20-million-step budget on the 2025 training partition; its viability decision used only the 2025 in-sample evaluation and reconciled reward diagnostics. After that gate passed, the paired-seed comparison started both arms from scratch for matched training seeds 101–105 with the same requested budget per run. Runtime libraries, resolved environment settings, and data identities are recorded in each run's effective configuration and manifest.

The terminal development iteration warm-started all 18 variants from earlier checkpoints: six at 9 million steps, four at 10 million, seven at 11 million, and one at 13 million. Both selected entry-state policies started from 9 million-step checkpoints. This was a continuation under reorganized source, not a fresh 20-million-step run. The later viability pilot and five-seed comparison started both selected policies from scratch; the paired comparison resumed only from its own saved checkpoints.

## 4. Evaluation and analysis

The paired evaluation uses deterministic policy actions and a matched evaluation runtime and execution-seed protocol for each pair. The 2025 interval supports viability diagnostics and training-only evaluation. The exposed 2026 interval is report-only and cannot support model selection or a fresh confirmatory out-of-sample claim. The primary outcome is total net return percentage, calculated as `100 × total_pnl / initial_balance`. For each seed 101–105, the paired difference is hidden-treatment return minus visible-control return in percentage points. Report every seed-level pair, the mean paired difference, and its two-sided 95% Student-t interval across the five paired differences (four degrees of freedom). This interval describes training-seed variability conditional on the fixed 2026 interval; it does not represent uncertainty across market years. A completed full-interval no-trade run contributes 0% return and remains included. Trade/fill counts and full-period survival are secondary diagnostics. If any declared seed lacks a valid completed pair, do not replace it or report a complete five-pair estimate.

The five paired runs are complete and identity matched. They compare the visible-state control with the hidden-state treatment across seeds 101–105. The report period had already been inspected, so this is exploratory evidence. Machine-readable run records show matching costs, data, execution, features, account settings, model settings, reward, split, and training budget; whether entry-lifecycle state is exposed is the only substantive policy-input difference.

The selected-pair cost-stress analysis is a separate evaluation-only comparison. The saved configurations specify 5.0 points of slippage; the replay therefore compares effective 5.0-point baseline fills with 10.0-point adverse stress fills. The evaluation override worsens only the executed quote side after tick selection, preserving the opposite side, selected tick, timestamp, latency draw, execution seed, and position-sizing reserve. Checkpoint, data, action mode, and all other settings are fixed. single-seed and paired-seed training used raw selected tick quotes without this extra slippage, so the replay describes evaluation cost sensitivity, not the costs experienced during training. The 24-record ledger and 240 artifact integrity checks passed, with exact repeated results for seed 101 in both arms at both cost levels. Numerical results and provenance are in Section 6.2 and the linked report.

## 5. Related work

Reinforcement learning has been applied to portfolio allocation and algorithmic trading with different instruments, action spaces, horizons, and transaction-cost assumptions. Examples include policy-gradient comparisons on daily Dow Jones stocks ([Yang et al., 2020](https://doi.org/10.1145/3383455.3422540)) and deep reinforcement learning on continuous futures ([Zhang, Zohren, and Roberts, 2020](https://doi.org/10.3905/jfds.2020.1.030)). These studies establish methodological precedent; they do not show that PPO or the structural entry rules used here are profitable on this US100 cash-index M1 simulation.

Differential-Sharpe objectives have been studied as online trading-system objectives ([Moody and Saffell, 1998](https://proceedings.neurips.cc/paper_files/paper/1998/file/4e6cd95227cb0c280e99a195be5f6615-Paper.pdf)), while proximal policy optimization is a general policy-gradient algorithm ([Schulman et al., 2017](https://arxiv.org/abs/1707.06347)). Temporal convolutional networks provide a sequence-modeling alternative to recurrent architectures ([Bai, Kolter, and Koltun, 2018](https://arxiv.org/abs/1803.01271)). This thesis uses its saved PPO, encoder, reward, and risk settings as fixed components of the selected comparison; it does not test which algorithm, encoder, or reward is best.

Partial-observability research studies when an agent's observation is not a sufficient state representation. Allen et al. introduce the λ-discrepancy as a way to detect this mismatch and demonstrate a recurrent memory function for mitigating it ([Allen et al., 2024](https://papers.nips.cc/paper_files/paper/2024/hash/73073ccb3bc559fd001e66b9079d6d5e-Abstract-Conference.html)). Nguyen et al. use a fully observable state expert during training to help a partially observable policy ([Nguyen et al., 2023](https://proceedings.mlr.press/v205/nguyen23a.html)). These works study broader sequential-decision and robotics settings. This thesis tests a narrower intervention: it exposes or omits four already-computed entry-lifecycle indicators while keeping the environment and training configuration fixed; it adds neither a learned memory nor a state-expert training objective.

Selection among many trials can overstate performance, motivating transparent trial history and strict separation of selection from reporting ([Bailey et al., 2017](https://doi.org/10.21314/jcf.2016.322)). Here, the previously inspected 2026 interval is exposed, report-only evidence; the paired-seed interval describes variation across training seeds conditional on that fixed market period, not uncertainty across market years. The comparison asks whether exposing the causal entry-lifecycle state changes the saved policy's simulated net return. The cited literature does not test this intervention or validate the project's PO3/IFVG definitions.

## 6. Results and interpretation

**Evidence status:** historical single-seed and paired-seed results from before the universal session-level entry gate was removed are retained for audit and are not results for the corrected implementation. The current 2M viability pilot pair is also unsuccessful: its net per-trade expectancy is near zero overall, changes from positive in Q1 to negative later in the training year, and the visible-state arm breaches the hard floor. the viability pilot did not pass; paired-seed comparison remains gated.

### Corrected 2M viability pilot result and training-year behavior

The matched seed-50 pair completed 2,007,040 steps per arm on the 2024-12-30–2025-12-31 training interval. On actual completed trades, historical net R (raw executable bid/ask, zero additional tick-fill slippage, zero commission, and no stress) averaged -0.0122 R across 987 hidden-state treatment trades and -0.0315 R across 825 visible-state control trades. The initial partial December 2024 month is included. In 2025 Q1, the respective means were +0.2343 R (269 trades) and +0.1977 R (266 trades); from April to each arm's final available month, they were -0.0957 R (706 trades, through December) and -0.1299 R (547 trades, through October). Thus the full-window net expectancy is close to zero, but the positive first quarter did not persist in-sample. The hidden-state arm survived the $90,000 floor but ended down 2.154%; the visible-state arm breached the floor on 2025-10-28 at $89,943.95. The pair therefore fails viability pilot; the treatment's survival is not a profitability pass.

The month-by-month behavior audit shows that logged PPO entry-intent frequency was high relative to actual openings: about 427–546 intents per 1,000 decisions for the hidden-state arm and 399–799 for the visible-state arm. Before the visible-state floor breach, about 1.2–3.6% of monthly entry intents became openings; after the breach its acceptance fell to zero. Openings per 1,000 decisions varied materially by month rather than following a steady decline; both arms had their lowest activity in July and recovered in October. After the visible-state arm hit the hard floor, it continued to produce logged entry intents but opened no new trades in November–December. Among logged entry intents, the treatment selected long more often (roughly 51–57%) and the control selected short more often (roughly 58–65%). These action shares are conditional on logged entry intents, not the full per-step PPO action distribution: the training trade ledger omits no-op decisions and actions taken while a position is open.

As a non-PPO reference on the same training months, the causal `SessionMomentumStrategy` opened and completed 1,057 positions across 99,492 decisions, then crossed the $90,000 floor on 2025-11-11 at $89,977.27. It is a descriptive in-sample rule reference under the same simulator and risk configuration, not a matched-entry comparison or independent out-of-sample test. After its floor breach, the remaining dataset decisions produced no openings.

The separate March–April gross-R replay found a decline of -0.2177 R/trade for the hidden-state arm and -0.2238 R/trade for the visible-state arm. The paired decomposition attributes larger point estimates to the changed monthly entry cohorts than to the actual-exit difference from the common EMA21 reference, but all component and total bootstrap intervals include zero. Entry composition versus exits is therefore not resolved by this analysis. The per-trade ledgers enable a further day-block before-and-after analysis.

Reproducible artifacts: [monthly policy dynamics, net expectancy, and non-PPO control report](evidence/p6_monthly_entry_exit_20261025/p6_training_dynamics_control.md), [actual-fill monthly gross/net and paired exit decomposition](evidence/p6_monthly_entry_exit_20261025/p6_monthly_entry_exit_decomposition.md), [treatment paired-trade ledger](evidence/p6_monthly_entry_exit_20261025/ladder_a4a_entry_fsm_hidden_qgrid025_paired_trades.csv), [control paired-trade ledger](evidence/p6_monthly_entry_exit_20261025/ladder_a4b_entry_fsm_qgrid025_paired_trades.csv), and [non-PPO per-trade ledger](evidence/p6_monthly_entry_exit_20261025/p6_session_momentum_trade_ledger.csv). These remain training-only descriptive evidence; the report-period split is not used here.

### Checkpoint recovery and deterministic replay

A recovery smoke restored a saved seed-50 checkpoint and completed 16,384 smoke steps. Two deterministic reanalyses used the same checkpoint, effective settings, action schema, evaluation backend, execution seed, and split boundaries. Their train and report-split numerical outputs matched exactly. The smoke trainer nevertheless failed its configured training survival gate, so this establishes recovery and report repeatability only, not strategy viability. No report-period performance values are claimed.

### Initial 18-variant development screen (before the FSM repair)

The first seed-50 screen targeted 20 million steps per variant and predates the baseline/FSM repair. Eight variants recorded at least one training trade and ten recorded none; both predeclared FSM arms recorded zero training trades. The terminal summary reports 15 controller successes and three failures of the configured training risk-survival gate (Single target policy, Single target policy (PO3/IFVG), Multiple targets policy (session-distribution)). This screen's 2026 evaluation role was `selection_acknowledged` on a previously inspected interval. These results are descriptive development evidence from an implementation later found to have a baseline/FSM candidate-generation defect; they neither estimate the effect of state visibility nor provide a confirmatory comparison or strategy-efficacy result. The screen is not treated as an unexposed holdout or as a basis for a new selection claim.

**Training outcomes**

| Variant | Controller | Train gate | Full-year episodes | Environments reaching year end | Train return | Train PnL (USD) | Train trades |
|---|---|---|---:|---:|---:|---:|---:|
| Flat policy | succeeded | PASS | 64 | 64 | -3.61% | -3,606.28 | 251 |
| Single stop policy | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single target policy | failed | FAIL | unavailable | unavailable | -10.10% | -10,102.11 | 571 |
| Multiple targets policy | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Visible-state control | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Hidden-state treatment | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Flat policy (PO3/IFVG) | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single stop policy (PO3/IFVG) | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single target policy (PO3/IFVG) | failed | FAIL | 0 | 0 | -10.13% | -10,127.90 | 295 |
| Multiple targets policy (PO3/IFVG) | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Visible-state control (PO3/IFVG) | succeeded | PASS | 0 | 0 | -0.89% | -886.36 | 11 |
| Hidden-state treatment (PO3/IFVG) | succeeded | PASS | 0 | 0 | -1.69% | -1,692.44 | 11 |
| Flat policy (session-distribution) | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single stop policy (session-distribution) | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single target policy (session-distribution) | succeeded | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Multiple targets policy (session-distribution) | failed | FAIL | 0 | 0 | -10.40% | -10,403.69 | 498 |
| Visible-state control (session-distribution) | succeeded | PASS | 0 | 0 | -0.44% | -444.65 | 1 |
| Hidden-state treatment (session-distribution) | succeeded | PASS | 0 | 0 | -0.00% | -0.16 | 1 |

**Exposed report-period outcomes**

| Variant | Return | PnL (USD) | Max DD | Sharpe | Profit factor | Trades | Survived / sessions |
|---|---:|---:|---:|---:|---:|---:|---|
| Flat policy | -1.73% | -1,731.17 | 3.41% | -1.005 | 0.870 | 197 | yes / 115/205 |
| Single stop policy | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single target policy | -10.28% | -10,279.84 | 12.51% | -1.142 | 0.834 | 166 | no / 44/205 |
| Multiple targets policy | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Visible-state control | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Hidden-state treatment | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Flat policy (PO3/IFVG) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single stop policy (PO3/IFVG) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single target policy (PO3/IFVG) | -10.32% | -10,319.65 | 18.30% | -0.959 | 0.799 | 99 | no / 23/205 |
| Multiple targets policy (PO3/IFVG) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Visible-state control (PO3/IFVG) | -0.62% | -623.56 | 0.64% | -1.252 | 0.023 | 4 | yes / 4/205 |
| Hidden-state treatment (PO3/IFVG) | -1.39% | -1,393.74 | 1.40% | -2.095 | 0.000 | 4 | yes / 4/205 |
| Flat policy (session-distribution) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single stop policy (session-distribution) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single target policy (session-distribution) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Multiple targets policy (session-distribution) | -10.48% | -10,480.14 | 15.07% | -1.008 | 0.764 | 82 | no / 20/205 |
| Visible-state control (session-distribution) | +0.49% | +491.32 | 0.20% | 1.306 | — | 1 | yes / 1/205 |
| Hidden-state treatment (session-distribution) | +0.00% | +0.28 | 0.00% | 1.306 | — | 1 | yes / 1/205 |

The controller report reconciled all 36 train/test PnL values against final equity. Three variants failed the configured training-survival checks. Full per-run evidence and resource samples remain in machine-readable run records; this development screen does not estimate the visible-versus-hidden intervention.

### Corrective development iteration (warm-start, exploratory)

The terminal development iteration continued inherited checkpoints after the baseline and entry-state repair; it was not a fresh matched comparison. In the selected pair's 2025 training evaluation, the visible-state control recorded 6 trades, +$1,002.70 total PnL, and a reconciled Differential-Sharpe reward sum of 0.2483. The hidden-state treatment recorded 7 trades, +$3.18 total PnL, and reward sum 0. Both completed the training period with full-year survival and tick-sourced fills. The treatment's zero reward fails the learning-viability criterion despite its trades and positive PnL. These exploratory warm-start figures are not an estimate of the state-visibility effect. Detailed diagnostics are retained with the machine-readable run records; both arms reconcile reward attribution with zero error and no unattributed reward.

The terminal development-screen outcomes are summarized below. Training metrics are in-sample; the 2026 results are exposed report-only outcomes from a previously inspected interval. “Pass” and “fail” refer only to the configured training survival gate. One controller success only re-evaluated an inherited checkpoint and performed zero new learning steps. These warm-start results are exploratory and were not used as comparative evidence or to select the frozen pair. The tables retain unavailable values from the source summary and report no profit factor where none was provided.

**Training outcomes**

| Variant | Gate | Full-year episodes | Environments reaching year end | Train return | Train PnL (USD) | Train trades |
|---|---|---:|---:|---:|---:|---:|
| Flat policy | PASS | 64 | 64 | -3.61% | -3,606.28 | 251 |
| Single stop policy | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single target policy | FAIL | unavailable | unavailable | -10.10% | -10,102.11 | 571 |
| Multiple targets policy | PASS† | unavailable | unavailable | +0.00% | +0.00 | 0 |
| Visible-state control | PASS | 0 | 0 | +1.00% | +1,002.70 | 6 |
| Hidden-state treatment | PASS | 0 | 0 | +0.00% | +3.18 | 7 |
| Flat policy (PO3/IFVG) | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single stop policy (PO3/IFVG) | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single target policy (PO3/IFVG) | FAIL | unavailable | unavailable | -10.69% | -10,688.57 | 314 |
| Multiple targets policy (PO3/IFVG) | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Visible-state control (PO3/IFVG) | PASS | 0 | 0 | -0.89% | -886.36 | 11 |
| Hidden-state treatment (PO3/IFVG) | PASS | 0 | 0 | -1.69% | -1,692.44 | 11 |
| Flat policy (session-distribution) | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single stop policy (session-distribution) | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Single target policy (session-distribution) | PASS | 0 | 0 | +0.00% | +0.00 | 0 |
| Multiple targets policy (session-distribution) | FAIL | unavailable | unavailable | -10.48% | -10,477.67 | 318 |
| Visible-state control (session-distribution) | PASS | 0 | 0 | -0.44% | -444.65 | 1 |
| Hidden-state treatment (session-distribution) | PASS | 0 | 0 | -0.00% | -0.16 | 1 |

**Exposed report-period outcomes**

| Variant | Return | PnL (USD) | Max DD | Sharpe | Profit factor | Trades | Survived / sessions |
|---|---:|---:|---:|---:|---:|---:|---|
| Flat policy | -1.73% | -1,731.17 | 3.41% | -1.005 | 0.870 | 197 | yes / 115/205 |
| Single stop policy | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single target policy | -10.28% | -10,279.84 | 12.51% | -1.142 | 0.834 | 166 | no / 44/205 |
| Multiple targets policy | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Visible-state control | +5.39% | +5,387.81 | 1.14% | 2.099 | 3.749 | 7 | yes / 7/205 |
| Hidden-state treatment | +0.00% | +1.56 | 0.00% | 1.130 | 3.977 | 8 | yes / 8/205 |
| Flat policy (PO3/IFVG) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single stop policy (PO3/IFVG) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single target policy (PO3/IFVG) | -10.12% | -10,115.57 | 12.12% | -1.051 | 0.571 | 51 | no / 10/205 |
| Multiple targets policy (PO3/IFVG) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Visible-state control (PO3/IFVG) | -0.62% | -623.56 | 0.64% | -1.252 | 0.023 | 4 | yes / 4/205 |
| Hidden-state treatment (PO3/IFVG) | -1.39% | -1,393.74 | 1.40% | -2.095 | 0.000 | 4 | yes / 4/205 |
| Flat policy (session-distribution) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single stop policy (session-distribution) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Single target policy (session-distribution) | +0.00% | +0.00 | 0.00% | 0.000 | 0.000 | 0 | yes / 0/205 |
| Multiple targets policy (session-distribution) | -10.21% | -10,211.90 | 13.89% | -0.915 | 0.763 | 67 | no / 20/205 |
| Visible-state control (session-distribution) | +0.49% | +491.32 | 0.20% | 1.306 | — | 1 | yes / 1/205 |
| Hidden-state treatment (session-distribution) | +0.00% | +0.28 | 0.00% | 1.306 | — | 1 | yes / 1/205 |

The terminal development screen recorded 15 controller successes, three training-gate failures, and reconciliation of all 36 train/test PnL values. Its machine-readable run records preserve the approved resume override and identify the results as exploratory. The screen is a development history, not a causal estimate for the visible-versus-hidden intervention.

The corrective development iteration is complete. It retains three training risk-gate failures and one checkpoint re-evaluation with no new learning; resumed outcomes are exploratory. Under the prior entry rules, the single-seed viability pilot and five-seed comparison passed their historical run-level checks, but neither supports claims about the corrected entry logic. The 2026 interval was previously inspected, so those comparisons were exploratory rather than fresh confirmatory evidence.

### Historical 2M seed-50 pilot (superseded run and risk-gate interpretation)

This earlier run tested startup, learning progress, and entry-lifecycle operation using the frozen visible-state control and hidden-state treatment. It is superseded by the latest viability pilot pair result above and retained only to preserve the run history. Each arm trained from scratch for the requested 2,000,000 steps and completed 2,007,040 steps. Its replay produced active trading and reconciled reward attribution, but each hit the then-used survival gate. Its reported training win rates were 41.73% in the visible arm and 39.38% in the hidden arm; mean PnL per completed position was -$72.23 and -$7.37, with profit factors 0.712 and 0.972. These values do not describe the latest two-million-step viability run and provide no current comparative-effect estimate.

| Arm | Completed steps | Training trades | Training PnL | Return | Max peak-to-trough drawdown | Breach | Cumulative DSR reward | Reward reconciliation error | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Visible-state control | 2,007,040 | 139 | -$10,040.58 | -10.04% | 10.41% | 1 | -21.2300 | 2.1e-14 | FAIL |
| Hidden-state treatment | 2,007,040 | 1,356 | -$9,991.11 | -9.99% | 39.50% | 1 | -16.8194 | 7.8e-14 | FAIL |

The saved configuration disabled peak-trailing drawdown in this historical pilot. The report’s 10% peak-to-trough threshold was checked after replay and did not stop evaluation. The full-period evaluation instead enforced the $10,000 loss limit from initial equity. This explains why the reported path could fall more than 10% from its peak before ending near the initial-equity floor. The test run’s settings and results are retained in the machine-readable run record. Before any longer viability run, test the intended peak-drawdown behavior in a bounded matched pilot; the historical checkpoints are not eligible for warm start.

### Historical seed-50 viability pilot (viability pilot; superseded entry rules)

After the FSM repair, each selected arm was trained from scratch for the requested 20 million steps with seed 50 on the 2025 training interval. Both completed 20,004,864 steps, survived the full training year without a risk-gate breach, and generated seven trades. The outcome is a minimum viability check for the repaired training path; the single seed does not estimate the effect of exposing the lifecycle state.

| Arm | Completed steps | Trades | Net PnL | Return | Max drawdown | Full-year survival | Cumulative DSR reward | Reward error / unattributed | Candidates; entries / closes |
|---|---:|---:|---:|---:|---:|---|---:|---|---|
| Visible-state control | 20,004,864 | 7 | $6,349.80 | 6.35% | 2.76% | yes | -4.0182 | 0.0 / 0.0 | 4,530; 7 / 7 |
| Hidden-state treatment | 20,004,864 | 7 | $4,579.86 | 4.58% | 1.70% | yes | -5.6819 | 0.0 / 0.0 | 4,577; 7 / 7 |

Both cumulative Differential-Sharpe reward sums are negative. The viability check therefore establishes only that both repaired policies completed the training year with trades and reconciled reward attribution; it does not establish positive risk-adjusted learning or comparative efficacy. Each arm recorded fourteen tick-sourced fill-quote events. The automatic 2026 evaluation is excluded. The replay used selected raw tick quotes without the additional configured 5-point slippage. Run settings, reports, and machine-readable evidence are retained with the experiment records.

### Historical paired-seed comparison exploratory paired results (superseded entry rules)

The primary outcome is net return, calculated as `100 × total_pnl / initial_balance`. The paired difference is hidden treatment minus visible control in percentage points. All five pairs completed at least the requested 20 million training steps, and each pair shares the same data, feature, execution, reward, cost, model, and evaluation identities. The machine-readable run records retain the exact input and source identities for reproduction.

Each arm requested 20,000,000 training steps. Completed step counts below were checked against all ten terminal run manifests.

| Seed | Visible control steps | Hidden treatment steps |
|---:|---:|---:|
| 101 | 20,004,864 | 20,005,312 |
| 102 | 20,004,864 | 20,004,864 |
| 103 | 20,001,280 | 20,004,864 |
| 104 | 20,001,280 | 20,005,440 |
| 105 | 20,005,312 | 20,005,440 |

| Seed | Visible control PnL | Trades | Return | Hidden treatment PnL | Trades | Return | Difference |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 101 | $531.55 | 8 | 0.5316% | $1,950.49 | 8 | 1.9505% | +1.4189 pp |
| 102 | $543.49 | 8 | 0.5435% | $76.97 | 8 | 0.0770% | -0.4665 pp |
| 103 | $7.96 | 8 | 0.0080% | $3,288.64 | 7 | 3.2886% | +3.2807 pp |
| 104 | $1.72 | 7 | 0.0017% | $1,904.46 | 7 | 1.9045% | +1.9027 pp |
| 105 | $1,714.26 | 7 | 1.7143% | $2.09 | 8 | 0.0021% | -1.7122 pp |

The mean paired difference is **+0.8847 percentage points** (sample SD 1.9769). Its two-sided 95% Student-t interval is **[-1.5699, +3.3393] percentage points** (4 degrees of freedom), which includes zero. The supplemental paired-seed bootstrap interval is [-0.7401, +2.3572] percentage points using 10,000 paired-seed resamples; the exact two-sided paired sign-flip test gives p=0.4375. With five seeds, this test has coarse attainable p-values and assumes symmetry of paired differences under its null. The comparison does not establish that hiding the lifecycle state improves returns. Because the 2026 interval was inspected previously, these results are exploratory and cannot support a fresh confirmatory claim. Detailed calculations are retained with the machine-readable run records.

### Historical selected-pair execution-cost sensitivity (paired-seed comparison; superseded entry rules)

The same five checkpoints per arm were re-evaluated at effective tick-fill slippage of 5.0 points and 10.0 points. Only the adverse executed side changes after tick selection; tick/time/latency selection, opposite quotes, action mode, data, checkpoint, and position-sizing reserve remain fixed. The 5-point baseline here is applied to evaluation fills even though single-seed and paired-seed results training used raw selected tick quotes. The 2026 report interval was previously inspected, so these are exploratory sensitivity results, not fresh out-of-sample evidence.

| Arm | Mean 10-point minus 5-point return | Paired-seed Student-t 95% CI (df=4) | Paired-seed bootstrap 95% CI | Exact sign-flip p (Holm) |
|---|---:|---:|---:|---:|
| Visible-state control | -0.7830 pp | [-1.7623, +0.1963] pp | [-1.4028, -0.1632] pp | 0.0625 (0.0625) |
| Hidden-state treatment | -0.7353 pp | [-1.5275, +0.0570] pp | [-1.2375, -0.2474] pp | 0.0625 (0.0625) |

The mean cost-stress difference is negative in both arms, and all five seed-level differences are negative in each arm. With only five paired seeds, the exact test is discrete; p=0.0625 does not cross a 0.05 threshold. The Student-t intervals include zero, while the paired-seed bootstrap intervals do not. These intervals resample training seeds and do not measure uncertainty across market periods or temporal paths. The divergence between interval methods, the small seed count, and low trade counts counsel against calling either arm robust or declaring a statistically established cost effect.

| Seed | Control 5-point return | Control 10-point return | Difference | Trades 5 / 10 | Treatment 5-point return | Treatment 10-point return | Difference | Trades 5 / 10 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 101 | +0.131244% | -0.627920% | -0.759165 pp | 8 / 8 | +1.175005% | -0.354295% | -1.529299 pp | 8 / 8 |
| 102 | +0.112123% | -1.658986% | -1.771108 pp | 8 / 8 | -0.006110% | -0.350668% | -0.344558 pp | 8 / 8 |
| 103 | +0.002044% | -0.024893% | -0.026938 pp | 8 / 8 | +2.738891% | +2.191543% | -0.547348 pp | 7 / 7 |
| 104 | +0.001048% | -0.000331% | -0.001378 pp | 7 / 7 | +1.690109% | +0.435291% | -1.254818 pp | 7 / 7 |
| 105 | +1.055341% | -0.301011% | -1.356353 pp | 7 / 7 | +0.001588% | +0.001257% | -0.000331 pp | 8 / 8 |

The replay ledger contains all 24 expected records. Exact repeated seed-101 runs matched for both arms at each cost level. The integrity audit passed; full per-run settings and replay inputs remain in the machine-readable evidence records.


## 7. Limitations

The available 2026 interval is exposed and cannot establish untouched out-of-sample performance. The configured date-level schedule reaches policy inputs from the first bar. In the audited 2025 training interval, all materially shorter observed NY sessions overlap configured dates; several near-full sessions with a few fewer than 391 minute rows remain unclassified, and the 2026 report interval has no separate per-date shape audit. Calendar completeness for every provider-specific reduced-hours or data-gap date is therefore not claimed. The selected-pair evaluation cost stress is complete: both arm means declined at 10 points, but each five-seed Student-t interval includes zero and the exact p-value is 0.0625. The paired-seed bootstrap intervals exclude zero, so the method-dependent uncertainty result is reported without treating it as a definitive effect. Low trade counts and prior inspection of the report interval further limit interpretation. single-seed and paired-seed results training used raw tick quotes without the extra slippage; the stress therefore measures evaluation sensitivity rather than training-time cost exposure. The simulator does not model queue position, market impact, every broker execution effect, or live trading performance. The data feed and contract details also limit transfer to other markets.

## 8. Discussion and current conclusion

**Historical conclusion only:** the interpretation below summarizes the prior implementation and must not be treated as the conclusion for the corrected entry rules. Replace it after single-seed and paired-seed results evidence is refreshed.

The experiment has not shown a reliable return advantage from hiding the entry-lifecycle state. The five paired differences have mixed signs, and the positive mean of +0.8847 percentage points is imprecise: its 95% Student-t interval spans negative and positive effects, and the exact paired sign-flip p-value is 0.4375. Report-period activity was low (seven or eight trades per arm and seed), so the result is sensitive to a small number of simulated trades. It remains descriptive evidence conditional on this market interval and simulator, not a causal or general profitability claim.

The seed-50 scratch pilot shows that both selected policies can complete the training year with trades and reconciled reward attribution, but their negative cumulative Differential-Sharpe rewards do not indicate strong risk-adjusted learning. The 18-variant screen records a development history and retained gate failures; its warm-start outcomes do not estimate the selected intervention. Cost-stress replays show lower returns at 10 points in every seed for both arms, but five pairs, low activity, exposed data, and interval-method disagreement leave the strength and generality of that sensitivity uncertain. The evidence identities for these claims are frozen in this report and its linked provenance artifacts.

## References

- Allen, C., Kirtland, A., Tao, R. Y., Lobel, S., Scott, D., Petrocelli, N., Gottesman, O., Parr, R., Littman, M. L., & Konidaris, G. (2024). [Mitigating partial observability in sequential decision processes via the λ-discrepancy](https://doi.org/10.52202/079017-2011). *Advances in Neural Information Processing Systems, 37*.
- Bai, S., Kolter, J. Z., & Koltun, V. (2018). [An empirical evaluation of generic convolutional and recurrent networks for sequence modeling](https://arxiv.org/abs/1803.01271). arXiv:1803.01271.
- Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2017). [The probability of backtest overfitting](https://doi.org/10.21314/jcf.2016.322). *Journal of Computational Finance, 20*(4), 39–69.
- Moody, J. E., & Saffell, M. (1998). [Reinforcement learning for trading](https://proceedings.neurips.cc/paper_files/paper/1998/file/4e6cd95227cb0c280e99a195be5f6615-Paper.pdf). *Advances in Neural Information Processing Systems, 11*.
- Nguyen, H. H., Baisero, A., Wang, D., Amato, C., & Platt, R. (2023). [Leveraging fully observable policies for learning under partial observability](https://proceedings.mlr.press/v205/nguyen23a.html). *Proceedings of the 6th Conference on Robot Learning*, 205, 1673–1683.
- Schulman, J., Wolski, F., Dhariwal, P., Radford, A., & Klimov, O. (2017). [Proximal policy optimization algorithms](https://arxiv.org/abs/1707.06347). arXiv:1707.06347.
- Yang, H., Liu, X.-Y., Zhong, S., & Walid, A. (2020). [Deep reinforcement learning for automated stock trading: An ensemble strategy](https://doi.org/10.1145/3383455.3422540). In *Proceedings of the First ACM International Conference on AI in Finance*.
- Zhang, Z., Zohren, S., & Roberts, S. (2020). [Deep reinforcement learning for trading](https://doi.org/10.3905/jfds.2020.1.030). *The Journal of Financial Data Science, 2*(2), 25–40.

## 9. Historical report audit and remaining work

- Historical selected-pair cost-stress ledger, 240 artifact integrity checks, four exact repeats, numerical report, and statistics JSON identities are retained above; rerun selected-pair stress only after corrected paired-seed comparison checkpoints exist.
- Historical 18-variant, viability pilot, and paired-seed comparison audit counts and machine-readable records apply only to the prior implementation. Reconcile corrected single-seed and paired-seed results artifacts against their manifests and evidence after those runs finish.
- Keep the report self-contained in its explanation and tables; keep exact input identity in machine-readable evidence records for reproducibility.
- The evidence freeze remains open. Freeze corrected experiment run manifests, checkpoints, metrics, reports, source/data/config provenance, and claim limits only after the corrected single-seed and paired-seed results gates pass.
The manuscript remains a working results draft. Refresh the results and conclusion after the corrected viability and paired-seed evidence is available; record the final document version in the execution plan.
