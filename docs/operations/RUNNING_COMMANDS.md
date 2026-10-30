# Running Commands

The [agent command quick reference](../../.agents/commands.md) is a
convenience index; this page owns executable research and operations
commands. Agent-specific commit checks belong to
[CI verification rules](../../.agents/rules/ci-verification.md).
Additional command discovery (read-only, check the actual CLI help):

```bash
uv run python scripts/research/benchmarks/compare_encoders.py --help
uv run python scripts/research/thesis/evaluation/report_g3.py --help
```
Command catalog for research, evaluation, and live sessions. For architecture
and config details see [architecture.md](../architecture.md) and
[config.md](../config.md).

---

## Setup

Arch-matching venvs (Triton shared NFS):

```bash
cd Quantitative-RL-Trading-System
tools/setup-venv                    # aarch64 -> .venv, x86_64 -> .venv-x86
source scripts/compute/slurm/activate_venv.sh   # use inside GPU shell on Triton
```

| Arch | Venv | One-time setup |
|------|------|----------------|
| aarch64 (GH200) | `.venv` | `uv sync` on aarch64 node |
| x86_64 (H200, local) | `.venv-x86` | `tools/setup-venv-x86` |

---

## CI gate (merge bar)

GitHub Actions runs the named `tools/check` gates in parallel. Orchestra phase 9
uses the same dispatcher sequentially:

```bash
./tools/check <gate>
./tools/check full
```

For direct Ruff, Mypy, or pytest checks on Triton, use the active architecture
environment (`.venv/bin/...` on ARM/GH200, `.venv-x86/bin/...` on x86_64).
Do not use a login-host `uv` binary when it does not match the compute node.

Local shortcut (not the merge bar): `.venv/bin/pytest -m "not slow"`

---

## Data pipeline

```bash
# Raw CSV → parquet bar cache → feature cache
thesis-data prepare

# Force rebuild (ignore cache)
thesis-data prepare --force
```

---

## Unit and integration tests

```bash
# Full local merge gate
./tools/check full

# By domain
.venv/bin/pytest tests/test_features/ -q
.venv/bin/pytest tests/test_simulation/test_environment/ -q
.venv/bin/pytest tests/integration/ -q
.venv/bin/pytest tests/test_orchestra/ -q
.venv/bin/pytest tests/test_live/ -q

# Targeted
.venv/bin/pytest tests/test_trading/test_risk.py tests/test_trading/test_macd_baseline.py -q
```

---

## Baseline strategies

```bash
# MACD crossover (quick, no charts)
uv run thesis-train baselines --strategy macd --no-save

# Full run with per-trade charts
uv run thesis-train baselines --strategy macd

# Other baselines
uv run thesis-train baselines --strategy ema
uv run thesis-train baselines --strategy rsi
```

MACD rules: EMA12/26 MACD + SMA9 signal + EMA50 trend filter. Long when
`close > EMA50` and bullish cross. Cooldown ≥5 bars after exit.

---

## Random-policy backtest

```bash
uv run thesis-train backtest --no-save
uv run thesis-train backtest --seed=42
```

---

## RL training

```bash
# MVP smoke test (~8k timesteps, 30 days)
uv run thesis-train train --mvp --seed=42

# Full training (500k timesteps)
uv run thesis-train train --seed=42

# Algorithm / encoder / reward
uv run thesis-train train --mvp --algo sac --arch gru --reward sweep --seed=42

# Strategy overlay (Idea 1: PO3 + IFVG, Idea 2: distribution)
uv run thesis-train train --mvp --strategy po3_ifvg --seed=42
uv run thesis-train train --mvp --strategy distribution --seed=42

# Optional frozen VAE narrative latent (train checkpoint first via training/runner/vae.py)
uv run thesis-train train --mvp --use-vae \
    --vae-path outputs/vae/vae_best.pth --vae-config config/vae.yaml --seed=42

# Feature variant config (MTF expansion)
uv run thesis-train train --mvp \
    --config config/features/full_po3_mtf.yaml --seed=42

# Purged walk-forward validation
uv run thesis-train train --walk-forward --wf-splits 5 \
    --purge-bars 60 --embargo-bars 20 --seed=42

# Weights & Biases logging
uv run thesis-train train --mvp --wandb
```

### Config overrides (OmegaConf key=value)

```bash
uv run thesis-train train --mvp \
    account.initial_balance=100000.0 \
    env.obs_window=30 \
    training.total_timesteps_mvp=4096
```

---

## Evaluation

```bash
# Re-evaluate an existing trained run (no retraining)
uv run thesis-evaluate reanalyze --run outputs/<run_dir>

# With a specific checkpoint
uv run thesis-evaluate reanalyze --run outputs/<run_dir> \
    --checkpoint model/ppo_ckpt_328350_steps.zip

# View latest metrics
LATEST=$(ls -d outputs/*/ | tail -1)
cat "$LATEST/test/metrics.json"
```

---

## Engine cross-validation

```bash
uv run python -m simulation.backtest.cross_validation.run
```

---

## Encoder comparison

```bash
uv run python scripts/research/benchmarks/compare_encoders.py
```

## Campaign operations

Use the installed campaign command for campaign workflows and cache-failure
recovery. The former `compute/slurm/resume.py` command remains a compatibility
adapter; recovery policy and provenance validation live in `experiments`.

```bash
uv run thesis-campaign --help
uv run thesis-campaign recover-cache --campaign-dir outputs/gpu_campaigns/<campaign-id>
```

Recovery validates the campaign fingerprint, attempt logs, provenance, and
checkpoint hashes before changing resumable state. It preserves prior
manifests and recovery reports as immutable backups.

---

## Ablation matrix + OOS cost sensitivity

Locked OOS dates are **final report only** for architecture selection
([validation_protocol.md](../thesis/validation_protocol.md)). Ablation JSON
includes `oos_role: final_report_only` unless
`--allow-locked-oos-for-selection` is passed.

```bash
# Declarative variant matrix (algo / arch / VAE / PD-context / strategy).
# Features CSV must match the variant flags (e.g. include_pd_context).
uv run thesis-campaign variants \
    --bars-csv data/us100_2025.csv \
    --features-csv data/us100_feat.csv \
    --experiments config/experiments.yaml \
    --steps 8192 --seeds 42 \
    --variants ablation_baseline_unconditional ablation_pd_context

# Inspect the named-cache rebuild plan without writing caches.
uv run thesis-campaign rebuild-named-cache --plan-only

uv run python scripts/research/thesis/evaluation/report_ablations.py --ablations-dir outputs/ablations

# Cost-sensitivity grid on a saved SB3 zip (CostModel spread_points + slippage).
# --cost-multipliers scales both (TI-7); default 0.5 1 2 3.
uv run python scripts/research/thesis/evaluation/test_oos.py \
    --model-path outputs/<run>/model/ppo_final.zip \
    --bars-csv data/us100_2025.csv \
    --features-csv data/us100_feat.csv \
    --algo ppo \
    --spreads 0.6 1.0 1.5 \
    --slippages 0.0 0.1 0.2 \
    --cost-multipliers 0.5 1.0 2.0 3.0 \
    --out outputs/reports/oos_report.json

# Leak detectors (label-shuffle + time-shift)
uv run python scripts/research/audits/leak_detectors.py \
    --features-csv data/us100_feat.csv \
    --target-col ret_1 --feature-col rsi \
    --out outputs/research/leak_detectors.json

# Thin orchestration (ablation smoke → walk-forward → optional OOS)
BARS_CSV=data/us100_2025.csv STEPS=8192 SEEDS=42 \
  MODEL_PATH=outputs/<run>/model/ppo_final.zip \
  bash scripts/compute/slurm/campaigns/run_18variant_matrix.sh
```

Do **not** use the retired validation package or
`scripts/run_walk_forward.py` from old feature branches — walk-forward lives on
`thesis-train train --walk-forward`.

---

## Run-report gate (G3)

```bash
uv run python scripts/research/thesis/evaluation/report_g3.py --runs-dir outputs --sharpe-threshold 1.0
```

---

## Live / paper trading

### RL agent (`live_trading_rl.py`)

```bash
# One dry-run cycle (PAPER_TRADING defaults to true)
PAPER_TRADING=true RL_MODEL_PATH=outputs/<run>/model/ppo_final \
    python live_trading_rl.py --once

# Continuous paper loop
PAPER_TRADING=true RL_MODEL_PATH=outputs/<run>/model/ppo_final python live_trading_rl.py

# Real orders — only after DEPLOYMENT.md criteria pass
PAPER_TRADING=false RL_MODEL_PATH=outputs/<run>/model/ppo_final python live_trading_rl.py
```

Live risk inputs come from the run's saved `live_risk_overrides` (or the
repository defaults when the block is absent). Invalid values fail startup;
when the broker cannot produce a valid risk-sized volume, the robot skips the
entry instead of substituting a fixed lot size. Paper mode remains the default.

### Rule-based baseline (`live_trading.py`)

```bash
PAPER_TRADING=true STRATEGY_TYPE=combined python live_trading.py --once
# STRATEGY_TYPE: crossover | smc | trend_breakout | combined
```

The root script is a compatibility entrypoint for
`integrations/mt5/cli/multi_symbol_trading.py`. `--once` runs one cycle and
exits; without it, the application runs an immediate cycle and starts the
configured recurring schedule. The analogous `demo_trading.py --once` command
is provided by `integrations/mt5/cli/single_symbol_demo.py`.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the paper-to-live promotion protocol.

---

## Orchestra (multi-model pipeline)

```bash
orchestra doctor              # Tier-0 health check (no inference)
orchestra run "task description"   # full pipeline (verify runs CI gate)
```

See [orchestra/README.md](../../orchestra/README.md).

---

## Troubleshooting

```bash
# Rebuild feature cache
uv run thesis-train backtest --force
rm -rf cache/*.parquet

# Reduce MVP memory / time
uv run thesis-train train --mvp env.obs_window=30 \
    training.total_timesteps_mvp=4096
```

---

## Quick reference

| Command | Purpose | Typical time |
|---------|---------|--------------|
| `./tools/check full` | Local merge gate | varies by host |
| `./tools/check quality` | Full-tree Ruff + Mypy | varies by host |
| `run_baselines --strategy macd` | MACD baseline | ~10 s |
| `uv run thesis-train train --mvp` | RL smoke test | varies by host |
| `uv run thesis-train train` | Full RL training | campaign-specific |
| `eval_run --run outputs/...` | Re-evaluate checkpoint | ~1 min |
| `orchestra run "task"` | Multi-model pipeline | varies |

For provenance and command validity, see [reproducibility](../reproducibility.md).
