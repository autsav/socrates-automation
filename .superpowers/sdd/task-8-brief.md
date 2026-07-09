# Task H — team/video_editor.py + team/engagement_strategist.py

Working directory: `/Users/utsab1/Documents/socrates automation`, venv `.venv/`, Python 3.11.
Depends on Task A (`team/models.py`: `ContentPlan`, `CopySpec`, `VisualSpec`, `AudioSpec`,
`VideoSpec`, `VIDEO_SPECS_SCHEMA`, `EngagementSpec`, `ENGAGEMENT_SPECS_SCHEMA`,
`team/prompt_loader.load_prompt`), Task B (`team/prompts/video_editor.md`,
`team/prompts/engagement_strategist.md`), Task F/G (you consume their output types
`list[CopySpec]`/`list[VisualSpec]`/`list[AudioSpec]`, not their code). `studio/settings.py`
already registers roles `"video_editor"` and `"engagement_strategist"` (both
`claude-sonnet-4-6`, effort `"medium"`).

Mirror `team/visual_designer.py`/`team/audio_engineer.py`'s exact structure for both new files.

## `team/video_editor.py`

```python
class VideoEditorAgent:
    def __init__(self, client):
        self.client = client
        self.system_prompt = load_prompt("video_editor")

    def run(self, plan: ContentPlan, visual_specs: list[VisualSpec],
            audio_specs: list[AudioSpec]) -> list[VideoSpec]:
        ...
```

- Only reel-format posts need real scene/transition/motion-effect detail — carousel and single
  posts don't have video. The prompt should tell the model this explicitly (pass each post's
  `format` from the plan) rather than the code branching on format; for non-reel posts the model
  can return a minimal/trivial `VideoSpec` (e.g. empty `scenes`, `total_duration: 0.0`) — same
  "distinction lives in the prompt, not new code paths" rule as Task F/G.
- Prompt embeds `plan.to_dict()`, `[v.to_dict() for v in visual_specs]` (for `flux_prompt`/
  `wallpaper_design` context — what's actually on screen), and
  `[a.to_dict() for a in audio_specs]` (for `beat_markers`/`voiceover_text` — what the video must
  sync to), joined by `post_number`.
- Call `self.client.call("video_editor", shared_prefix, self.system_prompt, "Edit the video plan
  for all 7 posts now.", VIDEO_SPECS_SCHEMA)`; unwrap `{"items": [...]}` into `list[VideoSpec]`
  via `VideoSpec.from_dict`, preserving order.

## `team/engagement_strategist.py`

```python
class EngagementStrategistAgent:
    def __init__(self, client):
        self.client = client
        self.system_prompt = load_prompt("engagement_strategist")

    def run(self, plan: ContentPlan, copy_specs: list[CopySpec]) -> list[EngagementSpec]:
        ...
```

- Prompt embeds `plan.to_dict()` (for `controversy_question`, `engagement_strategy`, `audience`
  per post) and `[c.to_dict() for c in copy_specs]` (the actual `controversy_question`/`caption`
  text written by the content writer — seed comments must reference the real copy, not the
  plan's abstract strategy field alone), joined by `post_number`.
- Call `self.client.call("engagement_strategist", shared_prefix, self.system_prompt, "Plan
  engagement tactics for all 7 posts now.", ENGAGEMENT_SPECS_SCHEMA)`; unwrap into
  `list[EngagementSpec]` via `EngagementSpec.from_dict`, preserving order.

## Tests

`tests/test_team_video_editor.py`, `tests/test_team_engagement_strategist.py` — same mocking
convention as prior team agent tests. For each, cover:
- `run()` builds correct spec list from a mocked `{"items": [...]}` response.
- Role passed to `client.call` is exactly `"video_editor"` / `"engagement_strategist"`.
- Video editor: prompt contains content from all three inputs (`plan`, `visual_specs`,
  `audio_specs`) — e.g. a post's `format`, a `flux_prompt` snippet, and a `beat_markers`/
  `voiceover_text` value.
- Engagement strategist: prompt contains content from both inputs (`plan`'s
  `controversy_question`/`engagement_strategy` and a `CopySpec`'s `controversy_question`/
  `caption`).
- Confirm neither `run()` method adds format-specific (`reel`/`carousel`/`single`) code branches
  — same check style as Task G's tests (e.g. via `inspect.getsource`).

## Verification

`cd "/Users/utsab1/Documents/socrates automation" && source .venv/bin/activate && python -m pytest tests/test_team_video_editor.py tests/test_team_engagement_strategist.py -q` — all pass.

## Report

Write `.superpowers/sdd/task-8-report.md` (signatures, test results, deviations). Commit
(do not push): `feat: video editor and engagement strategist team agents`. Return DONE /
DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED, one-line summary, commit hash.
