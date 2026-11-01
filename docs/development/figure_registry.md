# Figure and diagram registry

Machine-readable metadata is maintained in [`figure_registry.json`](../figure_registry.json)
and checked by `tools.documentation.figures` in the docs gate.

Every maintained figure needs a title/alt description, an owner, source or
generator, provenance/license status, and a linked explanation. Mermaid
diagrams are source text in the page and are therefore versioned with their
explanation. A copied bitmap without a recorded source is not acceptable.

## Current authored diagrams

| Figure | Source | Provenance | Accessibility/context |
|---|---|---|---|
| Data-to-policy-to-evidence flow | `../index.md` Mermaid source | Newly authored from current architecture | The adjacent text names each stage and links the reader paths. |
| Observation to intent flow | `../concepts/observations_and_actions.md` | Newly authored from decisioning contracts | Flow labels distinguish policy proposal from execution checks. |
| PPO rollout/update geometry | `../concepts/ppo_rollout_geometry.md` prose/equations | Newly authored from agent builder and manifests | Text gives equations and the source fields for non-visual readers. |
| Trade lifecycle | `../concepts/trade_lifecycle.md` Mermaid source | Newly authored after checking environment/runtime order | The nearby stage-by-stage text and symptom table explain each node. |
| Environment step sequence | `../architecture/runtime/environment_step.md` Mermaid source | Existing project-authored diagram | Chronology is followed by an explicit explanation of fill timing. |

## Binary research figures already tracked

| Asset | Owner/source | License/provenance status | Use |
|---|---|---|---|
| `docs/research/figures/setup_conditioned_policy_replay_equity.png` | Generated research evidence; source evidence packet is linked from its finding | Repository evidence asset; consult packet for inputs and limitations | Historical exploratory screen only; see the finding page and evidence status. |

## Supplementary archive exclusions

No binary figure from the supplementary archive is copied into this portal by
this documentation pass.
The archive includes publication-derived figures whose reuse permission is not
established by the ZIP, plus custom project figures with differing source
histories. See the [source map](supplementary_source_map.md). The archive's
license is not assumed to cover all embedded assets.

Before adding an image, record its repository-relative path, caption, alt text,
creator/generator, input/source commit, license or permission, citation, and
the page that explains it. Remove or redirect a page only after checking for
references to its assets.

## V3 vector teaching figures

The following original SVGs supplement the source diagrams with labeled visual
sequences. Each is registered in `figure_registry.json`, has an accessible
caption on its source page, and is project-authored:

| Figure | Source | Teaching purpose |
|---|---|---|
| Feature availability | `../framework/market_data_and_features.md` | Shows why a higher-timeframe value is unavailable before candle close. |
| Policy action contract | `../concepts/observations_and_actions.md` | Separates policy intent, schema decoding, risk checks, and execution. |
| Trade geometry | `../concepts/risk_and_account_limits.md` | Connects stop distance, entry, and target for a long position. |
| Stop/target lifecycle | `../concepts/trade_lifecycle.md` | Shows recurring protection checks while a position is open. |
| Encoder composition | `../framework/models_and_learning.md` | Shows structured inputs flowing through encoders and policy head. |
| Rollout transitions | `../framework/evaluation_and_artifacts.md` | Shows observation/action/reward sequencing and episode boundary. |
| Evidence lineage | `../reproduce/result_registry.md` | Summarizes the increasing evidence needed at each reproduction level. |

These figures explain contracts and workflows. They are not empirical results;
research plots remain linked to their evidence packets and claim scopes.
