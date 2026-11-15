---
trigger: model_decision
description: "Use for the default repository work loop and stopping criteria."
---

# Core execution

Use the smallest complete loop:

```text
UNDERSTAND → LOCATE → VERIFY → DECIDE → EXECUTE → VALIDATE → STOP
```

1. **Understand:** state the requested outcome, acceptance checks, affected
   domain, dependencies, and whether the task is read-only or writable.
2. **Locate:** use the cheapest sufficient retrieval. Known path → read it;
   unknown symbol → scoped search; unknown code relationships → Code Review
   Graph; broader cross-artifact questions → Graphify; historical rationale →
   targeted Obsidian note.
3. **Verify:** source/config/tests decide current behavior. Graphs, notes, plans,
   and agent reports are navigation or historical context only.
4. **Decide:** execute in the root unless ready independent work makes
   delegation faster or materially improves correctness. Follow `delegation.md`.
5. **Execute:** make the smallest complete change, including directly affected
   callers, tests, configuration, and compatibility contracts. Avoid unrelated
   cleanup and speculative abstractions.
6. **Validate:** follow `validation-routing.md`; preserve failures and repair
   their root cause.
7. **Stop** when the requested outcome, acceptance checks, and required
   validation are satisfied. Do not search for unrelated improvements.
