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
| Observation to order decision | `../concepts/observations_and_actions.md` | Mermaid flow based on decisioning contracts | Shows rejection and approved execution paths and where account state changes. |
| Feature availability at candle close | `../framework/market_data_and_features.md` | Mermaid sequence based on timeframe alignment | Distinguishes a forming source candle from the latest completed value. |
| Trade lifecycle | `../concepts/trade_lifecycle.md` Mermaid source | Reconciled with environment/runtime order | Shows the open-position loop and its partial and final exit paths. |
| Observation encoding and policy outputs | `../framework/models_and_learning.md` | Mermaid flow based on the observation and encoder contracts | Separates structured inputs, shared representation, and algorithm outputs. |
| Evaluation transition record | `../framework/evaluation_and_artifacts.md` | Mermaid flow based on the rollout contract | Connects each transition to the ledger and run manifest. |
| Environment step sequence | `../architecture/runtime/environment_step.md` Mermaid source | Existing project-authored diagram | Chronology is followed by an explicit explanation of fill timing. |

## Binary research figures already tracked

| Asset | Owner/source | License/provenance status | Use |
|---|---|---|---|
| `docs/research/figures/setup_conditioned_policy_replay_equity.png` | Generated research evidence; source evidence packet is linked from its finding | Repository evidence asset; consult packet for inputs and limitations | Historical exploratory screen only; see the finding page and evidence status. |

## Supplementary archive exclusions

No binary figure from the supplementary archive is currently used in this
portal.
The archive includes publication-derived figures whose reuse permission is not
established by the ZIP, plus custom project figures with differing source
histories. See the [source map](supplementary_source_map.md). The archive's
license is not assumed to cover all embedded assets.

Before adding an image, record its repository-relative path, caption, alt text,
creator/generator, input/source commit, license or permission, citation, and
the page that explains it. Remove or redirect a page only after checking for
references to its assets.

## Standalone SVG illustration

The price ladder uses an SVG because aligned levels and measured distances are
clearer in a plotted scale. Workflow and lifecycle diagrams stay inline with
their source pages, where their explanation and accessible text remain close:

| Figure | Source | Teaching purpose |
|---|---|---|
| Long-position price geometry | `../concepts/risk_and_account_limits.md` | Shows stop/entry/target levels and labels planned risk and reward distances. |

The standalone illustration explains a contract and is not an empirical
result; research plots remain linked to their evidence packets and claim
scopes.
