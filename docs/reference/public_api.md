# Public Python API inventory

This file is generated from production ``__all__`` declarations and the source definitions
they re-export. Do not edit it by hand. Regenerate it with ``python -m
tools.documentation.public_api --write``.

Package initializers define stable public boundaries. Names exported from individual
modules are recorded as cross-package internal contracts in the companion JSON file.
Compatibility names and experimental exports remain labeled explicitly.

| Classification | Exported names |
|---|---:|
| stable | 710 |
| experimental | 0 |
| compatibility-only | 10 |
| cross-package internal | 448 |
| private implementation | 972 |

## Public package exports

### `artifacts`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `ArtifactId` | class | [artifacts.identity](../../artifacts/identity.py#L11) | stable |
| `ArtifactLayout` | class | [artifacts.layout](../../artifacts/layout.py#L27) | stable |
| `ArtifactManifest` | class | [artifacts.manifest](../../artifacts/manifest.py#L14) | stable |
| `BaselineValidation` | class | [artifacts.promotion](../../artifacts/promotion.py#L18) | stable |
| `ExperimentRunArtifactLayout` | class | [artifacts.layout](../../artifacts/layout.py#L129) | stable |
| `RetentionClass` | class | [artifacts.retention](../../artifacts/retention.py#L6) | stable |
| `artifact_id` | function | [artifacts.identity](../../artifacts/identity.py#L31) | stable |
| `file_sha256` | function | [artifacts.identity](../../artifacts/identity.py#L47) | stable |
| `promote_to_baseline` | function | [artifacts.promotion](../../artifacts/promotion.py#L99) | stable |
| `write_config_snapshot` | function | [artifacts.config_snapshot](../../artifacts/config_snapshot.py#L13) | stable |
| `write_json_atomic` | function | [artifacts.atomic](../../artifacts/atomic.py#L75) | stable |
| `write_text_atomic` | function | [artifacts.atomic](../../artifacts/atomic.py#L41) | stable |
| `ArtifactLayout.evaluation` | method | [artifacts.layout](../../artifacts/layout.py#L100) | stable |
| `ArtifactLayout.experiment_run` | method | [artifacts.layout](../../artifacts/layout.py#L74) | stable |
| `ArtifactLayout.experiment_runs` | method | [artifacts.layout](../../artifacts/layout.py#L66) | stable |
| `ArtifactLayout.gpu_experiment_run` | method | [artifacts.layout](../../artifacts/layout.py#L87) | stable |
| `ArtifactLayout.reports` | method | [artifacts.layout](../../artifacts/layout.py#L119) | stable |
| `ArtifactLayout.research` | method | [artifacts.layout](../../artifacts/layout.py#L111) | stable |
| `ArtifactLayout.run` | method | [artifacts.layout](../../artifacts/layout.py#L40) | stable |
| `ArtifactLayout.runs` | method | [artifacts.layout](../../artifacts/layout.py#L32) | stable |
| `ArtifactLayout.timestamped_run` | method | [artifacts.layout](../../artifacts/layout.py#L51) | stable |
| `ExperimentRunArtifactLayout.attempt` | method | [artifacts.layout](../../artifacts/layout.py#L271) | stable |
| `ExperimentRunArtifactLayout.bootstrap_checkpoint` | method | [artifacts.layout](../../artifacts/layout.py#L309) | stable |
| `ExperimentRunArtifactLayout.completion_marker` | method | [artifacts.layout](../../artifacts/layout.py#L297) | stable |
| `ExperimentRunArtifactLayout.controller_lock` | method | [artifacts.layout](../../artifacts/layout.py#L144) | stable |
| `ExperimentRunArtifactLayout.ensure_controller_directories` | method | [artifacts.layout](../../artifacts/layout.py#L355) | stable |
| `ExperimentRunArtifactLayout.failure_logs` | method | [artifacts.layout](../../artifacts/layout.py#L171) | stable |
| `ExperimentRunArtifactLayout.log` | method | [artifacts.layout](../../artifacts/layout.py#L246) | stable |
| `ExperimentRunArtifactLayout.logs` | method | [artifacts.layout](../../artifacts/layout.py#L153) | stable |
| `ExperimentRunArtifactLayout.manifest` | method | [artifacts.layout](../../artifacts/layout.py#L135) | stable |
| `ExperimentRunArtifactLayout.markers` | method | [artifacts.layout](../../artifacts/layout.py#L189) | stable |
| `ExperimentRunArtifactLayout.queue` | method | [artifacts.layout](../../artifacts/layout.py#L216) | stable |
| `ExperimentRunArtifactLayout.recovery_checkpoint` | method | [artifacts.layout](../../artifacts/layout.py#L339) | stable |
| `ExperimentRunArtifactLayout.report` | method | [artifacts.layout](../../artifacts/layout.py#L224) | stable |
| `ExperimentRunArtifactLayout.reports` | method | [artifacts.layout](../../artifacts/layout.py#L198) | stable |
| `ExperimentRunArtifactLayout.resolve_recorded_path` | method | [artifacts.layout](../../artifacts/layout.py#L321) | stable |
| `ExperimentRunArtifactLayout.root_file` | method | [artifacts.layout](../../artifacts/layout.py#L235) | stable |
| `ExperimentRunArtifactLayout.run_attempts` | method | [artifacts.layout](../../artifacts/layout.py#L285) | stable |
| `ExperimentRunArtifactLayout.runs` | method | [artifacts.layout](../../artifacts/layout.py#L180) | stable |
| `ExperimentRunArtifactLayout.source_snapshot` | method | [artifacts.layout](../../artifacts/layout.py#L207) | stable |
| `ExperimentRunArtifactLayout.worker_log` | method | [artifacts.layout](../../artifacts/layout.py#L257) | stable |
| `ExperimentRunArtifactLayout.worker_logs` | method | [artifacts.layout](../../artifacts/layout.py#L162) | stable |
| `ArtifactManifest.read` | method | [artifacts.manifest](../../artifacts/manifest.py#L61) | stable |
| `ArtifactManifest.to_dict` | method | [artifacts.manifest](../../artifacts/manifest.py#L50) | stable |
| `BaselineValidation.to_dict` | method | [artifacts.promotion](../../artifacts/promotion.py#L31) | stable |

### `compute`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `configure_accelerator_for_training` | function | [compute.environment.precision](../../compute/environment/precision.py#L76) | stable |
| `configure_cuda_for_training` | function | [compute.environment.precision](../../compute/environment/precision.py#L105) | stable |
| `discover_device_capabilities` | function | [compute.environment.capabilities](../../compute/environment/capabilities.py#L12) | stable |
| `get_autocast_context` | function | [compute.environment.precision](../../compute/environment/precision.py#L51) | stable |
| `get_autocast_dtype` | function | [compute.environment.precision](../../compute/environment/precision.py#L31) | stable |
| `get_device` | function | [compute.environment.device](../../compute/environment/device.py#L31) | stable |
| `scale_training_cfg` | function | [compute.environment.device](../../compute/environment/device.py#L174) | stable |

### `configuration`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `CURRENT_CONFIG_SCHEMA_VERSION` | value | [configuration.schema](../../configuration/schema.py#L6) | stable |
| `ConfigSchemaError` | class | [configuration.schema](../../configuration/schema.py#L9) | stable |
| `RepositoryPaths` | class | [configuration.paths](../../configuration/paths.py#L8) | stable |
| `apply_overrides` | function | [configuration.configuration_loader](../../configuration/configuration_loader.py#L81) | stable |
| `config_sha256` | function | [configuration.hashing](../../configuration/hashing.py#L23) | stable |
| `load_config` | function | [configuration.configuration_loader](../../configuration/configuration_loader.py#L18) | stable |
| `load_config_overlay` | function | [configuration.configuration_loader](../../configuration/configuration_loader.py#L42) | stable |
| `merge_config_overlay` | function | [configuration.configuration_loader](../../configuration/configuration_loader.py#L57) | stable |
| `RepositoryPaths.from_root` | method | [configuration.paths](../../configuration/paths.py#L30) | stable |

### `decisioning`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `ActionSchema` | class | [decisioning.actions](../../decisioning/actions.py#L94) | stable |
| `ActionSchemaRef` | class | [decisioning.contracts](../../decisioning/contracts.py#L15) | stable |
| `BASE_ACCOUNT_DIM` | value | [decisioning.observation_state](../../decisioning/observation_state.py#L8) | stable |
| `CANDIDATE_GEOMETRY_ENTRY_TYPES` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L15) | stable |
| `CANDIDATE_GEOMETRY_FEATURE_NAMES` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L16) | stable |
| `CANDIDATE_GEOMETRY_FEATURE_VERSION` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L14) | stable |
| `CANDIDATE_GEOMETRY_OBSERVATION_VERSION` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L13) | stable |
| `ContinuousAction` | class | [decisioning.contracts](../../decisioning/contracts.py#L41) | stable |
| `Decision` | class | [decisioning.contracts](../../decisioning/contracts.py#L58) | stable |
| `DecisionArtifactRef` | class | [decisioning.contracts](../../decisioning/contracts.py#L77) | stable |
| `DecisionInput` | class | [decisioning.contracts](../../decisioning/contracts.py#L25) | stable |
| `DecisionProvider` | class | [decisioning.contracts](../../decisioning/contracts.py#L85) | stable |
| `DiscreteAction` | class | [decisioning.contracts](../../decisioning/contracts.py#L33) | stable |
| `DiscreteActionSchema` | class | [decisioning.actions](../../decisioning/actions.py#L22) | stable |
| `ENTRY_STATES` | value | [decisioning.observation_state](../../decisioning/observation_state.py#L9) | stable |
| `ENTRY_STATE_DIM` | value | [decisioning.observation_state](../../decisioning/observation_state.py#L10) | stable |
| `NO_TRADE_ID` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L45) | stable |
| `OBSERVATION_SCHEMA_REPEATED_PAYOUT` | value | [decisioning.observations](../../decisioning/observations.py#L110) | stable |
| `ObservationSchema` | class | [decisioning.observations](../../decisioning/observations.py#L155) | stable |
| `PredictorMetadata` | class | [decisioning.contracts](../../decisioning/contracts.py#L66) | stable |
| `StructuredAction` | class | [decisioning.contracts](../../decisioning/contracts.py#L48) | stable |
| `TRADE_SETUP_ACTION_VERSION` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L11) | stable |
| `TRADE_SETUP_CANDIDATES` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L494) | stable |
| `TRADE_SETUP_CATEGORY_COUNT` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L495) | stable |
| `TRADE_SETUP_DIRECTIONS` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L44) | stable |
| `TRADE_SETUP_EXECUTION_ACTION_VERSION` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L12) | stable |
| `TRADE_SETUP_IDEAS` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L35) | stable |
| `TRADE_SETUP_OBSERVATION_VERSION` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L10) | stable |
| `TRADE_SETUP_SCHEMA_VERSION` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L9) | stable |
| `TRADE_SETUP_TIMEFRAMES` | value | [decisioning.trade_setup](../../decisioning/trade_setup.py#L43) | stable |
| `TradeSetupActionSchema` | class | [decisioning.trade_setup](../../decisioning/trade_setup.py#L202) | stable |
| `TradeSetupCandidate` | class | [decisioning.trade_setup](../../decisioning/trade_setup.py#L157) | stable |
| `TradeSetupExecutionChoice` | class | [decisioning.trade_setup](../../decisioning/trade_setup.py#L176) | stable |
| `TradeSetupGeometryChoice` | class | [decisioning.trade_setup](../../decisioning/trade_setup.py#L185) | stable |
| `build_action_schema` | function | [decisioning.actions](../../decisioning/actions.py#L185) | stable |
| `build_action_schema_from_config` | function | [decisioning.actions](../../decisioning/actions.py#L229) | stable |
| `build_discrete_trading_action_schema` | function | [decisioning.actions](../../decisioning/actions.py#L67) | stable |
| `build_observation_schema` | function | [decisioning.observations](../../decisioning/observations.py#L185) | stable |
| `build_trade_setup_action_schema` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L290) | stable |
| `candidate_geometry_observation_schema` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L103) | stable |
| `candidate_geometry_slot` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L48) | stable |
| `candidate_geometry_slot_count` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L75) | stable |
| `candidate_geometry_slot_semantics` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L85) | stable |
| `decode_trade_setup_execution_choice` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L338) | stable |
| `decode_trade_setup_geometry_choice` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L387) | stable |
| `entry_state_one_hot` | function | [decisioning.observation_state](../../decisioning/observation_state.py#L13) | stable |
| `normalized_account_vector` | function | [decisioning.observations](../../decisioning/observations.py#L51) | stable |
| `pad_observation_window` | function | [decisioning.observations](../../decisioning/observations.py#L17) | stable |
| `requires_normalized_account_observation` | function | [decisioning.observations](../../decisioning/observations.py#L228) | stable |
| `to_policy_action` | function | [decisioning.contracts](../../decisioning/contracts.py#L110) | stable |
| `trade_setup_candidate` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L501) | stable |
| `trade_setup_candidate_id` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L517) | stable |
| `trade_setup_center` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L536) | stable |
| `trade_setup_id_from_box` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L549) | stable |
| `trade_setup_observation_schema` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L567) | stable |
| `validate_candidate_geometry_observation_schema` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L613) | stable |
| `validate_trade_setup_observation_schema` | function | [decisioning.trade_setup](../../decisioning/trade_setup.py#L598) | stable |
| `ActionSchema.indices` | method | [decisioning.actions](../../decisioning/actions.py#L125) | stable |
| `ActionSchema.key` | method | [decisioning.actions](../../decisioning/actions.py#L137) | stable |
| `ActionSchema.to_dict` | method | [decisioning.actions](../../decisioning/actions.py#L166) | stable |
| `ActionSchema.width` | method | [decisioning.actions](../../decisioning/actions.py#L116) | stable |
| `DiscreteActionSchema.key` | method | [decisioning.actions](../../decisioning/actions.py#L38) | stable |
| `DiscreteActionSchema.to_dict` | method | [decisioning.actions](../../decisioning/actions.py#L46) | stable |
| `DiscreteActionSchema.width` | method | [decisioning.actions](../../decisioning/actions.py#L29) | stable |
| `DecisionProvider.metadata` | method | [decisioning.contracts](../../decisioning/contracts.py#L89) | stable |
| `DecisionProvider.predict` | method | [decisioning.contracts](../../decisioning/contracts.py#L97) | stable |
| `ObservationSchema.to_dict` | method | [decisioning.observations](../../decisioning/observations.py#L171) | stable |
| `ObservationSchema.width` | method | [decisioning.observations](../../decisioning/observations.py#L163) | stable |
| `TradeSetupActionSchema.indices` | method | [decisioning.trade_setup](../../decisioning/trade_setup.py#L223) | stable |
| `TradeSetupActionSchema.key` | method | [decisioning.trade_setup](../../decisioning/trade_setup.py#L235) | stable |
| `TradeSetupActionSchema.to_dict` | method | [decisioning.trade_setup](../../decisioning/trade_setup.py#L243) | stable |
| `TradeSetupActionSchema.width` | method | [decisioning.trade_setup](../../decisioning/trade_setup.py#L214) | stable |
| `TradeSetupCandidate.is_no_trade` | method | [decisioning.trade_setup](../../decisioning/trade_setup.py#L166) | stable |

### `evaluation`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `AlwaysNoTradePolicy` | class | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L207) | stable |
| `AlwaysNoTradeRolloutModel` | class | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L252) | stable |
| `CI` | class | [evaluation.metrics.bootstrap](../../evaluation/metrics/bootstrap.py#L62) | stable |
| `CalibrationReport` | class | [evaluation.metrics.calibration](../../evaluation/metrics/calibration.py#L22) | stable |
| `DEFAULT_PERIODS_PER_YEAR` | value | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L18) | stable |
| `DistributionMetrics` | class | [evaluation.metrics.distributions](../../evaluation/metrics/distributions.py#L31) | stable |
| `LEGACY_M1_PERIODS_PER_YEAR` | value | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L756) | compatibility-only |
| `PerformanceMetrics` | class | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L54) | stable |
| `RandomEligibleSetupPolicy` | class | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L17) | stable |
| `RandomEligibleSetupRolloutModel` | class | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L142) | stable |
| `WFSplit` | class | [market_data.splits.walkforward](../../market_data/splits/walkforward.py#L23) | stable |
| `account_path_metric_inputs` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L785) | stable |
| `aggregate_seeds` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L60) | stable |
| `bootstrap_ci` | function | [evaluation.metrics.bootstrap](../../evaluation/metrics/bootstrap.py#L79) | stable |
| `build_comparison_table` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L294) | stable |
| `build_run_report` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L359) | stable |
| `build_summary_table` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L273) | stable |
| `calculate_metrics` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L814) | stable |
| `calibration_report` | function | [evaluation.metrics.calibration](../../evaluation/metrics/calibration.py#L43) | stable |
| `compute_distribution_metrics` | function | [evaluation.metrics.distributions](../../evaluation/metrics/distributions.py#L56) | stable |
| `compute_metrics` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L553) | stable |
| `conditional_pnl_distributions` | function | [evaluation.metrics.temporal](../../evaluation/metrics/temporal.py#L157) | stable |
| `conditional_pnl_groups` | function | [evaluation.metrics.temporal](../../evaluation/metrics/temporal.py#L136) | stable |
| `evaluate_provider` | function | [evaluation.rollout.trained_policy_rollout](../../evaluation/rollout/trained_policy_rollout.py#L1110) | stable |
| `evaluation_periods_per_year` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L759) | stable |
| `holding_time_distribution` | function | [evaluation.metrics.temporal](../../evaluation/metrics/temporal.py#L63) | stable |
| `max_drawdown` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L450) | stable |
| `plot_reliability_diagram` | function | [evaluation.metrics.calibration](../../evaluation/metrics/calibration.py#L97) | stable |
| `print_report` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L88) | stable |
| `purged_walk_forward` | function | [market_data.splits.walkforward](../../market_data/splits/walkforward.py#L37) | stable |
| `run_episode` | function | [evaluation.rollout.episode_rollout](../../evaluation/rollout/episode_rollout.py#L26) | stable |
| `save_metrics_json` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L336) | stable |
| `sharpe_stat` | function | [evaluation.metrics.bootstrap](../../evaluation/metrics/bootstrap.py#L188) | stable |
| `sweep_delay_breakdown` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L217) | stable |
| `sweep_delay_distribution` | function | [evaluation.metrics.temporal](../../evaluation/metrics/temporal.py#L88) | stable |
| `DEFAULT_PERIODS_PER_YEAR` | value | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L18) | stable |
| `LEGACY_M1_PERIODS_PER_YEAR` | value | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L756) | compatibility-only |
| `LIMIT_EXECUTION_SENSITIVITY_SCHEMA` | value | [evaluation.metrics.limit_execution_sensitivity](../../evaluation/metrics/limit_execution_sensitivity.py#L11) | stable |
| `PerformanceMetrics` | class | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L54) | stable |
| `account_path_metric_inputs` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L785) | stable |
| `calculate_metrics` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L814) | stable |
| `compare_limit_execution_sensitivity` | function | [evaluation.metrics.limit_execution_sensitivity](../../evaluation/metrics/limit_execution_sensitivity.py#L301) | stable |
| `compute_metrics` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L553) | stable |
| `evaluation_periods_per_year` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L759) | stable |
| `max_drawdown` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L450) | stable |
| `sweep_delay_breakdown` | function | [evaluation.metrics.performance](../../evaluation/metrics/performance.py#L217) | stable |
| `CI.as_tuple` | method | [evaluation.metrics.bootstrap](../../evaluation/metrics/bootstrap.py#L70) | stable |
| `CalibrationReport.summary` | method | [evaluation.metrics.calibration](../../evaluation/metrics/calibration.py#L31) | stable |
| `plot_drawdown` | function | [evaluation.plotting.equity](../../evaluation/plotting/equity.py#L245) | stable |
| `plot_equity_curve` | function | [evaluation.plotting.equity](../../evaluation/plotting/equity.py#L41) | stable |
| `plot_per_trade_orders` | function | [evaluation.plotting.orders](../../evaluation/plotting/orders.py#L626) | stable |
| `plot_per_trade_orders_html (alias for plot_per_trade_orders)` | function | [evaluation.plotting.interactive_orders](../../evaluation/plotting/interactive_orders.py#L217) | stable |
| `plot_price_with_orders` | function | [evaluation.plotting.orders](../../evaluation/plotting/orders.py#L37) | stable |
| `main` | function | [evaluation.reanalysis](../../evaluation/reanalysis/__init__.py#L1) | stable |
| `aggregate_seeds` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L60) | stable |
| `build_comparison_table` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L294) | stable |
| `build_evaluation_manifest` | function | [evaluation.reporting.evaluation_manifest](../../evaluation/reporting/evaluation_manifest.py#L14) | stable |
| `build_run_report` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L359) | stable |
| `build_summary_table` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L273) | stable |
| `print_report` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L88) | stable |
| `save_metrics_json` | function | [evaluation.reporting.run_summary](../../evaluation/reporting/run_summary.py#L336) | stable |
| `save_run` | function | [evaluation.reporting.run_artifact_writer](../../evaluation/reporting/run_artifact_writer.py#L850) | stable |
| `write_evaluation_manifest` | function | [evaluation.reporting.evaluation_manifest](../../evaluation/reporting/evaluation_manifest.py#L74) | stable |
| `AlwaysNoTradePolicy` | class | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L207) | stable |
| `AlwaysNoTradeRolloutModel` | class | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L252) | stable |
| `RandomEligibleSetupPolicy` | class | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L17) | stable |
| `RandomEligibleSetupRolloutModel` | class | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L142) | stable |
| `StructurePrioritySetupPolicy` | class | [evaluation.rollout.structure_priority_setup](../../evaluation/rollout/structure_priority_setup.py#L21) | stable |
| `StructurePrioritySetupRolloutModel` | class | [evaluation.rollout.structure_priority_setup](../../evaluation/rollout/structure_priority_setup.py#L161) | stable |
| `discrete_actions_for_position_targets` | function | [evaluation.rollout.baseline_signal_actions](../../evaluation/rollout/baseline_signal_actions.py#L11) | stable |
| `evaluate_model` | function | [evaluation.rollout.trained_policy_rollout](../../evaluation/rollout/trained_policy_rollout.py#L290) | stable |
| `evaluate_provider` | function | [evaluation.rollout.trained_policy_rollout](../../evaluation/rollout/trained_policy_rollout.py#L1110) | stable |
| `make_action_fn` | function | [evaluation.rollout.trained_policy_rollout](../../evaluation/rollout/trained_policy_rollout.py#L231) | stable |
| `run_episode` | function | [evaluation.rollout.episode_rollout](../../evaluation/rollout/episode_rollout.py#L26) | stable |
| `AlwaysNoTradePolicy.metadata` | method | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L232) | stable |
| `RandomEligibleSetupPolicy.metadata` | method | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L109) | stable |
| `RandomEligibleSetupRolloutModel.hybrid_action_coordinates` | method | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L168) | stable |
| `RandomEligibleSetupRolloutModel.policy` | method | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L159) | stable |
| `RandomEligibleSetupRolloutModel.policy_metadata` | method | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L177) | stable |
| `RandomEligibleSetupRolloutModel.predict` | method | [evaluation.rollout.random_eligible_setup](../../evaluation/rollout/random_eligible_setup.py#L185) | stable |
| `StructurePrioritySetupPolicy.metadata` | method | [evaluation.rollout.structure_priority_setup](../../evaluation/rollout/structure_priority_setup.py#L130) | stable |
| `StructurePrioritySetupRolloutModel.hybrid_action_coordinates` | method | [evaluation.rollout.structure_priority_setup](../../evaluation/rollout/structure_priority_setup.py#L182) | stable |
| `StructurePrioritySetupRolloutModel.policy` | method | [evaluation.rollout.structure_priority_setup](../../evaluation/rollout/structure_priority_setup.py#L173) | stable |
| `StructurePrioritySetupRolloutModel.policy_metadata` | method | [evaluation.rollout.structure_priority_setup](../../evaluation/rollout/structure_priority_setup.py#L191) | stable |
| `StructurePrioritySetupRolloutModel.predict` | method | [evaluation.rollout.structure_priority_setup](../../evaluation/rollout/structure_priority_setup.py#L199) | stable |

### `experiments`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `BatchSpec` | class | [experiments.orchestration.weekly](../../experiments/orchestration/weekly.py#L21) | stable |
| `RunSpec` | class | [experiments.orchestration.weekly](../../experiments/orchestration/weekly.py#L36) | stable |
| `WeeklyOrchestrator` | class | [experiments.orchestration.weekly](../../experiments/orchestration/weekly.py#L167) | stable |
| `render_batch_report` | function | [experiments.orchestration.weekly](../../experiments/orchestration/weekly.py#L105) | stable |
| `render_weekly_report` | function | [experiments.orchestration.weekly](../../experiments/orchestration/weekly.py#L130) | stable |
| `WeeklyOrchestrator.run_week` | method | [experiments.orchestration.weekly](../../experiments/orchestration/weekly.py#L175) | stable |
| `run_experiment` | function | [experiments.runs](../../experiments/runs/__init__.py#L6) | stable |

### `features`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `FEATURE_CACHE_VERSION` | value | [features.pipeline.feature_cache_identity](../../features/pipeline/feature_cache_identity.py#L17) | stable |
| `InputKind` | value | [features.contracts](../../features/contracts.py#L9) | stable |
| `InputSchema` | class | [features.contracts](../../features/contracts.py#L13) | stable |
| `InputView` | class | [features.contracts](../../features/contracts.py#L35) | stable |
| `OBS_RAW_PRICE_COLUMNS` | value | [features.pipeline.schema](../../features/pipeline/schema.py#L122) | stable |
| `attach_reachable_r` | function | [features.context.reachability](../../features/context/reachability.py#L161) | stable |
| `build_features` | function | [features.pipeline.feature_matrix_builder](../../features/pipeline/feature_matrix_builder.py#L153) | stable |
| `build_fvg_zone_features` | function | [features.po3.fvg](../../features/po3/fvg.py#L28) | stable |
| `build_po3_phase_features` | function | [features.po3.entries](../../features/po3/entries.py#L11) | stable |
| `build_walkforward_fold_features` | function | [features.pipeline.walkforward_feature_fitting](../../features/pipeline/walkforward_feature_fitting.py#L13) | stable |
| `ensure_london_atr_distances` | function | [features.pipeline.session_context_features](../../features/pipeline/session_context_features.py#L8) | stable |
| `feature_cache_content_hash` | function | [features.pipeline.feature_cache_identity](../../features/pipeline/feature_cache_identity.py#L20) | stable |
| `feature_cache_path` | function | [features.pipeline.feature_cache_identity](../../features/pipeline/feature_cache_identity.py#L151) | stable |
| `input_view_from_frame` | function | [features.input_view](../../features/input_view.py#L10) | stable |
| `select_legacy_obs_columns` | function | [features.pipeline.schema](../../features/pipeline/schema.py#L125) | compatibility-only |
| `select_obs_columns` | function | [features.pipeline.schema](../../features/pipeline/schema.py#L152) | stable |
| `attach_policy_market_context` | function | [features.context.policy_market](../../features/context/policy_market.py#L130) | stable |
| `attach_reachable_r` | function | [features.context.reachability](../../features/context/reachability.py#L161) | stable |
| `max_tp_distance` | function | [features.context.reachability](../../features/context/reachability.py#L17) | stable |
| `reachable_r_series` | function | [features.context.reachability](../../features/context/reachability.py#L144) | stable |
| `rr_reaches` | function | [features.context.reachability](../../features/context/reachability.py#L187) | stable |
| `FEATURE_CACHE_VERSION` | value | [features.pipeline.feature_cache_identity](../../features/pipeline/feature_cache_identity.py#L17) | stable |
| `OBS_RAW_PRICE_COLUMNS` | value | [features.pipeline.schema](../../features/pipeline/schema.py#L122) | stable |
| `apply_rolling_zscore_state` | function | [features.pipeline.normalization](../../features/pipeline/normalization.py#L106) | stable |
| `attach_reachable_r` | function | [features.context.reachability](../../features/context/reachability.py#L161) | stable |
| `build_features` | function | [features.pipeline.feature_matrix_builder](../../features/pipeline/feature_matrix_builder.py#L153) | stable |
| `build_walkforward_fold_features` | function | [features.pipeline.walkforward_feature_fitting](../../features/pipeline/walkforward_feature_fitting.py#L13) | stable |
| `ensure_london_atr_distances` | function | [features.pipeline.session_context_features](../../features/pipeline/session_context_features.py#L8) | stable |
| `feature_cache_content_hash` | function | [features.pipeline.feature_cache_identity](../../features/pipeline/feature_cache_identity.py#L20) | stable |
| `feature_cache_path` | function | [features.pipeline.feature_cache_identity](../../features/pipeline/feature_cache_identity.py#L151) | stable |
| `fit_rolling_zscore_state` | function | [features.pipeline.normalization](../../features/pipeline/normalization.py#L40) | stable |
| `rolling_zscore` | function | [features.pipeline.normalization](../../features/pipeline/normalization.py#L158) | stable |
| `select_legacy_obs_columns` | function | [features.pipeline.schema](../../features/pipeline/schema.py#L125) | compatibility-only |
| `select_obs_columns` | function | [features.pipeline.schema](../../features/pipeline/schema.py#L152) | stable |
| `EntryConfig` | class | [features.po3.trigger_rules](../../features/po3/trigger_rules.py#L16) | stable |
| `EntryTriggerType` | value | [features.po3.trigger_rules](../../features/po3/trigger_rules.py#L12) | stable |
| `FVGConfig` | class | [features.po3.fvg_detection](../../features/po3/fvg_detection.py#L9) | stable |
| `FVGZone` | class | [features.po3.zones](../../features/po3/zones.py#L33) | stable |
| `IFVGConfig` | class | [features.po3.ifvg_detection](../../features/po3/ifvg_detection.py#L19) | stable |
| `build_fvg_zones` | function | [features.po3.zones](../../features/po3/zones.py#L58) | stable |
| `build_fvg_zones_for_plot` | function | [features.po3.zones](../../features/po3/zones.py#L177) | stable |
| `build_po3_ifvg_state` | function | [features.po3.ifvg_state](../../features/po3/ifvg_state.py#L9) | stable |
| `build_po3_setup_lifecycle_ledger` | function | [features.po3.setup_lifecycle](../../features/po3/setup_lifecycle.py#L82) | stable |
| `detect_entry_trigger` | function | [features.po3.trigger_rules](../../features/po3/trigger_rules.py#L31) | stable |
| `detect_fvg` | function | [features.po3.fvg_detection](../../features/po3/fvg_detection.py#L25) | stable |
| `detect_htf_fvg` | function | [features.po3.trigger_rules](../../features/po3/trigger_rules.py#L210) | stable |
| `detect_ifvg_confirmation` | function | [features.po3.ifvg_detection](../../features/po3/ifvg_detection.py#L251) | stable |
| `detect_ltf_ifvg` | function | [features.po3.trigger_rules](../../features/po3/trigger_rules.py#L289) | stable |
| `detect_po3_entries` | function | [features.po3.trigger_rules](../../features/po3/trigger_rules.py#L372) | stable |
| `atr` | function | [features.technical.indicators](../../features/technical/indicators.py#L109) | stable |
| `build_indicators` | function | [features.technical.indicators](../../features/technical/indicators.py#L468) | stable |
| `classify_structure` | function | [features.technical.swings](../../features/technical/swings.py#L222) | stable |
| `detect_pivots` | function | [features.technical.swings](../../features/technical/swings.py#L26) | stable |
| `detect_swings` | function | [features.technical.swings](../../features/technical/swings.py#L86) | stable |

### `integrations`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `MT5Data` | class | [integrations.mt5.domain.data_sources.mt5_data](../../integrations/mt5/domain/data_sources/mt5_data.py#L7) | stable |
| `MT5Trader` | class | [integrations.mt5.domain.trader](../../integrations/mt5/domain/trader.py#L8) | stable |
| `RiskManager` | class | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L10) | stable |
| `ensure_mt5_logged_in` | function | [integrations.mt5.domain.mt5_connection](../../integrations/mt5/domain/mt5_connection.py#L8) | stable |
| `Trader` | class | [integrations.mt5.adapters.trader](../../integrations/mt5/adapters/trader.py#L5) | stable |
| `TradingData` | class | [integrations.mt5.adapters.data](../../integrations/mt5/adapters/data.py#L6) | stable |
| `TradingStrategy` | class | [integrations.mt5.adapters.strategy](../../integrations/mt5/adapters/strategy.py#L10) | stable |
| `TradingData.get_data` | method | [integrations.mt5.adapters.data](../../integrations/mt5/adapters/data.py#L10) | stable |
| `TradingData.get_symbol` | method | [integrations.mt5.adapters.data](../../integrations/mt5/adapters/data.py#L19) | stable |
| `TradingStrategy.signal` | method | [integrations.mt5.adapters.strategy](../../integrations/mt5/adapters/strategy.py#L14) | stable |
| `Trader.calculate_position_size` | method | [integrations.mt5.adapters.trader](../../integrations/mt5/adapters/trader.py#L74) | stable |
| `Trader.close_positions` | method | [integrations.mt5.adapters.trader](../../integrations/mt5/adapters/trader.py#L22) | stable |
| `Trader.get_all_positions` | method | [integrations.mt5.adapters.trader](../../integrations/mt5/adapters/trader.py#L48) | stable |
| `Trader.get_opened_positions` | method | [integrations.mt5.adapters.trader](../../integrations/mt5/adapters/trader.py#L35) | stable |
| `Trader.open_position` | method | [integrations.mt5.adapters.trader](../../integrations/mt5/adapters/trader.py#L9) | stable |
| `Trader.send_to_break_even` | method | [integrations.mt5.adapters.trader](../../integrations/mt5/adapters/trader.py#L61) | stable |
| `CombinedStrategy` | class | [integrations.mt5.domain.strategies.combined_strategy](../../integrations/mt5/domain/strategies/combined_strategy.py#L10) | stable |
| `CrossOverStrategy` | class | [integrations.mt5.domain.strategies.cross_over_strategy](../../integrations/mt5/domain/strategies/cross_over_strategy.py#L8) | stable |
| `MT5Data` | class | [integrations.mt5.domain.data_sources.mt5_data](../../integrations/mt5/domain/data_sources/mt5_data.py#L7) | stable |
| `MT5Trader` | class | [integrations.mt5.domain.trader](../../integrations/mt5/domain/trader.py#L8) | stable |
| `MultiSymbolManager` | class | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L11) | stable |
| `RiskManager` | class | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L10) | stable |
| `SMCStrategy` | class | [integrations.mt5.domain.strategies.smc_strategy](../../integrations/mt5/domain/strategies/smc_strategy.py#L7) | stable |
| `TrendBreakoutStrategy` | class | [integrations.mt5.domain.strategies.trend_breakout_strategy](../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L9) | stable |
| `VolatilityAnalyzer` | class | [integrations.mt5.domain.volatility_analyzer](../../integrations/mt5/domain/volatility_analyzer.py#L11) | stable |
| `MT5Data.get_data` | method | [integrations.mt5.domain.data_sources.mt5_data](../../integrations/mt5/domain/data_sources/mt5_data.py#L25) | stable |
| `MT5Data.get_symbol` | method | [integrations.mt5.domain.data_sources.mt5_data](../../integrations/mt5/domain/data_sources/mt5_data.py#L37) | stable |
| `MultiSymbolManager.add_symbol` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L127) | stable |
| `MultiSymbolManager.get_active_symbols` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L193) | stable |
| `MultiSymbolManager.get_all_data_sources` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L86) | stable |
| `MultiSymbolManager.get_all_volatility_metrics` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L119) | stable |
| `MultiSymbolManager.get_data_source` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L75) | stable |
| `MultiSymbolManager.get_volatility_metrics` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L108) | stable |
| `MultiSymbolManager.refresh_data` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L183) | stable |
| `MultiSymbolManager.remove_symbol` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L158) | stable |
| `MultiSymbolManager.update_volatility_metrics` | method | [integrations.mt5.domain.multi_symbol_manager](../../integrations/mt5/domain/multi_symbol_manager.py#L94) | stable |
| `RiskManager.calculate_position_size` | method | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L267) | stable |
| `RiskManager.calculate_stop_loss_price` | method | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L394) | stable |
| `RiskManager.check_risk_limits` | method | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L546) | stable |
| `RiskManager.get_account_balance` | method | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L129) | stable |
| `RiskManager.get_account_equity` | method | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L149) | stable |
| `RiskManager.get_total_exposure` | method | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L435) | stable |
| `RiskManager.get_volatility_multiplier` | method | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L639) | stable |
| `RiskManager.supports_training_account_loss_guardrails` | method | [integrations.mt5.domain.risk_manager](../../integrations/mt5/domain/risk_manager.py#L18) | stable |
| `CombinedStrategy` | class | [integrations.mt5.domain.strategies.combined_strategy](../../integrations/mt5/domain/strategies/combined_strategy.py#L10) | stable |
| `CrossOverStrategy` | class | [integrations.mt5.domain.strategies.cross_over_strategy](../../integrations/mt5/domain/strategies/cross_over_strategy.py#L8) | stable |
| `SMCStrategy` | class | [integrations.mt5.domain.strategies.smc_strategy](../../integrations/mt5/domain/strategies/smc_strategy.py#L7) | stable |
| `TrendBreakoutStrategy` | class | [integrations.mt5.domain.strategies.trend_breakout_strategy](../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L9) | stable |
| `CombinedStrategy.signal` | method | [integrations.mt5.domain.strategies.combined_strategy](../../integrations/mt5/domain/strategies/combined_strategy.py#L51) | stable |
| `CrossOverStrategy.signal` | method | [integrations.mt5.domain.strategies.cross_over_strategy](../../integrations/mt5/domain/strategies/cross_over_strategy.py#L19) | stable |
| `SMCStrategy.identify_fair_value_gaps` | method | [integrations.mt5.domain.strategies.smc_strategy](../../integrations/mt5/domain/strategies/smc_strategy.py#L76) | stable |
| `SMCStrategy.identify_market_structure` | method | [integrations.mt5.domain.strategies.smc_strategy](../../integrations/mt5/domain/strategies/smc_strategy.py#L110) | stable |
| `SMCStrategy.identify_order_blocks` | method | [integrations.mt5.domain.strategies.smc_strategy](../../integrations/mt5/domain/strategies/smc_strategy.py#L31) | stable |
| `SMCStrategy.signal` | method | [integrations.mt5.domain.strategies.smc_strategy](../../integrations/mt5/domain/strategies/smc_strategy.py#L149) | stable |
| `TrendBreakoutStrategy.calculate_trend_strength` | method | [integrations.mt5.domain.strategies.trend_breakout_strategy](../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L140) | stable |
| `TrendBreakoutStrategy.calculate_volume_profile` | method | [integrations.mt5.domain.strategies.trend_breakout_strategy](../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L82) | stable |
| `TrendBreakoutStrategy.detect_breakout` | method | [integrations.mt5.domain.strategies.trend_breakout_strategy](../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L105) | stable |
| `TrendBreakoutStrategy.identify_consolidation` | method | [integrations.mt5.domain.strategies.trend_breakout_strategy](../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L58) | stable |
| `TrendBreakoutStrategy.identify_support_resistance` | method | [integrations.mt5.domain.strategies.trend_breakout_strategy](../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L36) | stable |
| `TrendBreakoutStrategy.signal` | method | [integrations.mt5.domain.strategies.trend_breakout_strategy](../../integrations/mt5/domain/strategies/trend_breakout_strategy.py#L158) | stable |
| `MT5Trader.calculate_position_size` | method | [integrations.mt5.domain.trader](../../integrations/mt5/domain/trader.py#L227) | stable |
| `MT5Trader.close_positions` | method | [integrations.mt5.domain.trader](../../integrations/mt5/domain/trader.py#L64) | stable |
| `MT5Trader.get_all_positions` | method | [integrations.mt5.domain.trader](../../integrations/mt5/domain/trader.py#L163) | stable |
| `MT5Trader.get_opened_positions` | method | [integrations.mt5.domain.trader](../../integrations/mt5/domain/trader.py#L129) | stable |
| `MT5Trader.open_position` | method | [integrations.mt5.domain.trader](../../integrations/mt5/domain/trader.py#L11) | stable |
| `MT5Trader.send_to_break_even` | method | [integrations.mt5.domain.trader](../../integrations/mt5/domain/trader.py#L178) | stable |
| `VolatilityAnalyzer.calculate_atr` | method | [integrations.mt5.domain.volatility_analyzer](../../integrations/mt5/domain/volatility_analyzer.py#L50) | stable |
| `VolatilityAnalyzer.calculate_volatility_metrics` | method | [integrations.mt5.domain.volatility_analyzer](../../integrations/mt5/domain/volatility_analyzer.py#L94) | stable |
| `VolatilityAnalyzer.get_symbol_info` | method | [integrations.mt5.domain.volatility_analyzer](../../integrations/mt5/domain/volatility_analyzer.py#L212) | stable |
| `VolatilityAnalyzer.rank_symbols_by_volatility` | method | [integrations.mt5.domain.volatility_analyzer](../../integrations/mt5/domain/volatility_analyzer.py#L155) | stable |
| `VolatilityAnalyzer.select_top_volatile_symbols` | method | [integrations.mt5.domain.volatility_analyzer](../../integrations/mt5/domain/volatility_analyzer.py#L179) | stable |

### `learning`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `FitRequest` | class | [learning.contracts](../../learning/contracts.py#L14) | stable |
| `FitResult` | class | [learning.contracts](../../learning/contracts.py#L42) | stable |
| `Learner` | class | [learning.contracts](../../learning/contracts.py#L65) | stable |
| `build_learner` | function | [learning.learner_factory](../../learning/learner_factory.py#L10) | stable |
| `Learner.fit` | method | [learning.contracts](../../learning/contracts.py#L68) | stable |
| `ReferenceTorchLearner` | class | [learning.supervised.reference](../../learning/supervised/reference.py#L145) | stable |
| `ReferenceTorchProvider` | class | [learning.supervised.reference](../../learning/supervised/reference.py#L78) | stable |
| `build_reference_torch_learner` | function | [learning.supervised.reference](../../learning/supervised/reference.py#L305) | stable |
| `load_reference_torch_provider` | function | [learning.supervised.reference](../../learning/supervised/reference.py#L249) | stable |
| `ReferenceTorchLearner.fit` | method | [learning.supervised.reference](../../learning/supervised/reference.py#L170) | stable |
| `ReferenceTorchProvider.metadata` | method | [learning.supervised.reference](../../learning/supervised/reference.py#L105) | stable |
| `ReferenceTorchProvider.predict` | method | [learning.supervised.reference](../../learning/supervised/reference.py#L113) | stable |

### `live`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `RLStrategyAdapter` | class | [live.runtime.strategy](../../live/runtime/strategy.py#L71) | stable |
| `RLStrategyAdapter.as_strategy` | method | [live.runtime.strategy](../../live/runtime/strategy.py#L355) | stable |
| `RLStrategyAdapter.build_observation` | method | [live.runtime.strategy](../../live/runtime/strategy.py#L224) | stable |
| `RLStrategyAdapter.predict_signal` | method | [live.runtime.strategy](../../live/runtime/strategy.py#L329) | stable |
| `RLStrategyAdapter.update_bars` | method | [live.runtime.strategy](../../live/runtime/strategy.py#L191) | stable |

### `market_data`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `BAR_CACHE_VERSION` | value | [market_data.loading.market_data_ingestion](../../market_data/loading/market_data_ingestion.py#L44) | stable |
| `TickBook` | class | [market_data.loading.ticks](../../market_data/loading/ticks.py#L489) | stable |
| `build_tick_books` | function | [market_data.loading.tick_book_pipeline](../../market_data/loading/tick_book_pipeline.py#L22) | stable |
| `get_split_config` | function | [market_data.splits.definitions](../../market_data/splits/definitions.py#L117) | stable |
| `load_bars` | function | [market_data.loading.bars](../../market_data/loading/bars.py#L22) | stable |
| `make_train_mask` | function | [market_data.splits.definitions](../../market_data/splits/definitions.py#L153) | stable |
| `run_pipeline` | function | [market_data.loading.market_data_ingestion](../../market_data/loading/market_data_ingestion.py#L47) | stable |
| `split_train_test` | function | [market_data.splits.definitions](../../market_data/splits/definitions.py#L16) | stable |
| `BAR_CACHE_MANIFEST_SCHEMA_VERSION` | value | [market_data.cache.bars](../../market_data/cache/bars.py#L19) | stable |
| `BAR_CACHE_TRANSFORM_ID` | value | [market_data.cache.bars](../../market_data/cache/bars.py#L20) | stable |
| `TICK_CACHE_MANIFEST_SCHEMA_VERSION` | value | [market_data.cache.ticks](../../market_data/cache/ticks.py#L19) | stable |
| `TICK_CACHE_TRANSFORM_ID` | value | [market_data.cache.ticks](../../market_data/cache/ticks.py#L20) | stable |
| `bar_cache_is_complete` | function | [market_data.cache.bars](../../market_data/cache/bars.py#L50) | stable |
| `bar_cache_manifest_path` | function | [market_data.cache.bars](../../market_data/cache/bars.py#L38) | stable |
| `bar_cache_path` | function | [market_data.cache.bars](../../market_data/cache/bars.py#L23) | stable |
| `build_bar_cache_identity` | function | [market_data.cache.bars](../../market_data/cache/bars.py#L69) | stable |
| `build_tick_cache_identity` | function | [market_data.cache.ticks](../../market_data/cache/ticks.py#L35) | stable |
| `cache_is_complete` | function | [market_data.cache.storage](../../market_data/cache/storage.py#L42) | stable |
| `file_sha256` | function | [artifacts.identity](../../artifacts/identity.py#L47) | stable |
| `load_bar_cache` | function | [market_data.cache.bars](../../market_data/cache/bars.py#L118) | stable |
| `load_parquet_cache` | function | [market_data.cache.storage](../../market_data/cache/storage.py#L131) | stable |
| `load_tick_cache` | function | [market_data.cache.ticks](../../market_data/cache/ticks.py#L100) | stable |
| `mark_cache_complete` | function | [market_data.cache.storage](../../market_data/cache/storage.py#L26) | stable |
| `market_data_cache_id` | function | [market_data.cache.identity](../../market_data/cache/identity.py#L8) | stable |
| `parquet_cache_is_complete` | function | [market_data.cache.storage](../../market_data/cache/storage.py#L109) | stable |
| `parquet_cache_manifest_path` | function | [market_data.cache.storage](../../market_data/cache/storage.py#L54) | stable |
| `tick_cache_is_complete` | function | [market_data.cache.ticks](../../market_data/cache/ticks.py#L82) | stable |
| `tick_cache_manifest_path` | function | [market_data.cache.ticks](../../market_data/cache/ticks.py#L23) | stable |
| `write_bar_cache` | function | [market_data.cache.bars](../../market_data/cache/bars.py#L133) | stable |
| `write_parquet_cache` | function | [market_data.cache.storage](../../market_data/cache/storage.py#L184) | stable |
| `write_tick_cache` | function | [market_data.cache.ticks](../../market_data/cache/ticks.py#L119) | stable |
| `BAR_CACHE_VERSION` | value | [market_data.loading.market_data_ingestion](../../market_data/loading/market_data_ingestion.py#L44) | stable |
| `TickBook` | class | [market_data.loading.ticks](../../market_data/loading/ticks.py#L489) | stable |
| `build_tick_book` | function | [market_data.loading.ticks](../../market_data/loading/ticks.py#L925) | stable |
| `build_tick_books` | function | [market_data.loading.tick_book_pipeline](../../market_data/loading/tick_book_pipeline.py#L22) | stable |
| `iter_ticks_chunks` | function | [market_data.loading.bars](../../market_data/loading/bars.py#L108) | stable |
| `load_bars` | function | [market_data.loading.bars](../../market_data/loading/bars.py#L22) | stable |
| `run_pipeline` | function | [market_data.loading.market_data_ingestion](../../market_data/loading/market_data_ingestion.py#L47) | stable |
| `TickBook.bar_quotes` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L691) | stable |
| `TickBook.content_sha256` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L654) | stable |
| `TickBook.delayed_exit_event` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L750) | stable |
| `TickBook.delayed_exit_quote` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L714) | stable |
| `TickBook.execution_quote_event_at` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L563) | stable |
| `TickBook.first_limit_execution_event` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L590) | stable |
| `TickBook.has_ticks_between` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L674) | stable |
| `TickBook.quote_at` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L517) | stable |
| `TickBook.quote_event_at` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L536) | stable |
| `TickBook.slice` | method | [market_data.loading.ticks](../../market_data/loading/ticks.py#L814) | stable |
| `get_split_config` | function | [market_data.splits.definitions](../../market_data/splits/definitions.py#L117) | stable |
| `get_train_start_config` | function | [market_data.splits.definitions](../../market_data/splits/definitions.py#L137) | stable |
| `make_train_mask` | function | [market_data.splits.definitions](../../market_data/splits/definitions.py#L153) | stable |
| `split_bars` | function | [market_data.splits.definitions](../../market_data/splits/definitions.py#L77) | stable |
| `split_train_test` | function | [market_data.splits.definitions](../../market_data/splits/definitions.py#L16) | stable |
| `add_session_id` | function | [market_data.transforms.sessions](../../market_data/transforms/sessions.py#L162) | stable |
| `add_session_labels` | function | [market_data.transforms.sessions](../../market_data/transforms/sessions.py#L104) | stable |
| `align_timeframes` | function | [market_data.transforms.align](../../market_data/transforms/align.py#L83) | stable |
| `clean` | function | [market_data.transforms.cleaning](../../market_data/transforms/cleaning.py#L10) | stable |
| `ny_session_mask` | function | [market_data.transforms.sessions](../../market_data/transforms/sessions.py#L83) | stable |
| `resample` | function | [market_data.transforms.resample](../../market_data/transforms/resample.py#L35) | stable |
| `scheduled_session_close_map` | function | [market_data.transforms.session_schedule](../../market_data/transforms/session_schedule.py#L13) | stable |
| `timeframe_close_times` | function | [market_data.transforms.align](../../market_data/transforms/align.py#L25) | stable |

### `models`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `VAE` | class | [models.auxiliary.vae](../../models/auxiliary/vae.py#L250) | stable |
| `VAE.decode` | method | [models.auxiliary.vae](../../models/auxiliary/vae.py#L327) | stable |
| `VAE.encode` | method | [models.auxiliary.vae](../../models/auxiliary/vae.py#L312) | stable |
| `VAE.forward` | method | [models.auxiliary.vae](../../models/auxiliary/vae.py#L353) | stable |
| `VAE.reparameterize` | method | [models.auxiliary.vae](../../models/auxiliary/vae.py#L339) | stable |
| `GRUEncoder` | class | [models.encoders.gru](../../models/encoders/gru.py#L20) | stable |
| `LegacyTCNEncoderV1` | class | [models.encoders.tcn](../../models/encoders/tcn.py#L75) | compatibility-only |
| `LiteTCNEncoder` | class | [models.encoders.lite_tcn](../../models/encoders/lite_tcn.py#L95) | stable |
| `M1TCNHTFLiteReasoningEncoder` | class | [models.encoders.mtf_m1_htf_lite_reasoning](../../models/encoders/mtf_m1_htf_lite_reasoning.py#L19) | stable |
| `M1TCNHTFSnapshotReasoningEncoder` | class | [models.encoders.mtf_m1_htf_snapshot_reasoning](../../models/encoders/mtf_m1_htf_snapshot_reasoning.py#L19) | stable |
| `MTFEmptyStreamMaskedV1Encoder` | class | [models.encoders.mtf_empty_stream_masked](../../models/encoders/mtf_empty_stream_masked.py#L10) | stable |
| `MTFEncoder` | class | [models.encoders.mtf](../../models/encoders/mtf.py#L86) | stable |
| `MTFReasoningEncoder` | class | [models.encoders.mtf_reasoning](../../models/encoders/mtf_reasoning.py#L13) | stable |
| `SharedTCNMTFReasoningEncoder` | class | [models.encoders.mtf_shared_tcn_reasoning](../../models/encoders/mtf_shared_tcn_reasoning.py#L77) | stable |
| `TCNEncoder` | class | [models.encoders.tcn](../../models/encoders/tcn.py#L141) | stable |
| `TCNRegimeEncoder` | class | [models.encoders.tcn_regime](../../models/encoders/tcn_regime.py#L15) | stable |
| `TransformerEncoder` | class | [models.encoders.transformer](../../models/encoders/transformer.py#L52) | stable |
| `LegacyTCNEncoderV1` | class | [models.encoders.tcn](../../models/encoders/tcn.py#L75) | compatibility-only |
| `GRUEncoder.forward` | method | [models.encoders.gru](../../models/encoders/gru.py#L80) | stable |
| `LiteTCNEncoder.forward` | method | [models.encoders.lite_tcn](../../models/encoders/lite_tcn.py#L171) | stable |
| `LiteTCNEncoder.receptive_field` | method | [models.encoders.lite_tcn](../../models/encoders/lite_tcn.py#L149) | stable |
| `MTFEncoder.forward` | method | [models.encoders.mtf](../../models/encoders/mtf.py#L140) | stable |
| `MTFEmptyStreamMaskedV1Encoder.forward` | method | [models.encoders.mtf_empty_stream_masked](../../models/encoders/mtf_empty_stream_masked.py#L27) | stable |
| `M1TCNHTFLiteReasoningEncoder.encoder_provenance` | method | [models.encoders.mtf_m1_htf_lite_reasoning](../../models/encoders/mtf_m1_htf_lite_reasoning.py#L79) | stable |
| `M1TCNHTFLiteReasoningEncoder.forward` | method | [models.encoders.mtf_m1_htf_lite_reasoning](../../models/encoders/mtf_m1_htf_lite_reasoning.py#L97) | stable |
| `M1TCNHTFSnapshotReasoningEncoder.encoder_provenance` | method | [models.encoders.mtf_m1_htf_snapshot_reasoning](../../models/encoders/mtf_m1_htf_snapshot_reasoning.py#L79) | stable |
| `M1TCNHTFSnapshotReasoningEncoder.forward` | method | [models.encoders.mtf_m1_htf_snapshot_reasoning](../../models/encoders/mtf_m1_htf_snapshot_reasoning.py#L97) | stable |
| `MTFReasoningEncoder.forward` | method | [models.encoders.mtf_reasoning](../../models/encoders/mtf_reasoning.py#L75) | stable |
| `SharedTCNMTFReasoningEncoder.encoder_provenance` | method | [models.encoders.mtf_shared_tcn_reasoning](../../models/encoders/mtf_shared_tcn_reasoning.py#L131) | stable |
| `SharedTCNMTFReasoningEncoder.forward` | method | [models.encoders.mtf_shared_tcn_reasoning](../../models/encoders/mtf_shared_tcn_reasoning.py#L149) | stable |
| `LegacyTCNEncoderV1.forward` | method | [models.encoders.tcn](../../models/encoders/tcn.py#L125) | compatibility-only |
| `TCNEncoder.forward` | method | [models.encoders.tcn](../../models/encoders/tcn.py#L209) | stable |
| `TCNEncoder.receptive_field` | method | [models.encoders.tcn](../../models/encoders/tcn.py#L201) | stable |
| `TCNRegimeEncoder.forward` | method | [models.encoders.tcn_regime](../../models/encoders/tcn_regime.py#L49) | stable |
| `TransformerEncoder.forward` | method | [models.encoders.transformer](../../models/encoders/transformer.py#L142) | stable |
| `ENCODER_TYPES` | value | [models.factory.encoder_registry](../../models/factory/encoder_registry.py#L22) | stable |
| `encoder_for` | function | [models.factory.encoder_registry](../../models/factory/encoder_registry.py#L40) | stable |
| `enable_extractor_autocast` | function | [models.runtime.precision](../../models/runtime/precision.py#L13) | stable |

### `simulation`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `SimulationTransition` | class | [simulation.contracts.transition](../../simulation/contracts/transition.py#L13) | stable |
| `TradingEnv` | class | [simulation.environment.env](../../simulation/environment/env.py#L33) | stable |
| `run_backtest` | function | [simulation.backtest.event_driven_backtest](../../simulation/backtest/event_driven_backtest.py#L538) | stable |
| `CrossOverStrategy` | class | [simulation.backtest.cross_validation.strategies.cross_over](../../simulation/backtest/cross_validation/strategies/cross_over.py#L4) | stable |
| `EMAMACDStrategy` | class | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L130) | stable |
| `MACDStrategy` | class | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L6) | stable |
| `SignalFollowingStrategy` | class | [simulation.backtest.cross_validation.strategies.signal_following](../../simulation/backtest/cross_validation/strategies/signal_following.py#L12) | stable |
| `CrossOverStrategy.log` | method | [simulation.backtest.cross_validation.strategies.cross_over](../../simulation/backtest/cross_validation/strategies/cross_over.py#L46) | stable |
| `CrossOverStrategy.next` | method | [simulation.backtest.cross_validation.strategies.cross_over](../../simulation/backtest/cross_validation/strategies/cross_over.py#L103) | stable |
| `CrossOverStrategy.notify_order` | method | [simulation.backtest.cross_validation.strategies.cross_over](../../simulation/backtest/cross_validation/strategies/cross_over.py#L58) | stable |
| `CrossOverStrategy.notify_trade` | method | [simulation.backtest.cross_validation.strategies.cross_over](../../simulation/backtest/cross_validation/strategies/cross_over.py#L92) | stable |
| `CrossOverStrategy.stop` | method | [simulation.backtest.cross_validation.strategies.cross_over](../../simulation/backtest/cross_validation/strategies/cross_over.py#L125) | stable |
| `EMAMACDStrategy.log` | method | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L180) | stable |
| `EMAMACDStrategy.next` | method | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L222) | stable |
| `EMAMACDStrategy.notify_order` | method | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L192) | stable |
| `MACDStrategy.log` | method | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L45) | stable |
| `MACDStrategy.next` | method | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L98) | stable |
| `MACDStrategy.notify_order` | method | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L57) | stable |
| `MACDStrategy.notify_trade` | method | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L87) | stable |
| `MACDStrategy.stop` | method | [simulation.backtest.cross_validation.strategies.macd_strategy](../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L121) | stable |
| `SignalFollowingStrategy.log` | method | [simulation.backtest.cross_validation.strategies.signal_following](../../simulation/backtest/cross_validation/strategies/signal_following.py#L30) | stable |
| `SignalFollowingStrategy.next` | method | [simulation.backtest.cross_validation.strategies.signal_following](../../simulation/backtest/cross_validation/strategies/signal_following.py#L59) | stable |
| `SignalFollowingStrategy.notify_order` | method | [simulation.backtest.cross_validation.strategies.signal_following](../../simulation/backtest/cross_validation/strategies/signal_following.py#L42) | stable |
| `SimulationTransition` | class | [simulation.contracts.transition](../../simulation/contracts/transition.py#L13) | stable |
| `SimulationTransition.as_gymnasium` | method | [simulation.contracts.transition](../../simulation/contracts/transition.py#L22) | stable |
| `TradingEnv` | class | [simulation.environment.env](../../simulation/environment/env.py#L33) | stable |
| `build_eval_common` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L217) | stable |
| `cost_model` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L523) | stable |
| `eval_guardrail_kwargs` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L112) | stable |
| `fill_delay_ms` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L361) | stable |
| `guardrail_kwargs` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L71) | stable |
| `make_env` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L550) | stable |
| `max_episode_steps` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L127) | stable |
| `max_loss_per_trade` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L54) | stable |
| `max_tick_quote_wait_ms` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L458) | stable |
| `mtf_settings` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L476) | stable |
| `randomized_fill_latency_ms` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L403) | stable |
| `regime_observation_enabled` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L434) | stable |
| `scheduled_session_closes` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L509) | stable |
| `strategy_from_cfg` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L144) | stable |
| `strategy_risk_ranges` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L24) | stable |
| `tick_execution_required` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L421) | stable |
| `TradingEnv.from_bundle` | method | [simulation.environment.env](../../simulation/environment/env.py#L424) | stable |
| `TradingEnv.step` | method | [simulation.environment.env](../../simulation/environment/env.py#L456) | stable |
| `TradingEnv.transition` | method | [simulation.environment.env](../../simulation/environment/env.py#L470) | stable |

### `trading`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `AccountState` | class | [trading.account.account_state](../../trading/account/account_state.py#L28) | stable |
| `TradingPolicyConfig` | class | [trading.policy.config](../../trading/policy/config.py#L24) | stable |
| `resolve_trading_policy` | function | [trading.policy.config](../../trading/policy/config.py#L200) | stable |
| `ACCOUNT_STATE_TRACE_SCHEMA` | value | [trading.account.snapshots](../../trading/account/snapshots.py#L9) | stable |
| `AccountState` | class | [trading.account.account_state](../../trading/account/account_state.py#L28) | stable |
| `account_state_snapshot` | function | [trading.account.snapshots](../../trading/account/snapshots.py#L12) | stable |
| `canonical_daily_loss` | function | [trading.account.limits](../../trading/account/limits.py#L6) | stable |
| `daily_floor` | function | [trading.account.limits](../../trading/account/limits.py#L19) | stable |
| `payout_amount` | function | [trading.account.accounting](../../trading/account/accounting.py#L19) | stable |
| `payout_due` | function | [trading.account.accounting](../../trading/account/accounting.py#L6) | stable |
| `remaining_account_capacity` | function | [trading.account.limits](../../trading/account/limits.py#L48) | stable |
| `remaining_daily_capacity` | function | [trading.account.limits](../../trading/account/limits.py#L32) | stable |
| `AccountState.canonical_daily_loss` | method | [trading.account.account_state](../../trading/account/account_state.py#L123) | stable |
| `AccountState.close_trade` | method | [trading.account.account_state](../../trading/account/account_state.py#L95) | stable |
| `AccountState.daily_floor` | method | [trading.account.account_state](../../trading/account/account_state.py#L184) | stable |
| `AccountState.daily_pnl_basis` | method | [trading.account.account_state](../../trading/account/account_state.py#L133) | stable |
| `AccountState.drawdown_pct` | method | [trading.account.account_state](../../trading/account/account_state.py#L284) | stable |
| `AccountState.loss_from_initial` | method | [trading.account.account_state](../../trading/account/account_state.py#L276) | stable |
| `AccountState.peak_eod_drawdown_usd` | method | [trading.account.account_state](../../trading/account/account_state.py#L314) | stable |
| `AccountState.record_eod_equity` | method | [trading.account.account_state](../../trading/account/account_state.py#L302) | stable |
| `AccountState.remaining_account_capacity` | method | [trading.account.account_state](../../trading/account/account_state.py#L216) | stable |
| `AccountState.remaining_daily_capacity` | method | [trading.account.account_state](../../trading/account/account_state.py#L200) | stable |
| `AccountState.reset_daily` | method | [trading.account.account_state](../../trading/account/account_state.py#L117) | stable |
| `AccountState.reset_operating_balance` | method | [trading.account.account_state](../../trading/account/account_state.py#L227) | stable |
| `AccountState.to_array` | method | [trading.account.account_state](../../trading/account/account_state.py#L322) | stable |
| `AccountState.to_risk_state` | method | [trading.account.account_state](../../trading/account/account_state.py#L149) | stable |
| `AccountState.trailing_drawdown_pct` | method | [trading.account.account_state](../../trading/account/account_state.py#L292) | stable |
| `AccountState.update_equity` | method | [trading.account.account_state](../../trading/account/account_state.py#L81) | stable |
| `BaseStrategy` | class | [trading.baselines.step_indexed_strategy](../../trading/baselines/step_indexed_strategy.py#L16) | stable |
| `BuyAndHoldStrategy` | class | [trading.baselines.classical](../../trading/baselines/classical.py#L34) | stable |
| `EMAMACDRSIStrategy` | class | [trading.baselines.classical](../../trading/baselines/classical.py#L102) | stable |
| `LSTMStrategy` | class | [trading.baselines.lstm_classifier](../../trading/baselines/lstm_classifier.py#L156) | stable |
| `LSTMSweepClassifier` | class | [trading.baselines.lstm_classifier](../../trading/baselines/lstm_classifier.py#L114) | stable |
| `MultiLevelBreakoutStrategy` | class | [trading.baselines.breakout](../../trading/baselines/breakout.py#L18) | stable |
| `SessionMomentumStrategy` | class | [trading.baselines.classical](../../trading/baselines/classical.py#L157) | stable |
| `SignalSeriesStrategy` | class | [trading.baselines.signal_series](../../trading/baselines/signal_series.py#L11) | stable |
| `build_sweep_dataset` | function | [trading.baselines.lstm_classifier](../../trading/baselines/lstm_classifier.py#L25) | stable |
| `ema_crossover` | function | [trading.baselines.rule_based](../../trading/baselines/rule_based.py#L28) | stable |
| `fit_hold_lots` | function | [trading.baselines.cash_hold](../../trading/baselines/cash_hold.py#L75) | stable |
| `macd_baseline` | function | [trading.baselines.rule_based](../../trading/baselines/rule_based.py#L60) | stable |
| `macd_ema50_baseline` | function | [trading.baselines.rule_based](../../trading/baselines/rule_based.py#L76) | stable |
| `rsi_mean_reversion` | function | [trading.baselines.rule_based](../../trading/baselines/rule_based.py#L176) | stable |
| `simulate_hold` | function | [trading.baselines.cash_hold](../../trading/baselines/cash_hold.py#L123) | stable |
| `swap_usd_per_lot` | function | [trading.baselines.cash_hold](../../trading/baselines/cash_hold.py#L30) | stable |
| `LSTMSweepClassifier.forward` | method | [trading.baselines.lstm_classifier](../../trading/baselines/lstm_classifier.py#L142) | stable |
| `BaseStrategy.act` | method | [trading.baselines.step_indexed_strategy](../../trading/baselines/step_indexed_strategy.py#L51) | stable |
| `BaseStrategy.act_at` | method | [trading.baselines.step_indexed_strategy](../../trading/baselines/step_indexed_strategy.py#L65) | stable |
| `BaseStrategy.fast_forward` | method | [trading.baselines.step_indexed_strategy](../../trading/baselines/step_indexed_strategy.py#L38) | stable |
| `BaseStrategy.reset` | method | [trading.baselines.step_indexed_strategy](../../trading/baselines/step_indexed_strategy.py#L34) | stable |
| `Broker` | class | [trading.execution.broker](../../trading/execution/broker.py#L129) | stable |
| `COST_US100` | value | [trading.execution.costs](../../trading/execution/costs.py#L75) | stable |
| `CostModel` | class | [trading.execution.costs](../../trading/execution/costs.py#L12) | stable |
| `FILL_COST_PROVENANCE_SCHEMA_VERSION` | value | [trading.execution.costs](../../trading/execution/costs.py#L8) | stable |
| `Position` | class | [trading.execution.broker](../../trading/execution/broker.py#L46) | stable |
| `TRADE_CASHFLOW_SCHEMA_VERSION` | value | [trading.execution.costs](../../trading/execution/costs.py#L7) | stable |
| `adverse_tick_fill_quote` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L10) | stable |
| `bar_stop_fill_quote` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L212) | stable |
| `bar_stop_trigger_price` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L189) | stable |
| `exit_side_bar_range` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L135) | stable |
| `protective_level_fill_quote` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L167) | stable |
| `quote_from_bar_price` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L118) | stable |
| `raw_spread_to_price` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L102) | stable |
| `undo_adverse_quote_level_slippage` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L78) | stable |
| `undo_adverse_tick_slippage_quote` | function | [trading.execution.quotes](../../trading/execution/quotes.py#L46) | stable |
| `Broker.close_position` | method | [trading.execution.broker](../../trading/execution/broker.py#L202) | stable |
| `Broker.mark_to_market` | method | [trading.execution.broker](../../trading/execution/broker.py#L245) | stable |
| `Broker.open_position` | method | [trading.execution.broker](../../trading/execution/broker.py#L159) | stable |
| `Broker.required_margin` | method | [trading.execution.broker](../../trading/execution/broker.py#L147) | stable |
| `CostModel.bar_quote` | method | [trading.execution.costs](../../trading/execution/costs.py#L56) | stable |
| `CostModel.fill_price` | method | [trading.execution.costs](../../trading/execution/costs.py#L36) | stable |
| `CostModel.total_cost` | method | [trading.execution.costs](../../trading/execution/costs.py#L21) | stable |
| `DEVIATION_KS` | value | [trading.orders.levels](../../trading/orders/levels.py#L5) | stable |
| `OrderGeometry` | class | [trading.orders.entries](../../trading/orders/entries.py#L45) | stable |
| `TIMEFRAME_ORDER` | value | [trading.orders.timeframes](../../trading/orders/timeframes.py#L5) | stable |
| `TargetReference` | class | [trading.orders.entries](../../trading/orders/entries.py#L31) | stable |
| `collapse_levels` | function | [trading.orders.targets](../../trading/orders/targets.py#L20) | stable |
| `decode_tp_fractions` | function | [trading.orders.selection](../../trading/orders/selection.py#L148) | stable |
| `decode_tp_mode` | function | [trading.orders.selection](../../trading/orders/selection.py#L15) | stable |
| `decode_tp_selections` | function | [trading.orders.selection](../../trading/orders/selection.py#L74) | stable |
| `deviation_candidates` | function | [trading.orders.targets](../../trading/orders/targets.py#L212) | stable |
| `deviation_levels` | function | [trading.orders.levels](../../trading/orders/levels.py#L29) | stable |
| `dynamic_tp` | function | [trading.orders.entries](../../trading/orders/entries.py#L165) | stable |
| `filter_sl_candidates` | function | [trading.orders.stops](../../trading/orders/stops.py#L76) | stable |
| `level_near_candles` | function | [trading.orders.levels](../../trading/orders/levels.py#L8) | stable |
| `limit_order_expiry` | function | [trading.orders.entry_execution](../../trading/orders/entry_execution.py#L51) | stable |
| `limit_price_from_atr_offset` | function | [trading.orders.entry_execution](../../trading/orders/entry_execution.py#L10) | stable |
| `manipulation_state` | function | [trading.orders.stops](../../trading/orders/stops.py#L48) | stable |
| `normalize_timeframe` | function | [trading.orders.timeframes](../../trading/orders/timeframes.py#L8) | stable |
| `place_strategy_order` | function | [trading.orders.entries](../../trading/orders/entries.py#L202) | stable |
| `reference_timeframe` | function | [trading.orders.timeframes](../../trading/orders/timeframes.py#L32) | stable |
| `reference_timeframe_index` | function | [trading.orders.timeframes](../../trading/orders/timeframes.py#L75) | stable |
| `resolve_strategy_entry` | function | [trading.orders.entries](../../trading/orders/entries.py#L636) | stable |
| `source_timeframe` | function | [trading.orders.timeframes](../../trading/orders/timeframes.py#L54) | stable |
| `stop_menu` | function | [trading.orders.stops](../../trading/orders/stops.py#L107) | stable |
| `target_menu` | function | [trading.orders.targets](../../trading/orders/targets.py#L58) | stable |
| `timeframe_index` | function | [trading.orders.timeframes](../../trading/orders/timeframes.py#L20) | stable |
| `validate_tp_levels` | function | [trading.orders.selection](../../trading/orders/selection.py#L198) | stable |
| `LEGACY_POLICY_MODE` | value | [trading.policy.legacy](../../trading/policy/legacy.py#L5) | compatibility-only |
| `PayoutDecision` | class | [trading.policy.repeated_payout](../../trading/policy/repeated_payout.py#L13) | stable |
| `TradingPolicyConfig` | class | [trading.policy.config](../../trading/policy/config.py#L24) | stable |
| `build_payout_reset_event` | function | [trading.policy.repeated_payout](../../trading/policy/repeated_payout.py#L51) | stable |
| `evaluate_payout` | function | [trading.policy.repeated_payout](../../trading/policy/repeated_payout.py#L25) | stable |
| `resolve_trading_policy` | function | [trading.policy.config](../../trading/policy/config.py#L200) | stable |
| `resolve_trading_policy_mapping` | function | [trading.policy.config](../../trading/policy/config.py#L283) | stable |
| `uses_fixed_risk_budget` | function | [trading.policy.legacy](../../trading/policy/legacy.py#L8) | stable |
| `TradingPolicyConfig.daily_loss_limit` | method | [trading.policy.config](../../trading/policy/config.py#L72) | stable |
| `TradingPolicyConfig.from_mapping` | method | [trading.policy.config](../../trading/policy/config.py#L81) | stable |
| `TradingPolicyConfig.repeated_payout` | method | [trading.policy.config](../../trading/policy/config.py#L63) | stable |
| `TradingPolicyConfig.to_dict` | method | [trading.policy.config](../../trading/policy/config.py#L191) | stable |
| `TradingPolicyConfig.validate` | method | [trading.policy.config](../../trading/policy/config.py#L134) | stable |
| `reorder_remaining_targets` | function | [trading.positions.multi_tp](../../trading/positions/multi_tp.py#L47) | stable |
| `target_close_size` | function | [trading.positions.multi_tp](../../trading/positions/multi_tp.py#L10) | stable |
| `FTMOGuardrails` | class | [trading.risk.guardrails](../../trading/risk/guardrails.py#L83) | stable |
| `FTMOMidnightSnapshotUnavailable` | class | [trading.risk.ftmo_clock](../../trading/risk/ftmo_clock.py#L16) | stable |
| `RISK_BREACH_EVENT_SCHEMA_V1` | value | [trading.risk.contracts](../../trading/risk/contracts.py#L14) | stable |
| `RISK_BREACH_EVENT_SCHEMA_V2` | value | [trading.risk.contracts](../../trading/risk/contracts.py#L16) | stable |
| `RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES` | value | [trading.risk.contracts](../../trading/risk/contracts.py#L18) | compatibility-only |
| `RISK_DAILY_PNL_BASIS_SESSION_EQUITY` | value | [trading.risk.contracts](../../trading/risk/contracts.py#L17) | stable |
| `RISK_DECISION_SCHEMA_V1` | value | [trading.risk.contracts](../../trading/risk/contracts.py#L13) | stable |
| `RISK_STATE_SCHEMA_V1` | value | [trading.risk.contracts](../../trading/risk/contracts.py#L12) | stable |
| `RiskBudgetDecision` | class | [trading.risk.budget](../../trading/risk/budget.py#L9) | stable |
| `RiskDailyPnlBasis` | value | [trading.risk.contracts](../../trading/risk/contracts.py#L9) | stable |
| `RiskDecision` | class | [trading.risk.contracts](../../trading/risk/contracts.py#L59) | stable |
| `RiskPolicy` | class | [trading.risk.contracts](../../trading/risk/contracts.py#L82) | stable |
| `RiskState` | class | [trading.risk.contracts](../../trading/risk/contracts.py#L23) | stable |
| `adverse_position_loss_limit_usd` | function | [trading.risk.guardrails](../../trading/risk/guardrails.py#L49) | stable |
| `approve_dynamic_risk` | function | [trading.risk.budget](../../trading/risk/budget.py#L36) | stable |
| `breakeven_stop_price` | function | [trading.risk.stop_management](../../trading/risk/stop_management.py#L117) | stable |
| `compute_lots` | function | [trading.risk.sizing](../../trading/risk/sizing.py#L93) | stable |
| `compute_lots_with_execution_reserve` | function | [trading.risk.sizing](../../trading/risk/sizing.py#L151) | stable |
| `compute_sl_tp_long` | function | [trading.risk.sizing](../../trading/risk/sizing.py#L33) | stable |
| `compute_sl_tp_short` | function | [trading.risk.sizing](../../trading/risk/sizing.py#L63) | stable |
| `confirmed_swing_trailing_stop_price` | function | [trading.risk.stop_management](../../trading/risk/stop_management.py#L8) | stable |
| `ftmo_trading_day` | function | [trading.risk.ftmo_clock](../../trading/risk/ftmo_clock.py#L20) | stable |
| `guardrail_breach_scope` | function | [trading.risk.guardrails](../../trading/risk/guardrails.py#L25) | stable |
| `modeled_execution_reserve_usd` | function | [trading.risk.execution_reserve](../../trading/risk/execution_reserve.py#L6) | stable |
| `risk_budget_from_equity` | function | [trading.risk.budget](../../trading/risk/budget.py#L23) | stable |
| `stop_loss_risk_usd` | function | [trading.risk.sizing](../../trading/risk/sizing.py#L13) | stable |
| `tightened_breakeven_stop_price` | function | [trading.risk.stop_management](../../trading/risk/stop_management.py#L67) | stable |
| `RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES` | value | [trading.risk.contracts](../../trading/risk/contracts.py#L18) | compatibility-only |
| `RiskPolicy.decide` | method | [trading.risk.contracts](../../trading/risk/contracts.py#L85) | stable |
| `FTMOGuardrails.any_breach` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L316) | stable |
| `FTMOGuardrails.breach_reason` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L327) | stable |
| `FTMOGuardrails.check_daily` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L229) | stable |
| `FTMOGuardrails.check_max_drawdown` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L256) | stable |
| `FTMOGuardrails.check_soft_daily` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L241) | stable |
| `FTMOGuardrails.check_soft_trailing_dd` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L286) | stable |
| `FTMOGuardrails.check_trade_risk` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L301) | stable |
| `FTMOGuardrails.check_trailing_dd` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L271) | stable |
| `FTMOGuardrails.daily_limit_for` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L130) | stable |
| `FTMOGuardrails.max_drawdown_from_reference` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L188) | stable |
| `FTMOGuardrails.max_loss_floor_for` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L163) | stable |
| `FTMOGuardrails.max_loss_limit_for` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L152) | stable |
| `FTMOGuardrails.risk_per_trade_limit_for` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L216) | stable |
| `FTMOGuardrails.soft_daily_limit_for` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L141) | stable |
| `FTMOGuardrails.soft_max_loss_limit_for` | method | [trading.risk.guardrails](../../trading/risk/guardrails.py#L205) | stable |
| `BaselineStrategy` | class | [trading.strategies.baseline](../../trading/strategies/baseline.py#L11) | stable |
| `DistributionStrategy` | class | [trading.strategies.distribution](../../trading/strategies/distribution.py#L69) | stable |
| `PO3IFVGStrategy` | class | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L14) | stable |
| `TradingStrategy` | class | [trading.strategies.strategy_contract](../../trading/strategies/strategy_contract.py#L27) | stable |
| `BaselineStrategy.sl_reference` | method | [trading.strategies.baseline](../../trading/strategies/baseline.py#L34) | stable |
| `BaselineStrategy.target_candidates` | method | [trading.strategies.baseline](../../trading/strategies/baseline.py#L46) | stable |
| `BaselineStrategy.validate_entry` | method | [trading.strategies.baseline](../../trading/strategies/baseline.py#L22) | stable |
| `DistributionStrategy.bind_columns` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L141) | stable |
| `DistributionStrategy.context_direction` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L259) | stable |
| `DistributionStrategy.distribution_ready` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L277) | stable |
| `DistributionStrategy.entry_rejection_reason` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L168) | stable |
| `DistributionStrategy.previous_session_pd_eligible` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L189) | stable |
| `DistributionStrategy.sl_candidates` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L314) | stable |
| `DistributionStrategy.sl_reference` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L209) | stable |
| `DistributionStrategy.target_candidates` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L226) | stable |
| `DistributionStrategy.validate_entry` | method | [trading.strategies.distribution](../../trading/strategies/distribution.py#L154) | stable |
| `PO3IFVGStrategy.bind_columns` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L111) | stable |
| `PO3IFVGStrategy.context_direction` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L228) | stable |
| `PO3IFVGStrategy.entry_gap` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L204) | stable |
| `PO3IFVGStrategy.entry_liquidity` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L188) | stable |
| `PO3IFVGStrategy.entry_setup` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L253) | stable |
| `PO3IFVGStrategy.sl_candidates` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L406) | stable |
| `PO3IFVGStrategy.sl_reference` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L138) | stable |
| `PO3IFVGStrategy.target_candidates` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L155) | stable |
| `PO3IFVGStrategy.validate_entry` | method | [trading.strategies.po3_ifvg](../../trading/strategies/po3_ifvg.py#L124) | stable |
| `TradingStrategy.bind_columns` | method | [trading.strategies.strategy_contract](../../trading/strategies/strategy_contract.py#L81) | stable |
| `TradingStrategy.context_direction` | method | [trading.strategies.strategy_contract](../../trading/strategies/strategy_contract.py#L88) | stable |
| `TradingStrategy.sl_candidates` | method | [trading.strategies.strategy_contract](../../trading/strategies/strategy_contract.py#L101) | stable |
| `TradingStrategy.sl_reference` | method | [trading.strategies.strategy_contract](../../trading/strategies/strategy_contract.py#L58) | stable |
| `TradingStrategy.target_candidates` | method | [trading.strategies.strategy_contract](../../trading/strategies/strategy_contract.py#L70) | stable |
| `TradingStrategy.validate_entry` | method | [trading.strategies.strategy_contract](../../trading/strategies/strategy_contract.py#L46) | stable |

### `training`

| Exported name | Kind | Source | Status |
|---|---|---|---|
| `RUN_LOG_FILENAME` | value | [training.artifacts.logging](../../training/artifacts/logging.py#L8) | stable |
| `action_schema_manifest` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L192) | stable |
| `action_space_width` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L172) | stable |
| `aggregate_seed_results` | function | [training.artifacts.aggregation](../../training/artifacts/aggregation.py#L78) | stable |
| `attach_run_log` | function | [training.artifacts.logging](../../training/artifacts/logging.py#L11) | stable |
| `build_training_log` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L43) | stable |
| `entry_funnel_by_split` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L18) | stable |
| `observation_account_dim` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L503) | stable |
| `observation_schema_manifest` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L209) | stable |
| `observation_space_shapes` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L521) | stable |
| `save_seed_artifacts` | function | [training.artifacts.aggregation](../../training/artifacts/aggregation.py#L29) | stable |
| `sequence_feature_schema_manifest` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L336) | stable |
| `training_protocol_manifest` | function | [training.artifacts.manifests](../../training/artifacts/manifests.py#L358) | stable |
| `write_evaluation_artifacts` | function | [training.artifacts.evaluation_result_writer](../../training/artifacts/evaluation_result_writer.py#L16) | stable |
| `write_run_config_snapshot` | function | [training.artifacts.snapshots](../../training/artifacts/snapshots.py#L9) | stable |
| `resolve_variant` | function | [training.configuration.variant_resolution](../../training/configuration/variant_resolution.py#L140) | stable |
| `train_args` | function | [training.configuration.variant_resolution](../../training/configuration/variant_resolution.py#L356) | stable |
| `save_dashboard_plots` | function | [training.reporting.training_curves](../../training/reporting/training_curves.py#L738) | stable |
| `save_training_plots` | function | [training.reporting.training_curves](../../training/reporting/training_curves.py#L515) | stable |
| `main` | function | [training.runner](../../training/runner/__init__.py#L1) | stable |
| `make_env` | function | [simulation.environment.trading_environment_factory](../../simulation/environment/trading_environment_factory.py#L550) | stable |

## Installed commands

| Command | Entry point | Source |
|---|---|---|
| `orchestra` | `orchestra.cli:main` | [orchestra/cli.py](../../orchestra/cli.py) |
| `qrl-compute` | `compute.cli:main` | [compute/cli.py](../../compute/cli.py) |
| `qrl-data` | `market_data.cli:main` | [market_data/cli.py](../../market_data/cli.py) |
| `qrl-evaluate` | `evaluation.cli:main` | [evaluation/cli.py](../../evaluation/cli.py) |
| `qrl-experiment` | `experiments.cli:main` | [experiments/cli.py](../../experiments/cli.py) |
| `qrl-train` | `training.cli:main` | [training/cli.py](../../training/cli.py) |
