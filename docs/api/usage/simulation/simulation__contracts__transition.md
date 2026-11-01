# Simulation · `contracts.transition`

This page contains 3 public callable records owned by `simulation.contracts.transition`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `SimulationTransition`

**Kind:** class · **Status:** stable · **Owner:** `simulation.contracts.transition`

**Purpose:** Semantic outcome of advancing a simulator by one action.

**Exact API:** {py:obj}`simulation.contracts.transition.SimulationTransition` · **Source:** [simulation/contracts/transition.py:13](../../../../simulation/contracts/transition.py#L13)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SimulationTransition(...)
```

**Lifecycle context:** Semantic outcome of advancing a simulator by one action.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `SimulationTransition`

**Kind:** class · **Status:** stable · **Owner:** `simulation.contracts.transition`

**Purpose:** Semantic outcome of advancing a simulator by one action.

**Exact API:** {py:obj}`simulation.contracts.transition.SimulationTransition` · **Source:** [simulation/contracts/transition.py:13](../../../../simulation/contracts/transition.py#L13)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SimulationTransition(...)
```

**Lifecycle context:** Semantic outcome of advancing a simulator by one action.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `SimulationTransition.as_gymnasium`

**Kind:** method · **Status:** stable · **Owner:** `simulation.contracts.transition`

**Purpose:** Adapt this transition to Gymnasium's five-value step protocol.

**Exact API:** {py:obj}`simulation.contracts.transition.SimulationTransition.as_gymnasium` · **Source:** [simulation/contracts/transition.py:22](../../../../simulation/contracts/transition.py#L22)

**Inputs and outputs:**

- **Returns:**

  ```text
  Whether as gymnasium meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SimulationTransition(...)
result = instance.as_gymnasium()
```

**Lifecycle context:** This callable participates in `SimulationTransition`: Semantic outcome of advancing a simulator by one action. Related public lifecycle methods: {py:obj}`simulation.contracts.transition.SimulationTransition.as_gymnasium`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
