# Orchestra commands

`orchestra/commands/` provides CLI command handlers for task execution,
planning, status, recovery, and maintenance. The handlers use Orchestra's task
lifecycle and state model; they do not own trading or experiment semantics.

Commands that launch external tools should preserve task identity and logs,
and destructive cleanup behavior must stay explicit. Focused tests are in
`tests/unit/orchestra/`.
