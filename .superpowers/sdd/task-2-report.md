# Task B report — expert system prompts for team agents

## Files created

All 8 required files under `team/prompts/` (new directory):

| File | Lines |
|---|---|
| `team/prompts/analytics_analyst.md` | 56 |
| `team/prompts/planner.md` | 67 |
| `team/prompts/reviewer.md` | 59 |
| `team/prompts/content_writer.md` | 59 |
| `team/prompts/visual_designer.md` | 72 |
| `team/prompts/audio_engineer.md` | 64 |
| `team/prompts/video_editor.md` | 60 |
| `team/prompts/engagement_strategist.md` | 60 |

All 8 within the requested 40-80 line range.

## Ground-truth check

Read `src/core/excel_reader.py`'s `AUDIENCE_TO_MOOD` before writing (per brief instruction) — the
authoritative segment→mood set is: `procrastinator`→`dark_philosophical`,
`doomscroller`→`dramatic_ancient`, `stuck`→`cinematic_hopeful`, `lazy`→`stark_minimal`,
`quitter`→`epic_warrior`, `lost`→`mystical_greek`, `overwhelmed`→`calm_stoic`. This differs from
the segment names listed in the brief's own context section (`overthinker`, `burnt_out`,
`heartbroken`, `ambitious` do not exist in code). Per the brief's explicit instruction to match the
code's exact names, all 8 prompts use only the 7 real segment names above — none of the brief's
placeholder names were used.

Also cross-referenced `team/models.py` (the actual `PostPlan`/`CopySpec`/`VisualSpec`/`AudioSpec`/
`VideoSpec`/`EngagementSpec`/`AnalyticsReport` dataclasses + JSON schemas used by this pipeline) so
every "Output" section names the exact schema fields the calling code expects, and
`src/visual/brand_design.py`'s `MOOD_PALETTES` (real hex/RGB values per mood) and
`src/audio/voiceover_engine.py`'s prosody configs (real mood→emotion/pace mappings) so the visual
designer and audio engineer prompts cite this codebase's actual palette/prosody data rather than
invented values. Confirmed `src/visual/motion_effects.py` exposes exactly 15 named xfade
transition types and listed all 15 by name in `video_editor.md`.

## Deviation

The brief asked the video editor prompt to reference "target duration (15-22s per item in the
existing dataclass spec)." I could not find a 15-22s constant anywhere in the codebase — the
legacy `src/video/reel_composer.py` hardcodes a 3-scene, ~14-15s Reel (`SCENE_DURATIONS = [4, 8,
3]`), and `team/models.py`'s `VideoSpec.total_duration` is an unconstrained float with no bounds
in code. I used the brief's explicit 15-22s figure verbatim (the brief is the authoritative task
spec) but flag that this number doesn't correspond to a literal dataclass constant I could locate;
it reads as a deliberate widening of the legacy single-format 15s Reel for this new multi-format
pipeline's videos, consistent with the shorter-is-better completion-rate framing already in the
codebase's docstring.

## Self-review against style requirements

- Second person throughout: every file opens "You are a ..." and uses imperative instructions,
  no third-person agent descriptions.
- Every file ends with a `## Output` section naming its exact schema and reiterating
  structured-JSON-only, no prose.
- No code written; markdown prose only.
- Filler check: grepped all 8 files for "leverage synerg", "circle back", "synergy", "move the
  needle", "low-hanging fruit", "game-chang" — zero hits.
- Concrete numbers/thresholds/named techniques: every file contains well over 3 (posting-time
  windows, hold-rate percentages, mood/emotion mappings, hex color values, transition-type names,
  duration targets, score thresholds, etc.) — verified by grepping numeric tokens per file.

## Follow-up fix — mood/duration guidance corrections (post-review)

Task review flagged two inaccuracies in `team/prompts/` files vs. actual code behavior. Both fixed
directly, no tests added (prose-only files).

### 1. `team/prompts/audio_engineer.md` — voiceover emotion per mood

Original text asserted `dramatic_ancient`, `stark_minimal`, and `mystical_greek` all default to a
"balanced" style with whispered reserved for confessional posts only. Re-read
`src/audio/voiceover_engine.py`'s `_scene_configs` `mood_configs` dict (the mapping used when style
isn't explicitly `intense`/`calm`/`whispered`) and found:

- `mystical_greek` has an explicit entry with `hook`/`cta` emotion = `whispered` (medium pace) —
  whispered is this mood's own default, not a confessional-only override.
- `dramatic_ancient` and `stark_minimal` have **no entry** in `mood_configs` at all; the code's
  `.get(mood, mood_configs["dark_philosophical"])` fallback means both silently inherit the
  `dark_philosophical` arc (urgent/medium hook+cta, intense/slow quote) by default.

Rewrote the section to state each of these three moods' true default explicitly, kept the
intense/calm/whispered override styles as optional overrides, and narrowed the
"reserve-whispered-for-confessional" guidance to apply outside `mystical_greek`'s own default.

### 2. `team/prompts/video_editor.md` — duration and structure

Original text presented 15-22s as a target range to fill. Re-read `src/video/reel_composer.py`:
its module docstring and inline comments state the research finding directly — "7-15s Reels get
5-10x more reach than longer ones" — and `SCENE_DURATIONS = [4, 8, 3]` / `TOTAL_DURATION` (14s) was
deliberately shortened from a prior 21s total for that reason.

Kept 15-22s as the plan's stated outer ceiling (per instruction — this number traces to the source
plan doc's dataclass comment and should not be silently dropped), but added a sentence citing
`reel_composer.py`'s finding and its 21s→14s shortening, and instructed the video editor to default
toward the lower end (nearer 14-15s) rather than treating the full range as a target, reserving the
higher end for content that genuinely needs the extra runtime.

### Re-verification

Re-read both source files after writing the new prose and confirmed: `mood_configs` dict in
`voiceover_engine.py` has exactly 5 explicit entries (`dark_philosophical`, `cinematic_hopeful`,
`epic_warrior`, `calm_stoic`, `mystical_greek`) — `dramatic_ancient`/`stark_minimal` are absent and
fall back to `dark_philosophical` as stated; `reel_composer.py`'s `TOTAL_DURATION` comment and
docstring confirm the 14s current total / 21s prior total / 7-15s research figure as written.
