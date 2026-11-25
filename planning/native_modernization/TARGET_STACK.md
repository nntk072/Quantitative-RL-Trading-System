# Target technology stack, with status

Source: ARCHITECTURE_MODERNIZATION_PLAN.md sections 1, 2 and 3. Status meanings:
- **Decided**: the plan commits to it, and the repository already uses it or a package is built on it.
- **Conditional**: adopt only after a named measurement or trial shows the need (see the trial in the table).
- **Later**: production or product stage, not needed for offline completion.

| Layer | Technology | Status | Condition or note |
|---|---|---|---|
| Trading and simulation | Rust (native crates under native/) | Decided, engine pending | ENGINE-REUSE-TRIAL chooses between the native engine and NautilusTrader (or hftbacktest as a comparator). The native engine is the default if no engine passes the trial. |
| CPU parallelism | Rayon, bounded pool | Decided | Bounded pool per process. SIMD is not planned. Add it only after a profile shows a hot loop that benefits (PERFORMANCE-BASELINE). |
| Python integration | PyO3, maturin | Decided | Already built: native/python, CPU wheel for x86_64. aarch64 pending (GH200 allocation). |
| Data processing | Polars, PyArrow | Decided | Polars for tested ETL and resampling. PyArrow for schemas and Parquet interchange. Already used: market_data/arrow_schemas.py. |
| Historical storage | Parquet | Decided | Partitioned, immutable. DATA-INGESTION (offline part) pending. |
| Training memory | Shared arrays, memory mapping | Decided | Read-only mmap for DatasetView (SHARED-DATA-ABI). Measured per allocation. |
| Analytical database | DuckDB | Decided | Read model over manifest-resolved Parquet. One writer. Never in the environment step. DATA-QUERY. |
| Transactional database | PostgreSQL, Alembic | Conditional | Only when a concurrent multi-user control plane is needed (PRODUCTION-CONTROL-PLANE). Not needed for offline work. |
| Machine learning | PyTorch | Decided | Retained. TorchRL is a test alternative, not a replacement. JAX is an optional benchmark reference only. |
| GPU optimization | CUDA graphs, Triton, torch.compile | Conditional | Each one only after profiling shows the bottleneck and the static-shape or numerical conditions hold (LEARNER-OPTIMIZATION). |
| Experiment management | Existing framework, extended | Decided | experiments/, config/variant_catalog.yaml, artifacts/. Optuna only if a predeclared training-only search needs it. MLflow only as an optional read-only adapter. Ray and Dask deferred. |
| HPC orchestration | Existing Slurm infrastructure | Decided | compute/slurm; one persistent worker per allocation; no second scheduler. |
| Live networking | Rust, Tokio | Later | LIVE-CONTRACT. Mock and paper mode only until owner approval. |
| Statistical analysis | Python, SciPy, NumPy, SQL (DuckDB) | Decided | RESEARCH-STATISTICS. No custom inference where a library exists. |
| Testing and proof | Hypothesis (Python), proptest (Rust), criterion (Rust benchmarks) | Decided | Property and differential tests. Mutation checks with the existing tooling. |
| Profiling | py-spy, memray, flamegraph | Decided | Profiler output is kept separate from uninstrumented timings. |
| Monitoring | OpenTelemetry, Prometheus, Grafana | Later | Offline optional export first. Never per-tick remote logging. OPERABILITY. |
| Application | FastAPI (API), Next.js or React with TypeScript, TradingView Lightweight Charts | Later | Localhost first. No public deployment without owner approval. FINAL-PRODUCT-APPLICATION. |
| Deployment | Local first; containers (Docker or Podman) locally; Apptainer on HPC | Decided for local, Later for cloud | No Kubernetes by default. Infrastructure-as-code only when cloud deployment is needed. |
