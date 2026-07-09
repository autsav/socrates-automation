# Task H report — team/video_editor.py + team/engagement_strategist.py

## What was built

- `team/video_editor.py` — mirrors `team/visual_designer.py`/`team/audio_engineer.py`:
  - Module-level `_PREFIX` template + `build_prompt(plan: ContentPlan, visual_specs:
    list[VisualSpec], audio_specs: list[AudioSpec]) -> str`, embedding
    `json.dumps(plan.to_dict(), indent=2)`, `json.dumps([v.to_dict() for v in
    visual_specs], indent=2)`, and `json.dumps([a.to_dict() for a in audio_specs],
    indent=2)` so each post's `format` (from the plan) sits alongside every `VisualSpec`
    (`flux_prompt`/`wallpaper_design` — what's on screen) and `AudioSpec`
    (`beat_markers`/`voiceover_text` — what the video must sync to). The prompt tells the
    model explicitly that only reel-format posts need real scene/transition/motion-effect
    detail and that carousel/single posts should get a minimal/trivial `VideoSpec` (empty
    `scenes`, `total_duration: 0.0`) — the "distinction lives in the prompt, not new code
    paths" rule from Task F/G, so `VideoEditorAgent.run` contains no `"reel"`/`"carousel"`/
    `"single"` string literals.
  - Module-level `parse_response(d: dict) -> list[VideoSpec]`, mapping `d["items"]`
    through `VideoSpec.from_dict`, preserving response order.
  - `VideoEditorAgent.__init__(self, client)` — loads `system_prompt =
    load_prompt("video_editor")`.
  - `VideoEditorAgent.run(self, plan, visual_specs, audio_specs) -> list[VideoSpec]` —
    builds the prompt, calls `self.client.call("video_editor", shared_prefix,
    self.system_prompt, "Edit the video plan for all 7 posts now.", VIDEO_SPECS_SCHEMA)`,
    returns `parse_response(data)`.

- `team/engagement_strategist.py` — same structure:
  - `build_prompt(plan, copy_specs)` embeds each post's `controversy_question`/
    `engagement_strategy`/`audience` (plan) alongside each `CopySpec`'s
    `controversy_question`/`caption` (the actual copy text seed comments must reference,
    not just the plan's abstract strategy field).
  - `parse_response(d) -> list[EngagementSpec]` via `EngagementSpec.from_dict`, order
    preserved.
  - `EngagementStrategistAgent.run(self, plan, copy_specs) -> list[EngagementSpec]` calls
    `self.client.call("engagement_strategist", shared_prefix, self.system_prompt, "Plan
    engagement tactics for all 7 posts now.", ENGAGEMENT_SPECS_SCHEMA)`.

- `tests/test_team_video_editor.py`, `tests/test_team_engagement_strategist.py` — same
  `_FakeClient` mocking convention as prior team agent tests. Each covers:
  - `build_prompt` embeds identifying content from all inputs (video editor: `format`,
    `flux_prompt`, `voiceover_text`; engagement strategist: plan's
    `controversy_question`/`engagement_strategy`, `CopySpec`'s `controversy_question`/
    `caption`).
  - `parse_response` returns 7 specs of the correct dataclass type, `post_number` order
    preserved 1..7.
  - `run()` builds the correct spec list from a mocked `{"items": [...]}` payload (count,
    field values, ordering).
  - `role == "video_editor"` / `role == "engagement_strategist"` passed to `client.call`.
  - The shared prefix passed to `client.call` contains identifying content from every
    input, confirming all inputs actually reach the model.
  - A mixed-format-post test (`reel`/`carousel`/`single`) confirms the prompt carries the
    `carousel` format string while `inspect.getsource` on each `run()` method confirms no
    `"reel"`/`"carousel"`/`"single"` literal branch was added in code — same check style as
    Task G's `test_run_handles_carousel_format_post_without_special_code_path`.

## Test results

```
cd "/Users/utsab1/Documents/socrates automation" && source .venv/bin/activate && \
  python -m pytest tests/test_team_video_editor.py tests/test_team_engagement_strategist.py -q
............
12 passed in 0.04s
```

Full `tests/` suite: 224 passed, 2 pre-existing failures unrelated to this task
(`tests/test_reel_composer.py::test_generate_reel_success` and
`::test_generate_reel_silent_fallback` — both fail with an `ffmpeg`/`libx264` encoder
error, `RuntimeError: ffmpeg video pass failed: ... Could not open encoder`, an
environment issue in `src/video/reel_composer.py` unrelated to `team/`). `pipeline.py` and
`src/` were not touched.

## Deviations from the brief

None. Dependencies (Task A `team/models.py` — `VideoSpec`/`EngagementSpec`/
`VIDEO_SPECS_SCHEMA`/`ENGAGEMENT_SPECS_SCHEMA`, `team/prompt_loader.load_prompt`; Task B
`team/prompts/video_editor.md`/`team/prompts/engagement_strategist.md`;
`studio/settings.py` role registration for both roles) were all already present in the
repo from prior tasks.
