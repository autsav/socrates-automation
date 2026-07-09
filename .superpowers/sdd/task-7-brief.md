# Task G — team/visual_designer.py + team/audio_engineer.py

Working directory: `/Users/utsab1/Documents/socrates automation`, venv `.venv/`, Python 3.11.
Depends on Task A (`team/models.py`: `ContentPlan`, `CopySpec`, `VisualSpec`,
`VISUAL_SPECS_SCHEMA`, `AudioSpec`, `AUDIO_SPECS_SCHEMA`, `team/prompt_loader.load_prompt`),
Task B (`team/prompts/visual_designer.md`, `team/prompts/audio_engineer.md`), and Task F
(`team/content_writer.py`, for reference only — you consume its output type, `list[CopySpec]`,
not its code). `studio/settings.py` already registers roles `"visual_designer"` and
`"audio_engineer"` (both `claude-sonnet-4-6`, effort `"medium"`).

Mirror `team/content_writer.py`'s exact structure for both new files: module-level
`build_prompt(...)`/`parse_response(...)` helpers plus a thin class. Both agents take the same
two inputs (`plan`, `copy_specs`) so their prompts should combine `plan.to_dict()` +
`[c.to_dict() for c in copy_specs]` the same way.

## `team/visual_designer.py`

```python
class VisualDesignerAgent:
    def __init__(self, client):
        self.client = client
        self.system_prompt = load_prompt("visual_designer")

    def run(self, plan: ContentPlan, copy_specs: list[CopySpec]) -> list[VisualSpec]:
        ...
```

- Prompt embeds each post's `mood`, `visual_style`, `format` (from the plan) alongside that
  post's `hook` text (from the matching `CopySpec`, joined by `post_number`) — the visual
  designer needs to know what text will be overlaid to design composition/typography around it.
- Call `self.client.call("visual_designer", shared_prefix, self.system_prompt, "Design the
  visuals for all 7 posts now.", VISUAL_SPECS_SCHEMA)`; unwrap `{"items": [...]}` into
  `list[VisualSpec]` via `VisualSpec.from_dict`, preserving model order (same convention as
  `team/content_writer.py`).

## `team/audio_engineer.py`

```python
class AudioEngineerAgent:
    def __init__(self, client):
        self.client = client
        self.system_prompt = load_prompt("audio_engineer")

    def run(self, plan: ContentPlan, copy_specs: list[CopySpec]) -> list[AudioSpec]:
        ...
```

- Prompt embeds each post's `mood`, `audio_strategy`, `format` (from the plan) alongside that
  post's `hook`/`caption` (from the matching `CopySpec`) — the audio engineer needs the actual
  words to write a matching voiceover script and know how long the spoken content runs.
- Call `self.client.call("audio_engineer", shared_prefix, self.system_prompt, "Design the audio
  for all 7 posts now.", AUDIO_SPECS_SCHEMA)`; unwrap into `list[AudioSpec]` via
  `AudioSpec.from_dict`, same convention.

## Tests

`tests/test_team_visual_designer.py`, `tests/test_team_audio_engineer.py` — same mocking
convention as `tests/test_team_content_writer.py`. For each agent, cover:
- `run()` builds correct spec list from a mocked `{"items": [...]}` response.
- Role passed to `client.call` is exactly `"visual_designer"` / `"audio_engineer"`.
- The prompt/context passed to `client.call` contains identifying content from both `plan` (e.g.
  a post's `mood` or `visual_style`/`audio_strategy`) and `copy_specs` (e.g. a post's `hook`
  text) — confirms both inputs actually reach the model, not exhaustive matching.

## Verification

`cd "/Users/utsab1/Documents/socrates automation" && source .venv/bin/activate && python -m pytest tests/test_team_visual_designer.py tests/test_team_audio_engineer.py -q` — all pass.

## Report

Write `.superpowers/sdd/task-7-report.md` (signatures, test results, deviations). Commit
(do not push): `feat: visual designer and audio engineer team agents`. Return DONE /
DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED, one-line summary, commit hash.
