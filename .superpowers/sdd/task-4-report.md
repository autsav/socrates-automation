# Task 4 Report — pipeline wiring: directed VO, multi-clip payload, silence drop, new SFX

## Summary

Implemented per `task-4-brief.md` (attention-magnet plan). Commit `ef7d855`:
`feat(pipeline): directed VO wiring, multi-clip payload, silence drop, riser+sub SFX (spec 1+2)`
(4 files: `pipeline.py`, `src/video/remotion_reel.py`, `tests/test_cinematic_wiring.py` (new),
`tests/test_remotion_reel.py`).

## TDD sequence

1. Wrote `tests/test_cinematic_wiring.py` verbatim from the brief. Ran →
   2 of 3 FAILED as expected (`TypeError: unexpected keyword argument
   'backgrounds'`; `sfx` missing `riser`/`sub_impact`).
2. Implemented `write_bridge_file`/`generate_remotion_reel`/`_synth_sfx` per
   brief Step 3 verbatim (`src/video/remotion_reel.py`), then the
   `pipeline.py` wiring described below.
3. `tests/test_cinematic_wiring.py` + `tests/test_remotion_reel.py` → 32
   passed. One pre-existing test (`test_synth_sfx_creates_files`) enumerated
   the exact `_synth_sfx` return dict; updated it to include
   `riser`/`sub_impact` (its fake `subprocess.run` succeeds unconditionally
   for every ffmpeg call, so the new SFX entries appear too — this is the
   "minimally update payload-shape tests" case the brief flagged).
4. Full suite: `.venv/bin/python -m pytest -q` → **720 passed**.

## `src/video/remotion_reel.py`

- `write_bridge_file` gains `backgrounds: list | None = None,
  silence_drop_sec: float = 0.0`. ≥2 existing clips → `payload["backgrounds"]`
  + `payload["backgroundDurationsSec"]`, legacy `background`/
  `backgroundDurationSec` popped. 0–1 clips → today's single-`background`
  payload, byte-identical (verified by `test_single_clip_payload_unchanged`).
  `silenceDropSec` written only when `> 0`.
- `_synth_sfx` now also produces `riser` (1.2s pink-noise swell, lowpass +
  fade-in/out) and `sub_impact` (0.5s 55Hz sine, fast decay), each best-effort
  and independent of the existing whoosh/impact pair.
- `generate_remotion_reel` forwards both new params straight through.

## `pipeline.py` wiring

**Footage (multi-clip):** new block right before the `generate_remotion_reel`
call — `fetch_reel_clips(mood, pexels_key, OUTPUT_DIR, topic_query=...)`;
≥2 clips → `bg_clips` (passed as `backgrounds=`, `background=None`); exactly 1
→ used as legacy `background=`; 0 clips or a fetch exception → existing
`_reel_background` fallback (stock photo → FLUX) runs unchanged. The fetch
has its own local try/except so a Pexels failure never escapes past this
block (it's also nested inside the outer best-effort try that already wraps
the whole render call, per the brief's "whole block try/except").

**Silence drop:** `silence_drop = 0.8 if quote_voice else 0.0`, passed to
`generate_remotion_reel`. `quote_voice` is only truthy once the VO block
above has produced a quote track, so this naturally gates on "quote VO
exists."

**Quote gravitas:** after the VO dict is unpacked, `apply_gravitas(quote_voice)`
runs best-effort (try/except, warning-only on failure) whenever `quote_voice`
is set — regardless of ElevenLabs vs. edge-tts origin, since `apply_gravitas`
is a pure ffmpeg post-process on the resulting file.

**Bridge directed VO + chapter breaks:** the ElevenLabs branch now tags a
*local copy* (`tagged_bridge = insert_chapter_breaks(bridge_text)`) for
narration only, and passes `settings=delivery_profile("bridge")` to
`generate_scene_voiceover` (`_el_scene`). `bridge_text` itself — used for the
on-screen payload (`bridge=` arg to `generate_remotion_reel`) and as the
edge-tts fallback input — stays untagged. The edge-tts fallback branch does
**not** get chapter-break tags: edge-tts has no SSML `<break>` support and
would narrate the literal tag text, so it only ever sees `bridge_text`.

**Word-timing skew for the bridge:** `generate_scene_voiceover`'s SRT is
estimated by splitting the (tagged) input text on whitespace
(`elevenlabs_engine._estimate_word_timings`), which turns each
`<break time="0.4s" />` into three bogus "words" (`<break`, `time="0.4s"`,
`/>`). Rather than modify the shared VO engine (out of this task's file
scope), added `pipeline.py::_strip_break_artifacts(words)` — a regex filter
(`^</?break\b|^time="|^/>$`) applied to the parsed `bridge_words` before
they're used for animation. This is the brief's accepted approach: word
boundaries immediately around a stripped break tag can shift by a few tens of
ms relative to true speech (a real 0.4s pause was inserted into the audio,
so the tag's neighbor words' estimated durations shift slightly) —
documented as an accepted skew, not exact resync.

## Hook/quote/cta VO settings — limitation

Hook/quote/cta VO is generated via one combined call
(`elevenlabs_engine.prepare_reel_voiceover` / `edge_tts_engine.
prepare_reel_voiceover_edge_tts`), not per-scene calls in `pipeline.py`.
Neither combined function accepts a per-scene `settings` override today, so
`delivery_profile("hook"/"quote"/"cta")` is **not** wired into those three
scenes — doing so would mean editing `src/audio/elevenlabs_engine.py`
(passing `settings=delivery_profile(...)` into its three internal
`generate_scene_voiceover` calls), which is outside this task's file scope
(`pipeline.py` + `src/video/remotion_reel.py` only). Only the bridge scene —
which `pipeline.py` calls directly via `_el_scene` — got the
`delivery_profile` wiring. **Follow-up:** a small future task should add a
`settings: dict | None = None`-style per-scene override to
`elevenlabs_engine.prepare_reel_voiceover` (and its edge-tts counterpart,
where it would be ignored since edge-tts prosody is rate/pitch-based, not
ElevenLabs `stability`/`style`) so hook/quote/cta can pick up
`delivery_profile` too.

## Character-budget check (chapter-break tags vs. 1500-char ElevenLabs cap)

Tag string: `<break time="0.4s" />` = **21 chars** (brief's ~28/tag estimate
was conservative/high). Worst case cited in task context: a 185-word
story-arc reframe ≈ 1050 chars (`insert_chapter_breaks` fires every 3
sentences; a 185-word beat plausibly has ~8 chapter breaks) →
`1050 + 8 × 21 = 1218 chars`, comfortably under the 1500-char truncation
guard in `elevenlabs_engine.generate_voiceover`. No code change needed;
confirmed via arithmetic, not a live API call.

## Concerns / follow-ups

- Hook/quote/cta directed-VO settings limitation above — needs a small
  follow-up task to extend `elevenlabs_engine.prepare_reel_voiceover`.
- `bg_clips` download cost: `fetch_reel_clips` downloads up to `n=4` (default)
  full clips per reel when a Pexels key is present — larger network/IO cost
  per render than the previous single-clip fetch. Not addressed here (out of
  scope; brief only specifies wiring, not throttling `n`).
- `data/pipeline.db` was touched by the full-suite run (side effect of tests
  exercising `save_post`/etc.); restored via `git checkout --
  data/pipeline.db` before committing — not included in the commit.
- Other pre-existing working-tree changes unrelated to this task (task
  1/2/3/5/6/7/8/9 report/brief files, `logs/notifications.jsonl`,
  `output/product/landing.html`, `quotes.xlsx`, `.hermes/`,
  `remotion/public/bg.mp4`, `remotion/public/reel-data.json`) were present
  before this task started and were left untouched — not staged or
  committed.

## Note on this file

This report path previously held content for a different "Task 4" (embedding
expert playbooks into copywriter/trend_scout/music_director/strategist, from
an earlier spec run — commit `eaff110`). Overwritten per this task's explicit
instruction to write the report to this path; that prior work is unaffected
and remains on `main`.

## Status

DONE

---

## Fix: per-scene delivery profiles reach hook/quote/cta VO (review finding)

**Finding**: `delivery_profile("hook"/"quote"/"cta")` from `voice_director.py`
was only ever applied to the Bridge scene VO (direct `generate_scene_voiceover`
call in `pipeline.py`). The combined `elevenlabs_engine.prepare_reel_voiceover`
call that `_run_pov_reel` uses for hook/quote/cta had no per-scene settings
parameter, so those three scenes always got flat `DEFAULT_SETTINGS` — no
attack on the hook, no slow gravitas on the quote.

**Fix**:
1. `src/audio/elevenlabs_engine.py::prepare_reel_voiceover` — added optional
   `scene_settings: dict[str, dict] | None = None` param. Each of
   `scene_settings.get("hook"/"quote"/"cta")` is passed straight through to
   the existing `generate_scene_voiceover(..., settings=...)` call for that
   scene, which already merges over `DEFAULT_SETTINGS` inside
   `generate_voiceover` (same merge pattern as before — no new merge logic).
   `scene_settings=None` (default) reproduces prior behavior exactly (verified
   by test).
2. `pipeline.py::_run_pov_reel` — the ElevenLabs branch of the hook/quote/cta
   VO call now passes
   `scene_settings={"hook": delivery_profile("hook"), "quote":
   delivery_profile("quote"), "cta": delivery_profile("cta")}`. Reuses the
   `delivery_profile` import already in place for the bridge scene. Call site
   is unchanged inside its existing try/except — a `delivery_profile` failure
   still can't crash the reel (worst case: exception caught, whole VO stage
   skipped, same as any other VO failure today).
3. edge-tts fallback (`edge_tts_engine.prepare_reel_voiceover_edge_tts`) left
   **unchanged** — it already has its own per-scene direction system
   (`SCENE_PROSODY`), so it wasn't the affected combined path; no fix needed
   there.

**Tests added** (`tests/test_cinematic_wiring.py`):
- `test_reel_voiceover_applies_per_scene_delivery_profiles` — monkeypatches
  `elevenlabs_engine.generate_voiceover` to capture the merged voice_settings
  used per call, drives `prepare_reel_voiceover` with the real
  `delivery_profile()` outputs, asserts hook stability (0.22) != quote
  stability (0.70) in the settings actually used for those scenes.
- `test_reel_voiceover_scene_settings_default_none_is_unchanged` — same
  harness with `scene_settings` omitted; asserts all three calls receive
  `settings=None` (i.e. exactly current/prior behavior).

**Test runs**:
- `.venv/bin/python -m pytest tests/test_cinematic_wiring.py
  tests/test_remotion_reel.py -q` → `34 passed`
- `.venv/bin/python -m pytest -k elevenlabs -q` → `722 deselected` (no tests
  matched the "elevenlabs" keyword filter by name; new tests live in
  test_cinematic_wiring.py and were already covered by the run above)
- `.venv/bin/python -m pytest -q` (full suite) → `722 passed`

`data/pipeline.db` was touched by test runs (dry-run DB writes); restored via
`git checkout -- data/pipeline.db` before committing, not included in the
commit.

### Status

DONE
