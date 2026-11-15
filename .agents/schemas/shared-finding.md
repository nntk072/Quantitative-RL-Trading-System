# Shared finding

Store one JSON object per line in `facts.jsonl`:

```json
{"fact":"<verified conclusion>","revision":"<source SHA>","source":"<path::symbol>","verified_by":"<canonical_role>","verified_at":"<UTC timestamp>","stale_if":["<path or condition>"]}
```

Record only conclusions verified in source, tests, config, or immutable
artifacts. Mark investigation hypotheses as speculative rather than facts.
