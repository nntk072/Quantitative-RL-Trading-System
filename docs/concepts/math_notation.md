# Mathematical notation

| Symbol | Meaning here |
|---|---|
| \(t\) | Decision/bar index; timestamps also carry timezone and availability semantics. |
| \(s_t\) / \(x_t\) | Environment state / latent market state. The latter is not fully observed. |
| \(o_t\) | Versioned observation exposed to the policy. |
| \(a_t\) | Policy action proposal under the configured action schema. |
| \(r_t\) | Scalar training reward for a transition; not necessarily net return. |
| \(c_t\) | Cost signal for an optional constrained-RL objective. |
| \(\pi(a\mid o)\) | Policy distribution over actions given the observation. |
| \(V(o)\), \(Q(o,a)\) | State-value and action-value estimates used by actor-critic methods. |
| \(\gamma\) | Discount factor for future reward. |
| \(\lambda\) | GAE trace parameter in PPO; in a primal-dual objective, \(\lambda_c\) denotes the cost multiplier. |
| \(\hat A_t\) | Estimated advantage used to weight policy updates. |
| \(R\) | Initial monetary risk for a position; an R-multiple divides outcome by this risk. |
| \(N\times T\) | Aggregate transitions in a rollout with \(N\) environments and \(T\) per-environment steps. |

For empirical results, specify the return sampling interval, units, annualization,
equity definition, and resampling unit. Notation does not replace the
implementation contract; see [metrics](../reference/metrics.md),
[reward definitions](../reference/rewards.md), and
[PPO rollout geometry](ppo_rollout_geometry.md).
