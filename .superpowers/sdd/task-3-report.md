# Task C report — team/analytics_analyst.py

## Final `run()` signature

```python
class AnalyticsAnalystAgent:
    def __init__(self, client: StudioClient): ...
    def run(self, window_days: int = 90, now: datetime | None = None) -> AnalyticsReport: ...
```

- `now` defaults to `datetime.utcnow()` inside the method (mirrors `studio/analyst.py`'s
  `get_or_build_brief(client, *, now=None)` pattern), so tests can inject a fixed date.
- `window_days` controls `data_store.aggregate_performance(window_days)`. Hook-tracker calls use
  `hook_window = min(window_days, 30)` since `hook_tracker`'s own functions are designed around a
  30-day default window — never requested more days than that.
- Stats bundle passed to the model: `{date, window_days, performance, hook_rankings,
  hook_leaderboard}` — `performance` from `data_store.aggregate_performance`, `hook_rankings` from
  `hook_tracker.get_all_hook_rankings(window_days=hook_window)`, `hook_leaderboard` from
  `hook_tracker.get_hook_leaderboard(window_days=hook_window)` (included so the model has the
  `needs_more_data`/`min_trials`-qualified list on hand when deciding `worst_performing_content`,
  rather than the code special-casing it).
- `shared_prefix` built with `json.dumps(stats, indent=2)`, same convention as
  `studio/analyst.py::build_prompt`.
- Calls `self.client.call("analytics_analyst", shared_prefix, self.system_prompt,
  "Generate the AnalyticsReport now.", ANALYTICS_REPORT_SCHEMA)` and parses with
  `AnalyticsReport.from_dict`. No fallback/special-case branch for `sample_size == 0` — always
  calls through, per brief (error handling is a later task's job).

## Mocking approach

Followed `tests/test_studio_analyst.py`'s convention: a small `_FakeClient` class with a `.call()`
method that records every call's args and returns a canned payload dict, instead of mocking
`StudioClient` itself. `team.analytics_analyst.data_store` and `team.analytics_analyst.hook_tracker`
are patched via `unittest.mock.patch` (module-level, not the underlying `src.core.data_store` /
`src.analytics.hook_tracker` modules) so no real DB is needed — this mirrors how
`test_studio_analyst.py` patches `analyst.data_store.aggregate_performance` in an autouse fixture.

## Tests (`tests/test_team_analytics_analyst.py`)

5 tests:
1. `test_run_builds_valid_analytics_report` — `run()` returns an `AnalyticsReport` built from the
   mocked `client.call` payload.
2. `test_run_passes_role_and_stats_to_client` — asserts `role == "analytics_analyst"` and that the
   real seeded fake stats (`42`, `"hook_a"`, `"stoic_calm"`) appear in `shared_prefix`.
3. `test_run_requests_hook_rankings_within_30_day_cap` — `aggregate_performance` called with the
   full `window_days`; `get_all_hook_rankings` called with `window_days <= 30`.
4. `test_run_uses_fixed_now_for_deterministic_date` — a fixed `now` produces a deterministic
   `"2026-01-15"` in the prompt.
5. `test_run_handles_zero_sample_size_without_special_case` — `sample_size == 0` still results in
   exactly one `client.call`, returning an honest zeroed/empty `AnalyticsReport` with no
   code-level fallback branch.

## Verification

```
python -m pytest tests/test_team_analytics_analyst.py -q      → 5 passed
python -m pytest tests/test_analytics.py tests/test_studio_analyst.py -q  → 7 passed
python -m pytest tests/ -q  → 177 passed, 2 failed (test_reel_composer.py — pre-existing,
                               unrelated RuntimeError from ffmpeg/codec conversion, confirmed
                               failing identically before this change was added)
```

`pipeline.py` and `src/` were not modified.
