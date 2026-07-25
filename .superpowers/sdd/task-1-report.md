# Task 1: Rubric subscores + score_hook — Completion Report

**Status:** COMPLETE ✓

## Summary

Implemented subscore decomposition and hook-specialist scoring for the rubric system. All tests passing; no regressions in existing test suite.

## Files Modified

- `studio/rubric.py`: Added `score_story_detailed()`, `score_hook()`, `_clamp10()`, and `_WEAKNESS` constant
- `tests/test_rubric_detailed.py`: Created (5 new tests)

## Implementation Details

### New Constants
- `_WEAKNESS` dict: Maps subscore keys to weakness strings (hook/escalation/cta/simplicity)

### New Functions

**`_clamp10(x: float) -> float`**
- Clamps float to [0.0, 10.0] range
- Helper for subscore bounding

**`score_story_detailed(d: dict) -> dict`**
- Decomposes existing `score_story()` logic into 4 subscores
- Returns: `{hook, escalation, cta, simplicity, total, weaknesses}`
- Subscores: 0–10 each, clamped
- Total: weighted average (hook 40%, escalation 25%, cta 20%, simplicity 15%)
- Weaknesses: list of strings (one per subscore ≤ 4.0)
- Gracefully handles empty/malformed input (returns all zeros + empty weaknesses)

**`score_hook(hook: str) -> float`**
- Specialist pass for hook refinement
- Base score 5.0 + concrete hints (×2.0) − abstractions (×2.0)
- Penalties: question mark (−3.0), formulaic phrases (−3.0 each)
- Returns: max(0.0, rounded to 4 decimals)
- Never raises on any input

## Test Coverage

**New tests (5/5 passing):**
- `test_subscores_in_range_and_keys` → validates subscore ranges and required keys
- `test_weak_hook_gets_weakness_string` → verifies weakness string generation and ordering
- `test_total_orders_like_score_story` → ensures total maintains existing ordering (contract validation)
- `test_garbage_never_raises` → confirms graceful empty-input handling
- `test_score_hook_ordering` → verifies concrete vs. abstract discrimination

**Existing tests (5/5 still passing):**
- `tests/test_rubric.py` unchanged; `score_story()` behavior preserved

**Full suite:** 765 tests passing (0 regressions)

## Ordering Contract

The test pair (STRONG/WEAK_HOOK) validates that the new subscore weighting maintains existing `score_story()` ordering. Confirmed passing without subscore constant tuning.

## Commit

```
feat(rubric): subscore decomposition + hook scoring (spec 1)
```

Commit hash: `2552c67`

## Concerns

None. All specifications met; test coverage complete; no regressions.
