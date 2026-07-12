# Reel narration voice — deep, slow, "wise grandfather" sage

Date: 2026-07-12
Status: Approved

## Goal

Replace the reel voiceover with a warm, authoritative "grandfather / teacher we
look up to" delivery — deep bass, slow, calm, subtle (Morgan-Freeman-adjacent).
Chosen by ear from generated samples (`output/voice_samples/`): variant
**A2_Andrew_MAX**.

## Decision

| Setting | Value |
|---------|-------|
| Voice   | `en-US-AndrewNeural` (Warm, Confident, Authentic, Honest) |
| Rate    | `-30%` (slow, deliberate) |
| Pitch   | `-14Hz` (deep bass) |

Applies to **all** reel narration (one consistent sage voice), not per-mood.

## Changes — `src/audio/edge_tts_engine.py`

1. Add constants:
   ```python
   REEL_VOICE = "en-US-AndrewNeural"
   REEL_RATE  = "-30%"
   REEL_PITCH = "-14Hz"
   ```
2. Thread `rate`/`pitch` through the synth path so they reach the edge-tts
   `Communicate(...)` call (currently uses the library defaults `+0%`/`+0Hz`):
   `_edge_tts_synth(text, voice, media_path, rate, pitch)` →
   `generate_scene_voiceover_edge_tts(text, voice, output_path, rate, pitch)`.
   Both new params default to `"+0%"` / `"+0Hz"` so existing callers are
   unaffected.
3. `prepare_reel_voiceover_edge_tts` uses `REEL_VOICE` + `REEL_RATE` +
   `REEL_PITCH` for the three scene clips instead of `get_voice_for_mood(mood)`.
   `VOICE_MAP` / `get_voice_for_mood` remain for backward compatibility.

## Explicitly out of scope (YAGNI)

- **Ellipsis pause-injection.** The sample's deliberate pauses came from ellipses
  between phrases. The reel already speaks hook / quote / CTA as three separate
  clips with gaps between scenes, and `-30%` rate slows the cadence, so the
  effect is largely reproduced. Injecting ellipses would also corrupt per-word
  `wordTimes` (an ellipsis is not a spoken word). Skipped unless requested.
- Per-mood voice variety for reels — intentionally collapsed to one sage voice.

## Effects / risks

- `-30%` lengthens each VO clip → reel runs slightly longer. Handled by the
  existing duration clamp (7–15s) and `voiceDurations` in the Remotion bridge.
- `-14Hz` is an aggressive pitch shift; accepted after listening to A2.

## Tests

- Update `tests/test_edge_tts_engine.py::test_prepare_reel_voiceover_edge_tts_*`
  voice assertion `en-US-ChristopherNeural → en-US-AndrewNeural`.
- Add a test that `rate`/`pitch` propagate to the `_edge_tts_synth` seam.
