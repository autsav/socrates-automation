# Task G report — team/visual_designer.py + team/audio_engineer.py

## What was built

- `team/visual_designer.py` — mirrors `team/content_writer.py`:
  - Module-level `_PREFIX` template + `build_prompt(plan: ContentPlan, copy_specs:
    list[CopySpec]) -> str`, embedding `json.dumps(plan.to_dict(), indent=2)` and
    `json.dumps([c.to_dict() for c in copy_specs], indent=2)` so each post's `mood`,
    `visual_style`, `format` (from the plan) sit alongside every `CopySpec` (including its
    `hook` text) — the model matches them by `post_number` itself rather than the code
    pre-joining the two lists.
  - Module-level `parse_response(d: dict) -> list[VisualSpec]`, mapping `d["items"]` through
    `VisualSpec.from_dict`, preserving response order.
  - `VisualDesignerAgent.__init__(self, client)` — loads `system_prompt =
    load_prompt("visual_designer")`.
  - `VisualDesignerAgent.run(self, plan, copy_specs) -> list[VisualSpec]` — builds the
    prompt, calls `self.client.call("visual_designer", shared_prefix, self.system_prompt,
    "Design the visuals for all 7 posts now.", VISUAL_SPECS_SCHEMA)`, returns
    `parse_response(data)`.

- `team/audio_engineer.py` — same structure:
  - `build_prompt(plan, copy_specs)` embeds each post's `mood`, `audio_strategy`, `format`
    (plan) alongside each `CopySpec`'s `hook`/`caption` (the audio engineer needs the actual
    words to script/time a voiceover).
  - `parse_response(d) -> list[AudioSpec]` via `AudioSpec.from_dict`, order preserved.
  - `AudioEngineerAgent.run(self, plan, copy_specs) -> list[AudioSpec]` calls
    `self.client.call("audio_engineer", shared_prefix, self.system_prompt, "Design the audio
    for all 7 posts now.", AUDIO_SPECS_SCHEMA)`.

- `tests/test_team_visual_designer.py`, `tests/test_team_audio_engineer.py` — same
  `_FakeClient` mocking convention as `tests/test_team_content_writer.py`. Each covers:
  - `build_prompt` embeds identifying content from both `plan` (mood/visual_style or
    mood/audio_strategy) and `copy_specs` (hook, and caption for audio).
  - `parse_response` returns 7 specs of the correct dataclass type, `post_number` order
    preserved 1..7.
  - `run()` builds the correct spec list from a mocked `{"items": [...]}` payload (count,
    field values, ordering).
  - `role == "visual_designer"` / `role == "audio_engineer"` passed to `client.call`.
  - The shared prefix passed to `client.call` contains plan-identifying content (`mood`,
    `visual_style`/`audio_strategy`) and copy-identifying content (`hook`, `caption`) —
    confirms both inputs actually reach the model.

## Test results

```
cd "/Users/utsab1/Documents/socrates automation" && source .venv/bin/activate && \
  python -m pytest tests/test_team_visual_designer.py tests/test_team_audio_engineer.py -q
..........
10 passed in 0.02s
```

Full `team`-scoped suite (`tests/test_team_*.py`, 53 tests) also passes with no regressions.

Note: a full unscoped `pytest -q` from repo root pre-existingly errors during collection
(`import file mismatch` for `test_ab_test.py`, `test_analytics.py`, `test_config.py`,
`test_data_store.py`, `test_excel_reader.py`, `test_excel_reader_extended.py`,
`test_image_generator.py`, `test_imports.py`, `test_quote_generator.py`,
`test_reel_composer.py`, `test_scene_composer.py`, `test_token_manager.py`) because
`socrates_pipeline/tests/` has same-named modules as `tests/` and neither package uses
`__init__.py`-qualified imports. Verified via `git stash` that this predates this task's
changes entirely — unrelated to `team/`, out of scope (`pipeline.py`/`src/` untouched per
instructions).

## Deviations from the brief

None. Dependencies (Task A `team/models.py` — `VisualSpec`/`AudioSpec`/
`VISUAL_SPECS_SCHEMA`/`AUDIO_SPECS_SCHEMA`, `team/prompt_loader.load_prompt`; Task B
`team/prompts/visual_designer.md`/`team/prompts/audio_engineer.md`; `studio/settings.py`
role registration for both roles) were all already present in the repo from prior tasks.
`pipeline.py` and `src/` were not touched.
