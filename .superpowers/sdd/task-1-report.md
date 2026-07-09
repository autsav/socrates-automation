# Task A report — Scaffolding: team/models.py, prompt_loader, studio role registration

## What was built

- `team/__init__.py` — empty package marker.
- `team/prompt_loader.py` — `load_prompt(name)` reading `team/prompts/<name>.md`, exactly as
  specified in the brief (the `team/prompts/` directory itself is not created by this task —
  no prompt markdown files were required here).
- `team/models.py` — 9 dataclasses (`PostPlan`, `ContentPlan`, `DebateResult`, `CopySpec`,
  `VisualSpec`, `AudioSpec`, `VideoSpec`, `EngagementSpec`, `AnalyticsReport`), each with
  `to_dict`/`from_dict`. Nested-dataclass handling: `ContentPlan.to_dict` serializes
  `posts` via `[p.to_dict() for p in self.posts]` / `from_dict` reconstructs via
  `[PostPlan.from_dict(p) for p in d["posts"]]`; `DebateResult.to_dict`/`from_dict` do the
  same for the nested `final_plan: ContentPlan`. All other dataclasses have only
  primitive/list/dict fields, so `to_dict` = `dataclasses.asdict(self)` and `from_dict` =
  `cls(**d)`, matching the `studio/types.py` convention exactly.
- 14 JSON schema constants + local `_obj(props, required)` helper (duplicated, not imported
  from `studio/types.py`, per the brief): `POST_PLAN_ITEM_SCHEMA`, `CONTENT_PLAN_SCHEMA`,
  `REVIEWER_OUTPUT_SCHEMA`, `COPY_SPEC_ITEM_SCHEMA`/`COPY_SPECS_SCHEMA`,
  `VISUAL_SPEC_ITEM_SCHEMA`/`VISUAL_SPECS_SCHEMA`, `AUDIO_SPEC_ITEM_SCHEMA`/`AUDIO_SPECS_SCHEMA`,
  `VIDEO_SPEC_ITEM_SCHEMA`/`VIDEO_SPECS_SCHEMA`,
  `ENGAGEMENT_SPEC_ITEM_SCHEMA`/`ENGAGEMENT_SPECS_SCHEMA`, `ANALYTICS_REPORT_SCHEMA`.
  All follow the brief's wrapping rules exactly: `CONTENT_PLAN_SCHEMA` embeds
  `POST_PLAN_ITEM_SCHEMA` directly under `posts` (not `items`-wrapped); the `*_SPECS_SCHEMA`
  constants wrap their item schema as `_obj({"items": {"type": "array", "items": ITEM_SCHEMA}}, ["items"])`;
  `REVIEWER_OUTPUT_SCHEMA` and `ANALYTICS_REPORT_SCHEMA` are bare object schemas (no wrapping).
  Every schema has `"additionalProperties": False` and `required` listing every property key.
- `studio/settings.py` — added the 8 new role keys (`planner`, `reviewer`, `content_writer`,
  `visual_designer`, `audio_engineer`, `video_editor`, `engagement_strategist`,
  `analytics_analyst`) as literal entries inside the existing `ROLE_MODELS = {...}` /
  `ROLE_EFFORT = {...}` dict literals (not via `.update()`), with model/effort values exactly
  as specified in the brief. The existing 4 entries (`analyst`, `strategist`, `copywriter`,
  `director`) are untouched.
- `.gitignore` — added `team/output/` immediately after the existing `output/` line
  (harmless duplicate; confirmed via `git check-ignore -v team/output/anything` that the
  top-level `output/` rule already matched it before this addition).
- `team/output/.gitkeep` — created and force-added to git (`git add -f`) since both the
  pre-existing `output/` rule and the new `team/output/` rule in `.gitignore` match it; the
  directory needs to exist and be tracked in the repo even though its generated contents are
  ignored.
- `tests/test_team_models.py` — round-trip tests for all 9 dataclasses (including the two
  nested cases, `ContentPlan` and `DebateResult`), a loop over all 14 schema constants
  asserting `type: object`, `additionalProperties: False`, and that `properties.keys() ==
  required` (all fields required, as specified), explicit checks that `POST_PLAN_ITEM_SCHEMA`
  has all 15 required fields and `ANALYTICS_REPORT_SCHEMA` has all 10, and a
  `json.dumps(instance.to_dict())` smoke test for every dataclass instance.

## Deviations from the brief

None. Field names, schema names, and wrapping rules match the brief exactly as written.

## Test results

```
cd "/Users/utsab1/Documents/socrates automation" && source .venv/bin/activate
python -m pytest tests/test_team_models.py -q
# 13 passed in 0.02s

python -c "import studio.settings"
# no output / exit 0 — import succeeds

python -m pytest tests/test_studio_client.py tests/test_studio_analyst.py -q
# 10 passed in 0.11s
```

## Concerns

- Running the full `pytest -q` (no path filter) across the whole `tests/` directory produces
  12 collection errors ("import file mismatch") caused by a pre-existing, gitignored
  `socrates_pipeline/` nested repo that contains duplicate test module basenames (e.g.
  `socrates_pipeline/tests/test_config.py` vs `tests/test_config.py`). This is a pre-existing
  condition unrelated to this task's changes — confirmed present before any of my edits, and
  `socrates_pipeline/` is already gitignored (`.gitignore:8`). The brief's own verification
  section only asks for scoped `pytest` invocations (`tests/test_team_models.py`,
  `tests/test_studio_client.py tests/test_studio_analyst.py`), which all pass cleanly; I did
  not attempt to fix the pre-existing full-suite collection issue since it's out of this
  task's scope and touching it risked violating the "don't touch anything outside team/,
  studio/settings.py, .gitignore" constraint.
- `team/prompts/` directory does not exist yet — `load_prompt()` will raise
  `FileNotFoundError` until a later task populates it with the agents' markdown prompts. This
  matches the brief, which only specifies the loader, not the prompt files themselves.

## Status

DONE
