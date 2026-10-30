# Testing rules

Applies to this repo's pytest setup (`tests/`).

## Coverage target: 80% minimum

```bash
./tools/check unit
```

Test types required for features:
1. **Unit tests** — production behavior at an isolated package boundary, under `tests/unit/<domain>/`.
2. **Integration tests** — interactions across packages and controlled I/O, under `tests/integration/`.
3. **Architecture tests** — package ownership, imports, and repository contracts under `tests/architecture/`.
4. **Research tests** — evidence protocols and larger analysis checks under `tests/research/`.

## Test-driven development (mandatory for new features)

1. Write the test first (RED) — it should FAIL.
2. Run it to confirm failure.
3. Write minimal implementation (GREEN).
4. Refactor (IMPROVE) while keeping coverage ≥ 80%.

Fix the implementation, not the tests — unless the tests are wrong.

## Structure

- **AAA pattern**: Arrange → Act → Assert.
- **Descriptive names** explaining behavior:
  - `test_sweep_reward_penalizes_early_entry`
  - `test_env_raises_when_action_out_of_bounds`
- Name test modules and test functions after the production behavior or contract
  they verify. Do not name them after a plan, phase, work package, or test-suite
  category; the `tests/unit/`, `tests/integration/`, `tests/research/`, and
  `tests/architecture/` directories already express the suite category.
- Test observable behavior and public contracts. Avoid tests that only assert
  that a forwarding module re-exports the same object; test the owning behavior
  and remove redundant forwarding layers when no external contract requires them.
- Categorize with pytest markers:

```python
@pytest.mark.unit
def test_cosine_similarity_returns_one_for_identical_vectors(): ...


@pytest.mark.integration
def test_trading_env_episode_loop_updates_account_equity(): ...
```

## Relations

- Activates: any new feature, bug fix, or change to `features/`, `trading/`, `simulation/`, or environment logic.
- Enforced at commit by [git-commit-rules.md](git-commit-rules.md); orchestrated by [development-workflow.md](development-workflow.md); test runs follow [token-efficient-shell.md](token-efficient-shell.md).
