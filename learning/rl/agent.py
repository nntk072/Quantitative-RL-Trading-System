"""RL agent wiring: builds SB3 PPO or SAC with sequence encoders.

Usage
-----
Construct policies inside the canonical training workflow so survival and
provenance gates are enforced before portfolio-reward training.

    from learning.rl.agent import build_agent
    model = build_agent(env, cfg)                    # default PPO with TCN
    model = build_agent(env, cfg, arch="transformer")
    model = build_agent(env, cfg, arch="gru", algo="sac")  # SAC agent
"""

from __future__ import annotations

import multiprocessing
import sys
from collections.abc import Callable
from typing import Any, cast

import numpy as np
import torch
from gymnasium import spaces
from omegaconf import DictConfig

from compute.environment.precision import get_autocast_dtype
from decisioning.actions import ActionSchema
from decisioning.trade_setup import TradeSetupActionSchema
from learning.rl.agent_contracts import (
    bind_discrete_action_schema as bind_discrete_action_schema,  # noqa: F401 - re-exported checkpoint contract
)
from learning.rl.agent_contracts import (
    persist_action_schema as persist_action_schema,
)
from learning.rl.agent_contracts import (
    validate_model_action_schema as validate_model_action_schema,  # noqa: F401 - re-exported checkpoint contract
)
from learning.rl.agent_contracts import (
    validate_model_candidate_geometry_observation_schema as validate_model_candidate_geometry_observation_schema,  # noqa: F401 - re-export
)
from learning.rl.agent_contracts import (
    validate_model_discrete_action_schema as validate_model_discrete_action_schema,  # noqa: F401 - re-exported checkpoint contract
)
from learning.rl.agent_contracts import (
    validate_model_observation_schema as validate_model_observation_schema,  # noqa: F401 - re-exported checkpoint contract
)
from learning.rl.agent_contracts import (
    validate_model_trade_setup_observation_schema as validate_model_trade_setup_observation_schema,  # noqa: F401 - re-export
)
from learning.rl.ppo import ClampedStdMultiInputPolicy
from models.factory import encoder_for
from models.runtime.precision import enable_extractor_autocast

try:
    from stable_baselines3 import PPO, SAC
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    _SB3_AVAILABLE = True
except ImportError:
    _SB3_AVAILABLE = False


def build_vector_env(
    env: Any,
    cfg: DictConfig,
    env_fn: Callable[[], Any] | None,
) -> Any:
    """Build the VecEnv described by config for fresh or resumed PPO runs.

    Keeping this wiring shared matters when loading checkpoints: SB3 otherwise
    wraps the supplied raw environment in a single-env ``DummyVecEnv``, even
    when the resolved config requests many parallel environments.

    Args:
        env: Environment whose state is read or updated.
        cfg: Run configuration used by this operation.
        env_fn: Env fn used by the operation described above.

    Returns:
        Result of build the VecEnv described by config for fresh or resumed PPO runs.
    """
    if not _SB3_AVAILABLE:
        raise ImportError("stable-baselines3 is required: pip install stable-baselines3")

    n_envs = int(getattr(cfg.get("env", {}), "n_envs", 1))
    vector_backend = str(getattr(cfg.get("env", {}), "vector_backend", "subproc"))
    if vector_backend not in {"subproc", "serial", "sharded_bundle"}:
        raise ValueError(
            "env.vector_backend must be 'subproc', 'serial', or 'sharded_bundle', "
            f"got {vector_backend!r}"
        )
    if n_envs <= 1 or env_fn is None:
        return DummyVecEnv([lambda: env])

    bundle_workers = str(cfg.env.get("data_source", "frames")) == "bundle"
    use_forkserver = bundle_workers and "forkserver" in multiprocessing.get_all_start_methods()
    if use_forkserver:
        multiprocessing.set_forkserver_preload(
            [
                "stable_baselines3.common.vec_env.subproc_vec_env",
                "simulation.environment.worker",
                "simulation.environment.env",
            ]
        )

    def _thread_capped_env_fn() -> Any:
        """Process capped env fn.

        Returns:
            Result of process capped env fn.
        """
        import os as _os

        for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
            _os.environ[_var] = "1"
        _torch = sys.modules.get("torch")
        if _torch is not None:
            _torch.set_num_threads(1)
        return env_fn()

    if vector_backend == "serial":
        return DummyVecEnv([_thread_capped_env_fn] * n_envs)

    start_method = "forkserver" if use_forkserver else None
    if vector_backend == "sharded_bundle":
        if not bundle_workers:
            raise ValueError("vector_backend='sharded_bundle' requires env.data_source='bundle'")
        from learning.rl.environment_adapter import ShardedBundleVecEnv

        configured_shards = int(getattr(cfg.env, "vector_shards", 0))
        n_shards = min(8, n_envs) if configured_shards == 0 else configured_shards
        if n_shards < 1 or n_shards > n_envs:
            raise ValueError(
                f"env.vector_shards must be between 1 and env.n_envs ({n_envs}), got {n_shards}"
            )
        return ShardedBundleVecEnv(
            [_thread_capped_env_fn] * n_envs,
            n_shards=n_shards,
            start_method=start_method,
        )
    return SubprocVecEnv([_thread_capped_env_fn] * n_envs, start_method=start_method)


class LegacyFourToFiveActionAdapter:
    """Append the explicit structural-exit coordinate for a legacy 4D policy."""

    def __init__(self, model: Any) -> None:
        """Initialize LegacyFourToFiveActionAdapter and its owned state.

        Args:
            model: Model used for this operation.
        """
        self.model = model

    def __getattr__(self, name: str) -> Any:
        """Process LegacyFourToFiveActionAdapter.

        Args:
            name: Name used to identify the requested file, artifact, or item.

        Returns:
            Result of process LegacyFourToFiveActionAdapter.
        """
        return getattr(self.model, name)

    def predict(self, observation: Any, *, deterministic: bool = True) -> tuple[Any, Any]:
        """Append the structural-exit coordinate to a legacy four-value action.

        Args:
            observation: Batch or single observation passed to the wrapped model.
            deterministic: Whether the wrapped policy selects its modal action.

        Returns:
            Adapted action values and the wrapped model's state.
        """
        action, state = self.model.predict(observation, deterministic=deterministic)
        values = np.asarray(action)
        if values.shape[-1:] != (4,):
            raise ValueError(f"legacy 4D policy returned unexpected action shape {values.shape}")
        structural_exit = np.full((*values.shape[:-1], 1), -1.0, dtype=values.dtype)
        return np.concatenate((values, structural_exit), axis=-1), state


def validate_model_architecture(model: Any, expected_arch: str, *, use_vae: bool = False) -> None:
    """Fail closed when a checkpoint encoder differs from the requested lineage.

    Args:
        model: Model used for this operation.
        expected_arch: Text or path value identifying the expected arch.
        use_vae: Whether to enable or require the use vae.
    """
    if use_vae:
        return
    expected = encoder_for(expected_arch)
    extractor = getattr(getattr(model, "policy", None), "features_extractor", None)
    if extractor is None:
        raise ValueError(
            "checkpoint does not expose a feature extractor for architecture validation"
        )
    architecture_matches = (
        type(extractor) is expected
        if expected_arch
        in {
            "tcn",
            "tcn_regime",
            "mtf",
            "mtf_empty_stream_masked_v1",
            "mtf_reasoning",
            "mtf_shared_tcn_reasoning",
            "mtf_m1_tcn_htf_lite_reasoning",
            "mtf_m1_tcn_htf_snapshot_reasoning",
        }
        else isinstance(extractor, expected)
    )
    if not architecture_matches:
        raise ValueError(
            f"checkpoint encoder {type(extractor).__name__} does not match requested "
            f"architecture {expected_arch!r} ({expected.__name__})"
        )
    if expected_arch == "tcn_regime":
        from decisioning.regime_observations import regime_observation_schema

        expected_regime_schema = regime_observation_schema()
        actual_regime_schema = getattr(model, "_regime_observation_schema", None)
        if actual_regime_schema != expected_regime_schema:
            raise ValueError(
                "checkpoint regime observation schema differs from the current D1 feature "
                "order or semantics"
            )


def build_agent(
    env: Any,
    cfg: DictConfig,
    arch: str = "tcn",
    algo: str = "ppo",
    use_vae: bool = False,
    vae: Any | None = None,
    device: str | torch.device | None = None,
    env_fn: Callable[[], Any] | None = None,
    seed: int | None = None,
) -> Any:
    """Build an SB3 PPO or SAC agent wired to the sequence encoder.

    Args:
        env: A :class:`simulation.environment.env.TradingEnv` instance.
        cfg: Full OmegaConf config.
        arch: ``"tcn"`` (default), ``"transformer"``, ``"gru"``, or ``"mtf"``.
        algo: ``"ppo"`` (default) or ``"sac"``.
        use_vae: If True, use the VAE feature extractor (default: False).
        vae: A trained :class:`models.auxiliary.vae.VAE` instance.  Required when
            ``use_vae`` is ``True``.
        device: Torch device to place the policy on (e.g. ``"cpu"``, ``"cuda"``).
            ``None`` lets SB3 auto-detect.
        env_fn: Optional factory ``() -> TradingEnv`` used when ``cfg.env.n_envs > 1``
            to spawn parallel environments via ``SubprocVecEnv``.  When omitted or
            when ``n_envs == 1``, falls back to ``DummyVecEnv`` (sequential,
            single-env — the original behaviour).
        seed: Optional random seed used to initialize the agent and policy.

    Returns:
        ``stable_baselines3.PPO`` or ``stable_baselines3.SAC`` ready to call:
        ``.learn()``.:

    Raises:
        ValueError: If ``use_vae`` is ``True`` but ``vae`` is ``None``.
    """
    if not _SB3_AVAILABLE:
        raise ImportError("stable-baselines3 is required: pip install stable-baselines3")

    _validate_survival_objective_config(cfg, algo)

    from learning.rl.vae_extractor import VAEFeatureExtractor

    if use_vae and vae is None:
        raise ValueError("use_vae=True requires a constructed VAE instance passed via vae=")
    regime_enabled = "regime" in getattr(env.observation_space, "spaces", {})
    if (arch == "tcn_regime") != regime_enabled:
        raise ValueError(
            "tcn_regime requires the versioned regime observation branch, and other "
            "architectures must not receive it"
        )

        # Infer F from the env's observation space
    n_features: int = env.observation_space["seq"].shape[1]
    account_dim: int = int(env.observation_space["account"].shape[0])
    agent_cfg = cfg.get("agent", {})
    trade_setup_enabled = bool(getattr(env, "trade_setup_actions", False))
    candidate_geometry_enabled = bool(getattr(env, "candidate_geometry_actions", False))
    ppo_cfg = cfg.get("ppo", {})
    configured_distribution = str(ppo_cfg.get("policy_distribution", "clamped_diagonal_gaussian"))
    setup_distributions = {
        "trade_setup_hybrid_v1",
        "trade_setup_conditioned_v1",
        "trade_setup_candidate_geometry_v1",
    }
    if trade_setup_enabled and algo != "ppo":
        raise ValueError(
            "trade setup actions currently require PPO's masked categorical distribution"
        )
    if trade_setup_enabled and configured_distribution not in setup_distributions:
        raise ValueError("trade setup actions require a masked trade-setup PPO distribution")
    if configured_distribution in setup_distributions and not trade_setup_enabled:
        raise ValueError(f"{configured_distribution} requires trade setup actions to be enabled")
    if (
        candidate_geometry_enabled
        and configured_distribution != "trade_setup_candidate_geometry_v1"
    ):
        raise ValueError(
            "env.candidate_geometry_actions requires "
            "ppo.policy_distribution=trade_setup_candidate_geometry_v1"
        )
    if (
        configured_distribution == "trade_setup_candidate_geometry_v1"
        and not candidate_geometry_enabled
    ):
        raise ValueError(
            "trade_setup_candidate_geometry_v1 requires env.candidate_geometry_actions=true"
        )

        # Choose feature extractor based on architecture / VAE use
    extractor_cls: Any
    if use_vae and "vae_z" in env.observation_space.spaces:
        extractor_cls = VAEFeatureExtractor
        latent_dim = env.observation_space["vae_z"].shape[0]
        extractor_kwargs: dict[str, Any] = {
            "vae": vae,
            "freeze": True,
            "account_dim": account_dim,
        }
    else:
        mtf_architectures = {
            "mtf",
            "mtf_empty_stream_masked_v1",
            "mtf_reasoning",
            "mtf_shared_tcn_reasoning",
            "mtf_m1_tcn_htf_lite_reasoning",
            "mtf_m1_tcn_htf_snapshot_reasoning",
        }
        if arch in mtf_architectures and "seq_m5" not in env.observation_space.spaces:
            raise ValueError(f"arch {arch!r} requires an environment built with mtf=True")
        extractor_cls = encoder_for(arch)

        latent_dim = 128
        if arch in {"mtf", "mtf_empty_stream_masked_v1"}:
            extractor_kwargs = dict(latent_dim=latent_dim, account_dim=account_dim)
        elif arch == "mtf_reasoning":
            reasoning_cfg = agent_cfg.get("mtf_reasoning", {})
            latent_dim = int(reasoning_cfg.get("latent_dim", 128))
            extractor_kwargs = dict(
                latent_dim=latent_dim,
                account_dim=account_dim,
                attention_heads=int(reasoning_cfg.get("attention_heads", 4)),
                feedforward_dim=int(reasoning_cfg.get("feedforward_dim", 256)),
                dropout=float(reasoning_cfg.get("dropout", 0.1)),
            )
        elif arch in {
            "mtf_shared_tcn_reasoning",
            "mtf_m1_tcn_htf_lite_reasoning",
            "mtf_m1_tcn_htf_snapshot_reasoning",
        }:
            reasoning_cfg = agent_cfg.get(arch, {})
            latent_dim = int(reasoning_cfg.get("latent_dim", 128))
            extractor_kwargs = dict(
                latent_dim=latent_dim,
                channels=tuple(
                    int(value) for value in reasoning_cfg.get("channels", [128, 128, 256, 256])
                ),
                kernel_size=int(reasoning_cfg.get("kernel_size", 3)),
                dropout=float(reasoning_cfg.get("dropout", 0.1)),
                account_dim=account_dim,
                attention_heads=int(reasoning_cfg.get("attention_heads", 4)),
                feedforward_dim=int(reasoning_cfg.get("feedforward_dim", 256)),
                adapter_dim=int(
                    reasoning_cfg.get(
                        "adapter_dim",
                        64 if arch == "mtf_shared_tcn_reasoning" else 32,
                    )
                ),
            )
        elif arch == "lite_tcn":
            lite_cfg = agent_cfg.get("lite_tcn", {})
            latent_dim = int(lite_cfg.get("latent_dim", 128))
            extractor_kwargs = dict(
                seq_len=cfg.env.obs_window,
                n_features=n_features,
                latent_dim=latent_dim,
                channels=int(lite_cfg.get("channels", 96)),
                dilations=tuple(int(value) for value in lite_cfg.get("dilations", [1, 4, 10])),
                kernel_size=int(lite_cfg.get("kernel_size", 3)),
                dropout=float(lite_cfg.get("dropout", 0.1)),
                account_dim=account_dim,
            )
        else:
            extractor_kwargs = dict(
                seq_len=cfg.env.obs_window,
                n_features=n_features,
                latent_dim=latent_dim,
                account_dim=account_dim,
            )

            # Two hidden layers after the encoder. SAC uses ``qf`` for the critic.
    head_cfg = agent_cfg.get("head_arch", {})
    head_arch = [int(value) for value in head_cfg.get(arch, [256, 128])]
    if algo == "sac":
        net_arch: dict[str, Any] = dict(pi=head_arch, qf=head_arch)
    else:
        net_arch = dict(pi=head_arch, vf=head_arch)

    policy_kwargs: dict[str, Any] = dict(
        features_extractor_class=extractor_cls,
        features_extractor_kwargs=extractor_kwargs,
        net_arch=net_arch,
    )
    actor_arch = str(cfg.ppo.get("actor_arch", "shared")) if algo == "ppo" else "shared"
    if actor_arch == "semantic_heads":
        if not isinstance(env.action_space, spaces.Box):
            raise ValueError("semantic actor heads require a continuous Box action space")
        schema = getattr(env, "action_schema", None)
        if not isinstance(schema, ActionSchema):
            raise ValueError("semantic actor heads require a declared strategy ActionSchema")
        policy_kwargs["semantic_action_coordinates"] = schema.names
        policy_kwargs["semantic_head_width"] = int(cfg.ppo.get("semantic_head_width", 64))
    elif actor_arch != "shared":
        raise ValueError(f"unknown PPO actor_arch: {actor_arch!r}")

    n_envs = int(getattr(cfg.get("env", {}), "n_envs", 1))
    vec_env = build_vector_env(env, cfg, env_fn)

    if algo == "sac":
        # SAC requires continuous action space
        if not isinstance(env.action_space, spaces.Box):
            raise ValueError("SAC requires continuous action space (Box)")

        sac_cfg = cfg.get("sac", cfg.get("ppo", {}))
        sac_kwargs: dict[str, Any] = dict(
            learning_rate=sac_cfg.get("learning_rate", 3e-4),
            buffer_size=sac_cfg.get("buffer_size", 1_000_000),
            batch_size=sac_cfg.get("batch_size", 256),
            tau=sac_cfg.get("tau", 0.005),
            gamma=sac_cfg.get("gamma", 0.99),
            train_freq=sac_cfg.get("train_freq", 1),
            gradient_steps=sac_cfg.get("gradient_steps", 1),
            ent_coef=sac_cfg.get("ent_coef", "auto"),
            learning_starts=sac_cfg.get("learning_starts", 500),
            seed=seed,
            verbose=1,
        )
        if device is not None:
            sac_kwargs["device"] = device
        model = SAC(
            "MultiInputPolicy",
            vec_env,
            policy_kwargs=policy_kwargs,
            **sac_kwargs,
        )
        regime_schema = getattr(env, "regime_observation_schema", None)
        if isinstance(regime_schema, dict):
            cast(Any, model)._regime_observation_schema = regime_schema
        setup_schema = getattr(env, "trade_setup_observation_schema", None)
        if isinstance(setup_schema, dict):
            cast(Any, model)._trade_setup_observation_schema = setup_schema
        persist_action_schema(model, env)
        return _finalize_cuda_policy(model, device, _autocast_override(cfg))
        # Default to PPO
    ppo_n_steps = cfg.ppo.n_steps
    if n_envs > 1 and env_fn is not None:
        ppo_n_steps = max(1, ppo_n_steps // n_envs)

    ppo_kwargs: dict[str, Any] = dict(
        n_steps=ppo_n_steps,
        batch_size=cfg.ppo.batch_size,
        n_epochs=cfg.ppo.n_epochs,
        learning_rate=cfg.ppo.learning_rate,
        gamma=cfg.ppo.gamma,
        gae_lambda=cfg.ppo.gae_lambda,
        clip_range=cfg.ppo.clip_range,
        ent_coef=cfg.ppo.ent_coef,
        seed=seed,
        verbose=1,
    )
    if bool(cfg.ppo.get("rollout_buffer_on_device", False)):
        from learning.rl.rollout_buffer import DeviceDictRolloutBuffer

        ppo_kwargs["rollout_buffer_class"] = DeviceDictRolloutBuffer
    if device is not None:
        ppo_kwargs["device"] = device
    policy, policy_kwargs, ppo_kwargs["ent_coef"] = _ppo_policy_and_ent_coef(
        cfg,
        policy_kwargs,
        env.action_space,
        getattr(env, "action_schema", None),
        env.observation_space,
    )
    ppo_model = PPO(
        policy,
        vec_env,
        policy_kwargs=policy_kwargs,
        **ppo_kwargs,
    )
    observation_schema = getattr(env, "observation_schema", None)
    if observation_schema is not None:
        schema_manifest = observation_schema.to_dict()
        cast(Any, ppo_model)._observation_schema = schema_manifest
        ppo_model.policy._observation_schema = schema_manifest
    regime_schema = getattr(env, "regime_observation_schema", None)
    if isinstance(regime_schema, dict):
        cast(Any, ppo_model)._regime_observation_schema = regime_schema
    setup_schema = getattr(env, "trade_setup_observation_schema", None)
    if isinstance(setup_schema, dict):
        cast(Any, ppo_model)._trade_setup_observation_schema = setup_schema
    candidate_schema = getattr(env, "candidate_geometry_observation_schema", None)
    if isinstance(candidate_schema, dict):
        cast(Any, ppo_model)._candidate_geometry_observation_schema = candidate_schema
        cast(Any, ppo_model.policy)._candidate_geometry_observation_schema = candidate_schema
    persist_action_schema(ppo_model, env)
    from learning.rl.rollout_buffer import install_single_copy_add

    install_single_copy_add(ppo_model.rollout_buffer)
    # CUDA graphs need a GPU; on other devices the same eager path runs, so one config serves both.
    on_cuda = device is not None and torch.device(device).type == "cuda"
    if bool(cfg.ppo.get("rollout_feature_graph", False)) and on_cuda:
        enable_feature_graph = getattr(ppo_model.policy, "enable_feature_graph", None)
        if enable_feature_graph is None:
            raise ValueError("ppo.rollout_feature_graph requires a hybrid policy")
        enable_feature_graph()
    if bool(cfg.ppo.get("rollout_host_mask_check", False)):
        from learning.rl.host_mask_check import install_host_mask_check

        install_host_mask_check(ppo_model)
    if bool(cfg.ppo.get("rollout_policy_graph", False)):
        if not bool(cfg.ppo.get("rollout_host_mask_check", False)):
            raise ValueError("ppo.rollout_policy_graph requires ppo.rollout_host_mask_check")
        if on_cuda:
            enable_policy_graph = cast(Any, ppo_model.policy).enable_rollout_policy_graph
            enable_policy_graph()
    if bool(cfg.ppo.get("torch_compile_features", False)) and on_cuda:
        # Compile the extractor's forward in place: state-dict names and parameters stay unchanged.
        extractor = ppo_model.policy.features_extractor
        extractor.forward = torch.compile(extractor.forward, dynamic=False)
    if bool(cfg.ppo.get("update_graph", False)):
        from learning.rl.update_graph import install_graphed_update

        install_graphed_update(ppo_model)
    if bool(cfg.ppo.get("overlap_collect", False)):
        from omegaconf import OmegaConf

        from learning.rl.overlap_collect import install_overlap_collect

        # Separate snapshot policy for collection: built from the same config, never trained.
        snapshot_cfg = cast(DictConfig, OmegaConf.create(OmegaConf.to_container(cfg, resolve=True)))
        snapshot_cfg.ppo.overlap_collect = False
        snapshot = build_agent(
            env, snapshot_cfg, arch=arch, algo=algo, device=device, env_fn=None, seed=seed
        )
        install_overlap_collect(ppo_model, snapshot)
    return _finalize_cuda_policy(ppo_model, device, _autocast_override(cfg))


def _validate_survival_objective_config(cfg: DictConfig, algo: str) -> None:
    """Require undiscounted learning for the terminal survival objective.

    Args:
        cfg: Effective run configuration.
        algo: Selected learner algorithm.

    Raises:
        ValueError: If discounting would change the binary path-survival objective.
    """
    if str(cfg.env.get("reward_mode", "dsr")).strip().lower() != "survival":
        return
    if algo == "ppo":
        if float(cfg.ppo.gamma) != 1.0 or float(cfg.ppo.gae_lambda) != 1.0:
            raise ValueError("survival reward requires PPO gamma=1 and gae_lambda=1")
    elif algo == "sac":
        sac_cfg = cfg.get("sac", cfg.get("ppo", {}))
        if float(sac_cfg.get("gamma", 0.99)) != 1.0:
            raise ValueError("survival reward requires SAC gamma=1")
    else:
        raise ValueError(f"survival reward is unsupported for algo={algo!r}")


def _ppo_policy_and_ent_coef(
    cfg: DictConfig,
    policy_kwargs: dict[str, Any],
    action_space: spaces.Space[Any],
    action_schema: ActionSchema | TradeSetupActionSchema | None = None,
    observation_space: spaces.Space[Any] | None = None,
) -> tuple[Any, dict[str, Any], float]:
    """Box overlay: clamp Gaussian std. Discrete: keep categorical entropy coef.

    Args:
        cfg: Run configuration used by this operation.
        policy_kwargs: Key-value data used for the policy kwargs.
        action_space: Action space used by the operation described above.
        action_schema: Action schema used by the operation described above.
        observation_space: Observation space used by the operation described above.

    Returns:
        Mapping from ``str`` keys to ``Any], float`` values.
    """
    ent_coef = float(cfg.ppo.ent_coef)
    if not isinstance(action_space, spaces.Box):
        if str(cfg.ppo.get("policy_distribution", "clamped_diagonal_gaussian")) != (
            "clamped_diagonal_gaussian"
        ):
            raise ValueError("configured policy_distribution requires a Box action space")
        return "MultiInputPolicy", policy_kwargs, ent_coef
    actor_arch = str(cfg.ppo.get("actor_arch", "shared"))
    policy_distribution = str(cfg.ppo.get("policy_distribution", "clamped_diagonal_gaussian"))
    if policy_distribution in {
        "hybrid_v1",
        "trade_setup_hybrid_v1",
        "trade_setup_conditioned_v1",
        "trade_setup_candidate_geometry_v1",
    }:
        if actor_arch != "shared":
            raise ValueError("hybrid PPO distributions require ppo.actor_arch='shared'")
        setup_distribution = policy_distribution in {
            "trade_setup_hybrid_v1",
            "trade_setup_conditioned_v1",
            "trade_setup_candidate_geometry_v1",
        }
        conditioned_distribution = policy_distribution == "trade_setup_conditioned_v1"
        candidate_geometry_distribution = policy_distribution == "trade_setup_candidate_geometry_v1"
        if setup_distribution:
            if not isinstance(action_schema, TradeSetupActionSchema):
                raise ValueError(f"{policy_distribution} requires its matching action schema")
            observation_spaces = getattr(observation_space, "spaces", {})
            if "trade_setup_mask" not in observation_spaces:
                raise ValueError(f"{policy_distribution} requires the trade_setup_mask observation")
            if candidate_geometry_distribution:
                required_candidate_keys = {
                    "candidate_ids",
                    "candidate_features",
                    "candidate_mask",
                }
                missing_candidate_keys = sorted(
                    required_candidate_keys.difference(observation_spaces)
                )
                if missing_candidate_keys:
                    raise ValueError(
                        "trade_setup_candidate_geometry_v1 requires candidate observations: "
                        f"{missing_candidate_keys}"
                    )
                if not action_schema.has_entry_execution:
                    raise ValueError(
                        "trade_setup_candidate_geometry_v1 requires entry-execution coordinates"
                    )
        elif not isinstance(action_schema, ActionSchema):
            raise ValueError("hybrid_v1 requires a declared legacy strategy ActionSchema")
        if not setup_distribution and not isinstance(action_schema, ActionSchema):
            raise ValueError("hybrid_v1 requires a standard strategy action schema")
        if "exit" in action_schema.names and not bool(cfg.env.get("allow_ema_exit", True)):
            raise ValueError(
                "hybrid policy requires the EMA/structural exit coordinate to be active"
            )
        from learning.rl.hybrid import (
            HybridClampedStdMultiInputPolicy,
            TradeSetupConditionedClampedStdMultiInputPolicy,
        )

        kwargs = dict(policy_kwargs)
        kwargs["hybrid_action_coordinates"] = action_schema.names
        kwargs["trade_setup_mask_key"] = "trade_setup_mask" if setup_distribution else None
        kwargs["sl_mode_defer_threshold"] = float(cfg.env.get("sl_mode_defer_threshold", 0.1))
        kwargs["tp_mode_defer_threshold"] = float(cfg.env.get("tp_mode_defer_threshold", 0.1))
        kwargs["log_std_init"] = float(cfg.ppo.get("log_std_init", 0.0))
        kwargs["log_std_min"] = float(cfg.ppo.get("log_std_min", -0.7))
        kwargs["log_std_max"] = float(cfg.ppo.get("log_std_max", 0.0))
        kwargs["mode_prior_coef"] = float(cfg.ppo.get("mode_prior_coef", 1e-3))
        policy_cls: Any = HybridClampedStdMultiInputPolicy
        if conditioned_distribution:
            conditioned_cfg = cfg.ppo.get("trade_setup_conditioned", {})
            kwargs["trade_setup_embedding_dim"] = int(conditioned_cfg.get("embedding_dim", 32))
            kwargs["trade_setup_execution_hidden_dim"] = int(
                conditioned_cfg.get("execution_hidden_dim", 128)
            )
            policy_cls = TradeSetupConditionedClampedStdMultiInputPolicy
        elif candidate_geometry_distribution:
            from learning.rl.candidate_geometry_policy import (
                CandidateGeometryClampedStdMultiInputPolicy,
            )

            candidate_cfg = cfg.ppo.get("candidate_geometry", {})
            kwargs["candidate_ids_key"] = "candidate_ids"
            kwargs["candidate_features_key"] = "candidate_features"
            kwargs["candidate_mask_key"] = "candidate_mask"
            kwargs["candidate_embedding_dim"] = int(candidate_cfg.get("embedding_dim", 32))
            kwargs["candidate_execution_hidden_dim"] = int(
                candidate_cfg.get("execution_hidden_dim", 128)
            )
            kwargs["max_limit_offset_atr"] = float(
                cfg.execution.get("limit_order_max_offset_atr", 1.0)
            )
            kwargs["max_limit_ttl_bars"] = int(cfg.execution.get("limit_order_max_ttl_bars", 60))
            policy_cls = CandidateGeometryClampedStdMultiInputPolicy
        return (
            policy_cls,
            kwargs,
            float(cfg.ppo.get("ent_coef_continuous", 0.001)),
        )
    if policy_distribution != "clamped_diagonal_gaussian":
        raise ValueError(f"unknown PPO policy_distribution: {policy_distribution!r}")
    if actor_arch == "semantic_heads":
        from learning.rl.semantic import SemanticClampedStdMultiInputPolicy

        policy_cls = SemanticClampedStdMultiInputPolicy
    elif actor_arch == "shared":
        policy_cls = ClampedStdMultiInputPolicy
    else:
        raise ValueError(f"unknown PPO actor_arch: {actor_arch!r}")

    kwargs = dict(policy_kwargs)
    kwargs["log_std_init"] = float(cfg.ppo.get("log_std_init", 0.0))
    kwargs["log_std_min"] = float(cfg.ppo.get("log_std_min", -0.7))
    kwargs["log_std_max"] = float(cfg.ppo.get("log_std_max", 0.0))
    kwargs["mode_prior_coef"] = float(cfg.ppo.get("mode_prior_coef", 1e-3))
    return policy_cls, kwargs, float(cfg.ppo.get("ent_coef_continuous", 0.001))


def _autocast_override(cfg: Any) -> str:
    """Read the GPU-specific autocast override (``compute.autocast_dtype``, default auto).

    Args:
        cfg: Run configuration mapping.

    Returns:
        The configured autocast dtype name, ``auto`` when unset.
    """
    compute = cfg.get("compute", {}) if hasattr(cfg, "get") else {}
    return str(compute.get("autocast_dtype", "auto")) if hasattr(compute, "get") else "auto"


def _finalize_cuda_policy(
    model: Any, device: str | torch.device | None, autocast: str = "auto"
) -> Any:
    """Enable bf16 encoder autocast when the policy lives on CUDA.

    Args:
        model: Model used for this operation.
        device: Compute device on which to perform the operation.
        autocast: Encoder autocast override from compute.autocast_dtype (auto keeps the default).

    Returns:
        Result of enable bf16 encoder autocast when the policy lives on CUDA.
    """
    if device is None:
        return model
    dev = device if isinstance(device, torch.device) else torch.device(device)
    if dev.type != "cuda":
        return model
    policy = getattr(model, "policy", None)
    if policy is None:
        return model

        # PPO exposes one extractor on the policy. SAC keeps separate feature
        # extractors on its actor, critic, and target critic instead.
    extractors = [getattr(policy, "features_extractor", None)]
    for component_name in ("actor", "critic", "critic_target"):
        component = getattr(policy, component_name, None)
        if component is not None:
            extractors.append(getattr(component, "features_extractor", None))

    autocast_dtype = get_autocast_dtype(dev, autocast)
    seen_extractors: set[int] = set()
    for extractor in extractors:
        if extractor is None or id(extractor) in seen_extractors:
            continue
        seen_extractors.add(id(extractor))
        enable_extractor_autocast(extractor, autocast_dtype)
    return model
