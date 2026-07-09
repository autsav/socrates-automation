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
