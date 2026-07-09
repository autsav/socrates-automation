# Task F report — team/content_writer.py

## What was built

- `team/content_writer.py` — mirrors `team/planner.py`/`team/analytics_analyst.py`:
  - Module-level `_PREFIX` template + `build_prompt(plan: ContentPlan) -> str`, which embeds
    `json.dumps(plan.to_dict(), indent=2)` and tells the model to return one `CopySpec` per
    post (matching the plan's assigned `hook_strategy`/`audience`/`mood`/`format` per
    `post_number` rather than inventing its own direction), plus the `format`
    ("reel"/"carousel"/"single") rule: only populate `carousel_slides` with real content when
    `format == "carousel"`, empty list otherwise fine. This is prompt text only — no
    format-specific branching in code, since `plan.to_dict()` already carries each post's
    `format` field for the model to read.
  - Module-level `parse_response(d: dict) -> list[CopySpec]`, mapping `d["items"]` through
    `CopySpec.from_dict`, preserving response order (no re-sorting).
  - `ContentWriterAgent.__init__(self, client)` — loads `system_prompt = load_prompt("content_writer")`.
  - `ContentWriterAgent.run(self, plan: ContentPlan) -> list[CopySpec]` — builds the prompt,
    calls `self.client.call("content_writer", shared_prefix, self.system_prompt, "Write the
    copy for all 7 posts now.", COPY_SPECS_SCHEMA)`, returns `parse_response(data)`.
- `tests/test_team_content_writer.py` — same `_FakeClient` mocking convention as
  `tests/test_team_analytics_analyst.py`/`tests/test_team_planner.py`. Covers:
  - `build_prompt` embeds plan content (hook_strategy, controversy_question, date).
  - `parse_response` returns 7 `CopySpec`s, order preserved (`post_number` 1..7).
  - `run()` builds the correct `CopySpec` list from a mocked `{"items": [...]}` payload
    (count, field values, post_number ordering).
  - `role == "content_writer"` passed to `client.call`.
  - Prompt/context passed to `client.call` contains plan-identifying content
    (`hook_strategy`, `controversy_question`) — smoke check that plan data reaches the model.
  - A plan with mixed `reel`/`carousel`/`single` posts is handled identically (same call
    path, 7 specs back); additionally asserts via `inspect.getsource(ContentWriterAgent.run)`
    that no `"carousel"` string literal appears in the method body, confirming the
    format distinction stays prompt-level, not a code branch.

## Deviations from the brief

None. Dependencies (Task A `team/models.py`/`ContentPlan`/`CopySpec`/`COPY_SPECS_SCHEMA`,
`team/prompt_loader.load_prompt`; Task B `team/prompts/content_writer.md`;
`studio/settings.py` role registration for `content_writer`) were all already present in the
repo from prior tasks — nothing needed to be added to them. `pipeline.py` and `src/` were not
touched.

## Test results

```
cd "/Users/utsab1/Documents/socrates automation" && source .venv/bin/activate
python -m pytest tests/test_team_content_writer.py -q
# 6 passed in 0.02s

python -m pytest tests/test_team_*.py -q
# 43 passed in 0.24s
```

Full-repo `pytest -q` still shows the pre-existing collection errors in 12 legacy
`tests/test_*.py` files (e.g. `test_ab_test.py`, `test_data_store.py`, `test_imports.py`) and
one pre-existing failure in `socrates_pipeline/tests/test_image_generator.py::test_generate_background_success` — these predate this task (unrelated to `team/` package, caused by the
`src/` reorg per prior commits) and are unaffected by this change; confirmed the `team/`-scoped
suite is fully green.

## Signature

Task F complete. `team/content_writer.py` + `tests/test_team_content_writer.py` implemented
per brief, TDD (test written first, confirmed red on missing module, then green).

DONE — one-line summary: added `ContentWriterAgent` (build_prompt/parse_response + thin
class) mirroring planner/analytics_analyst pattern; all 6 new tests + full 43-test team/
suite pass.
