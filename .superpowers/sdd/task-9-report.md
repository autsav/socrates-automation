# Task J report — team/orchestrator.py (final task: wires the whole system together)

## What was built

- `team/orchestrator.py`:
  - `run_team_pipeline(dry_run: bool = True, *, client=None, now: datetime | None = None) -> dict`
    — matches the brief's signature exactly.
  - `client=None` path: lazily `from config import Config; cfg = Config(); client =
    StudioClient(cfg.ANTHROPIC_API_KEY)` (local import, so it's only touched when no client
    is injected — never during tests, which always inject a fake/mock client).
  - `data_store.init_db()` called unconditionally (idempotent, mirrors `studio/run.py`).
  - Sequential chain, exactly the dependency order in the brief: `AnalyticsAnalystAgent.run`
    → `_build_pool("quotes.xlsx")` → `run_debate(PlannerAgent(client), ReviewerAgent(client),
    analytics_report, quotes_pool, now=now)` → `ContentWriterAgent.run(approved_plan)` →
    `VisualDesignerAgent.run(approved_plan, copy_specs)` →
    `AudioEngineerAgent.run(approved_plan, copy_specs)` →
    `VideoEditorAgent.run(approved_plan, visual_specs, audio_specs)` →
    `EngagementStrategistAgent.run(approved_plan, copy_specs)`. No threading/concurrency, as
    directed.
  - Output file naming (`{date}` = `approved_plan.date`), written under `_OUTPUT_DIR =
    team/output/` (created if missing) as `json.dumps(..., indent=2)`:
    `approved_plan_{date}.json`, `analytics_report_{date}.json`, `copy_{date}.json` (bare
    plan/analytics dicts; `{"items": [...]}` wrapping for copy/visual/audio/video/engagement),
    `visual_specs_{date}.json`, `audio_specs_{date}.json`, `video_specs_{date}.json`,
    `engagement_specs_{date}.json`. Note the file-prefix key for copy specs is `"copy"` (per
    the brief's literal filename `copy_{date}.json`, not `copy_specs_{date}.json`) — this key
    is used both for the filename and as the corresponding key in the returned
    `output_paths` dict, so `output_paths` keys are `{"approved_plan", "analytics_report",
    "copy", "visual_specs", "audio_specs", "video_specs", "engagement_specs"}`.
  - Returns the plain dict specified in the brief (`analytics_report`, `approved_plan`,
    `debate_history`, `copy_specs`, `visual_specs`, `audio_specs`, `video_specs`,
    `engagement_specs`, `output_paths`).
  - `dry_run` is accepted and threaded through but does nothing further after the 7 files are
    written — no `pipeline.py` import or reference anywhere in the module (enforced by a
    dedicated test parsing the module's AST for imports).
  - `__main__` CLI block: `argparse` with a `--dry-run` flag; `dry_run=args.dry_run or True`
    (always `True` for now, per the brief), prints `{"output_paths": {...}}` as JSON.

- `tests/test_team_orchestrator.py` — a `Harness`/`wired` fixture patches every
  `team.orchestrator.XAgent` class (`AnalyticsAnalystAgent`, `PlannerAgent`, `ReviewerAgent`,
  `ContentWriterAgent`, `VisualDesignerAgent`, `AudioEngineerAgent`, `VideoEditorAgent`,
  `EngagementStrategistAgent`), `run_debate`, `_build_pool`, `data_store.init_db`, and
  `_OUTPUT_DIR` (→ `tmp_path`) via `monkeypatch`, with canned 7-post dataclass instances for
  every spec type. Each patched class/function records into a shared `call_log` list so call
  order across the whole chain can be asserted directly. Covers:
  - `test_calls_agents_in_correct_dependency_order` — full call-order assertion (15 steps:
    analytics init+run, planner/reviewer init, `run_debate`, then each remaining agent's
    init+run in order) plus per-call argument assertions (every agent constructed with the
    injected client; `run_debate` got the planner/reviewer instances + analytics report +
    pool; `content_writer.run` got the plan `run_debate` produced; `video_editor.run` got
    both `visual_specs` and `audio_specs` from the earlier steps; etc.).
  - `test_now_threaded_through_to_analytics_and_debate` — `now` reaches both
    `AnalyticsAnalystAgent.run` and `run_debate`.
  - `test_writes_all_seven_output_files_with_expected_shapes` — all 7 files exist under
    `tmp_path` with the exact expected filenames and JSON payloads (bare dict for
    plan/analytics, `{"items": [...]}` for the rest).
  - `test_returned_dict_has_all_expected_keys` — every top-level key present and correct.
  - `test_client_none_builds_real_client_from_config` — patches `config.Config` and
    `team.orchestrator.StudioClient`; asserts `Config()` called, `StudioClient` constructed
    with the mocked config's `ANTHROPIC_API_KEY`, and that constructed (mock) client is what
    gets threaded into every agent. No real network/credentials touched.
  - `test_dry_run_false_returns_same_shape_and_does_not_touch_pipeline` — `dry_run=False`
    doesn't raise and returns the identical dict shape.
  - `test_orchestrator_module_never_imports_pipeline` — AST-parses
    `inspect.getsource(orchestrator)`'s import statements and asserts none resolve to a
    `pipeline` module (deliberately not a blanket substring check on the word "pipeline",
    since the function name `run_team_pipeline` and prose in the module docstring legitimately
    contain that substring).

## Verification

```
cd "/Users/utsab1/Documents/socrates automation" && source .venv/bin/activate && \
  python -m pytest tests/test_team_orchestrator.py -q
.......
7 passed in 0.24s
```

```
python -m team.orchestrator --help
usage: orchestrator.py [-h] [--dry-run]

options:
  -h, --help  show this help message and exit
  --dry-run   Run the full team chain and save outputs; do not post.
```
(no API call made — argparse only)

```
python -m pytest tests/test_team_models.py tests/test_team_debate.py \
  tests/test_team_orchestrator.py tests/test_team_planner.py tests/test_team_reviewer.py \
  tests/test_team_analytics_analyst.py tests/test_team_content_writer.py \
  tests/test_team_visual_designer.py tests/test_team_audio_engineer.py \
  tests/test_team_video_editor.py tests/test_team_engagement_strategist.py -q
........................................................................
72 passed in 0.24s
```

Full `tests/` suite: 231 passed, 2 pre-existing failures unrelated to this task
(`tests/test_reel_composer.py::test_generate_reel_success` and
`::test_generate_reel_silent_fallback` — both fail with an `ffmpeg`/`libx264` encoder error,
an environment issue in `src/video/reel_composer.py` predating this task; same 2 failures
noted in Task H's report). `team/output/` contains only `.gitkeep` after the full run — no
test wrote into the real output directory (all tests monkeypatch `_OUTPUT_DIR` to `tmp_path`).

**No real Claude API call was made at any point during this task.** Every test injects a
mock/fake `client`; the one test that exercises the `client=None` construction path
(`test_client_none_builds_real_client_from_config`) patches both `config.Config` and
`team.orchestrator.StudioClient` before calling `run_team_pipeline`, so no real HTTP request,
network access, or credential lookup occurs. `python -m team.orchestrator --dry-run` was
never invoked; only `--help` was run, which only exercises `argparse` and prints usage.

## Deviations from the brief

- The brief's step 13 return-dict spec says `"output_paths": {<the 7 keys above>: <Path
  written>}`, referring back to step 12's bullet list. Step 12's bullets are keyed by file
  **prefix**, and the copy-specs prefix is `copy` (filename `copy_{date}.json`), not
  `copy_specs`. I used `"copy"` as the `output_paths`/artifact-loop key (not `"copy_specs"`,
  which would have produced a mismatched filename `copy_specs_{date}.json`). This is called
  out explicitly since it's the one place the two most literal readings of the brief
  disagree; the returned `dict`'s top-level `copy_specs` key (step 13, first half) is
  unaffected — that's still named `copy_specs` and holds the `list[CopySpec]`, only the
  `output_paths` sub-dict and on-disk filename use `copy`.
- No other deviations. `pipeline.py` and `src/` were not modified; every prior `team/*.py`
  agent file was only imported, never edited.
