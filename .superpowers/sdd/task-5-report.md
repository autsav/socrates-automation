# Task 5 report — team/debate.py

## Files added

- `team/debate.py`
- `tests/test_team_debate.py`

## Final signature

```python
def run_debate(
    planner: PlannerAgent,
    reviewer: ReviewerAgent,
    analytics_report,
    quotes_pool: list[dict],
    *,
    max_rounds: int = 3,
    approval_threshold: float = 8.0,
    now: datetime | None = None,
) -> tuple[ContentPlan, list[DebateResult]]: ...
```

Matches the brief's given signature exactly. Implementation is a plain `while True` loop:
each iteration increments `round_number`, calls `planner.run(analytics_report, quotes_pool,
feedback=feedback, now=now)` then `reviewer.run(plan, analytics_report)`, computes
`approved = review["score"] >= approval_threshold` (the reviewer's own `"approved"` key is never
read), appends a `DebateResult`, and returns `(plan, history)` immediately if `approved` or
`round_number == max_rounds`. Otherwise builds a feedback string via a small `_build_feedback`
helper (critique paragraph, then a `"Specific weaknesses:"` bullet list from `weaknesses`, then a
`"Required improvements:"` bullet list from `improvement_suggestions`) and loops again with that
feedback passed to the next `planner.run` call.

No randomness anywhere in the function — round count and approval outcome are a pure function of
the planner/reviewer doubles' returned values, satisfying the "debate loop must be deterministic"
requirement.

## Deviations from the brief

None. Implementation follows the brief's pseudocode and behavior spec directly.

## Test coverage

`tests/test_team_debate.py` (8 tests) using fake `PlannerAgent`/`ReviewerAgent` doubles (plain
objects with `.run()`, no real `StudioClient`):

- Approved round 1 (`score=9.0`) → history length 1, `approved=True`, planner's `.run` called
  once with `feedback=None`.
- Not approved round 1 (`score=6.0`) then approved round 2 (`score=8.5`) → history length 2;
  round-2 planner call received non-`None` feedback containing the round-1 critique text, the
  flagged weakness, and the improvement suggestion; returned plan is round 2's plan (identity
  check via `is`).
- Never approved across 3 rounds (`score=5.0` every round, default `max_rounds=3`) → history
  length exactly 3, no exception raised, final entry `approved=False`, returned plan is round 3's
  plan (not round 1's), both planner and reviewer called exactly 3 times.
- Reviewer self-reported `"approved": False` contradicting a `score=9.0` → asserts the code's
  computed `approved=True` wins (the one authoritative-gate test explicitly called for in the
  brief).
- `max_rounds=1` stops after one round even though not approved.
- `approval_threshold=5.0` approves a `score=6.0` plan that the default 8.0 threshold (and the
  reviewer's own `approved=False`) would reject.
- Fixed `now` is passed through unchanged to every `planner.run` call across multiple rounds.
- `DebateResult` fields sanity check: `planner_output` is `json.dumps(plan.to_dict())`,
  `final_plan is plan`.

## Verification run

```
$ source .venv/bin/activate
$ python -m pytest tests/test_team_debate.py -q
8 passed in 0.01s

$ python -m pytest tests/test_team_debate.py tests/test_team_planner.py tests/test_team_reviewer.py \
    tests/test_team_models.py tests/test_team_analytics_analyst.py -q
37 passed in 0.17s
```

A full-repo `python -m pytest -q` still hits the same **pre-existing, unrelated** collection
error documented in `task-4-report.md` (duplicate test module basenames between `tests/` and
`socrates_pipeline/tests/` — `test_ab_test.py`, `test_analytics.py`, `test_config.py`, etc.).
Confirmed present on a clean checkout (before this task's changes) as well, so it's unrelated to
`team/debate.py`. Not fixed — out of scope for this task.

`pipeline.py` and `src/` were not touched.

## Status

DONE
