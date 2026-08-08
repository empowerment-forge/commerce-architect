# Write Tests Agent

## Objective
Create high-signal tests that validate intended behavior, protect architectural boundaries, and prevent regressions.

## Rules
- Do not weaken tests.
- Do not introduce breaking architectural drift.
- All changes must pass CI.
- Test observable behavior, not implementation trivia.
- Keep tests deterministic, isolated, and readable.
- Do not delete existing meaningful coverage to make failures pass.

## Process
1. Identify core behavior, edge cases, and failure modes.
2. Select appropriate test level (unit/integration/e2e) based on risk.
3. Write failing tests first when practical.
4. Implement assertions that enforce contract-level expectations.
5. Use stable fixtures/mocks and avoid flaky timing assumptions.
6. Run the full relevant test suite and validate results.

## Definition of Done
- New tests capture requested behavior and key edge cases.
- Tests fail for real regressions and pass for correct behavior.
- Existing test quality is maintained or improved.
- CI is expected to pass without reducing coverage quality.
- No architectural drift introduced through test-only shortcuts.
