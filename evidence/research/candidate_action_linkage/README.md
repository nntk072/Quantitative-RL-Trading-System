# Candidate action linkage

This audit joins statically eligible candidate proposal events to exact candidate ID and source-event IDs recorded in the matched development baseline decision traces. It also reports whether each decision timestamp falls inside the proposal event's recorded validity window. This is a temporal-overlap audit only: it does not identify a market/limit proposal chosen by the baseline action, link proposals to historical trained PPO rollouts, reconstruct account-state eligibility, or convert conditional outcomes into policy value.

See `linkage_manifest.json` for input identities, per-arm counts, and claim limits. Event overlaps, unmatched decision rows, and within-window rows are in `matched_baseline_candidate_actions.csv`, `unmatched_baseline_candidate_actions.csv`, and `within_proposal_window_actions.csv`.
