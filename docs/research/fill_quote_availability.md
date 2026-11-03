# Fill quote availability in local tick exports

This analysis aligns recovered selected-run fill timestamps with the matching
local MT5 tick export. It asks whether each event timestamp falls in a source
quote group with missing required sides, side values carried by the configured
parser, or changed quotes sharing the same exported timestamp.

The [evidence packet](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/fill_quote_source_alignment)
contains the run-linked report, input hashes, and regeneration command. It
compares both selected arms in one scan of the US100 training tick file.

## Selected-campaign result

The scan matched all 3,698 tick-backed fill events across both ledgers: 1,812
entries and 1,886 exits. Sixteen events fell in timestamp groups whose quote
values changed at the exported timestamp precision. Eighty-seven events were in
groups with a missing required quote side; for those events, the parser's
first valid quote used a carried required side. No timestamp parse failures or
out-of-order source rows were recorded in the scanned tick file. These are
source-group counts, not evidence that the parser's carried value was
executable when the order arrived.

Reproduce the exact measurements from
`evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json`.

## Interpretation

The configured `Etc/GMT-3` value is used to join exported tick wall times to
the UTC fill timestamps. The configuration describes a fixed-offset carrier
for source labels; this analysis does not establish the provider's timezone,
daylight-saving history, or session calendar.

Events are joined at the timestamp precision present in the export. If several
quotes share that timestamp, the report records the changed values and source
row order but does not infer which quote came first in real time. A carried
bid or ask is a parser behavior, not proof that both sides were simultaneously
available to the order. The report does not reconstruct broker order arrival
or prove the quote actually used by the selected run.

The result is therefore a local source-alignment diagnostic. It can expose
dependence on ambiguous quote groups; it cannot validate fills or establish
the source clock on its own.

The refreshed report retains reported and reconstructed required-side prices,
same-timestamp price extrema, carried-side age, and order/arrival/fill timing.
It still does not establish source order within tied timestamps or actual
broker executability. No no-carry or next-valid-quote economic sensitivity has
been computed; timestamp-group extrema are descriptive source diagnostics,
not executable price bounds.
