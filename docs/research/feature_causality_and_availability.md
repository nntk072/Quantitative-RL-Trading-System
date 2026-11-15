# Feature causality and availability

Feature values are valid policy inputs only when their source information was
available at the decision time. Bar labels alone do not prove availability;
the source event time, aggregation interval, and publication boundary must be
considered together.

## Decision timing

The policy acts after the current M1 bar has closed. A feature built from that
bar may be used at the decision, and a market order is evaluated against the
next eligible quote. Higher-timeframe values are usable only after their source
bar has closed. Align completed higher-timeframe rows forward in time; never
backfill a later value into an earlier decision.

Session eligibility is represented as a mask. It does not remove bars from
the feature sequence. Any fitted normalization state is estimated from the
training portion only and then applied without refitting to evaluation rows.

## Availability and missingness

Each feature contract must distinguish a valid zero from an unavailable value
when downstream policy behavior depends on that distinction. Use an explicit
validity value or temporal mask where the observation schema supports one.
Do not silently replace an unknown value with a neutral value unless that is
the declared feature meaning.

Stateful features need an explicit warm-up rule. Structural events that require
future confirmation become available only after the confirming bars have
closed. Candidate identity must be derived from information available at the
decision and must remain stable when later rows are removed.

## Verification expectations

Validate feature construction at the real decision boundary. Truncating every
input after a decision must leave that decision's features and candidate
geometry unchanged. A higher-timeframe value must not appear before its bar
closes. Rebuilds from the same source prefix and configuration must produce the
same feature rows and candidate identities.

These checks establish software-level prefix behavior for the tested inputs.
They do not establish external feed publication latency, quote availability,
logical-event cardinality, or live-broker execution. Report those limits
separately when empirical evidence is produced.

For the shared alignment convention, see
[multi-timeframe data alignment](multitimeframe_data_alignment.md). The
[validation protocol](validation_protocol.md) defines when refreshed evidence
is sufficient for training or selection.
