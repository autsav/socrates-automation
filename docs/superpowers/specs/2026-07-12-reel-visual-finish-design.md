# Reel Visual Finish — Design

**Date:** 2026-07-12
**Status:** Approved (design)
**Sub-project 3B of 3** (final piece). Builds on 3A (narrated Remotion reel, merged `7161899`).

## 1. Goal

Cinematic finish on the narrated Remotion reel: make the VO actually run in CI,
karaoke-highlight the on-screen text in sync with speech, add a per-mood color
grade, a beat-timed camera zoom, and subtle SFX.

## 2. Decisions (locked)

| # | Decision |
|---|---|
| Captions | **Karaoke on the existing text** — highlight each word as the VO speaks it; no separate caption layer. |
| SFX | **Synthesized via ffmpeg** at bridge time (no asset licensing); swappable later. |
| Word timings | From edge-tts `--write-subtitles` (per-word SRT). |

## 3. Non-goals (YAGNI)

- No separate bottom-caption band.
- No change to VO/music/ducking/loudnorm from 3A (only additive).
- No bundled SFX/audio assets.

## 4. Architecture (ordered low-risk → high-risk)

### 4.0 edge-tts is installed in CI — `requirements.txt`
Add `edge-tts` to `requirements.txt`. CI runs `pip install -r requirements.txt`,
so this is what makes `edge_tts_available()` true in production — currently the
"narrated" reel is **music-only** because edge-tts isn't installed. Prerequisite
for both VO and word timings.

### 4.1 Per-mood color grade — `remotion/src/components/ColorGrade.tsx` + `theme.ts`
- Add a `grade` field per mood in `theme.ts` (e.g. `{ filter: string; vignette: number }`
  — a CSS `filter` string like `contrast(1.08) saturate(1.12) brightness(1.02)`
  plus a vignette strength 0–1), with a sensible default.
- `ColorGrade` = an `AbsoluteFill` wrapper applying `filter` to its children +
  an overlay `AbsoluteFill` with a radial vignette gradient and a very subtle
  grain. Wrap the **visual** layers in `PovReel` (backgrounds + text); audio
  stays outside it.

### 4.2 Beat-timed track + zoom — `remotion/src/lib/cameraZoom.ts` + `PovReel`
- Pure `cameraScale(frame, fps, durationInFrames, beats) -> number`: a slow base
  push `interpolate(frame, [0, total], [1.0, 1.06])` plus a decaying kick
  (`+~0.02`) on each beat frame within a short window. Apply as a `transform:
  scale(...)` on the visual-layer group (inside `ColorGrade`).

### 4.3 SFX — `remotion_reel.py` (synth + bridge) + `PovReel`
- At bridge time, synthesize two short mono SFX with ffmpeg into the bridge dir
  (best-effort, guarded by `shutil.which("ffmpeg")`):
  - `sfx-whoosh.wav` — filtered noise sweep (`anoisesrc` + bandpass + fade), ~0.4s.
  - `sfx-impact.wav` — short low sine thump (`sine` + fast decay), ~0.2s.
  - Bridge gains `sfx: {whoosh, impact}` (basenames or null when ffmpeg absent).
- Remotion plays `whoosh` at each scene boundary (`hookF`, `quoteEnd`) and a
  throttled `impact` on strong beats, at a low volume (~0.3). Guarded on presence.

### 4.4 Word timings — `edge_tts_engine.py` + `remotion_reel.py`
- `generate_scene_voiceover_edge_tts(text, voice, output_path)` also passes
  `--write-subtitles <output_path.srt>`; a parser `parse_word_srt(path) ->
  [{"w": str, "start": float, "end": float}]` reads the per-word cues.
- `prepare_reel_voiceover_edge_tts` returns per-scene word lists alongside the
  voice paths (e.g. `hook_words`/`quote_words`/`cta_words`).
- `pipeline.py` (`--remotion` branch) captures those word lists and passes them
  into `generate_remotion_reel(...)`, which gains `hook_words`/`quote_words`/
  `cta_words` params and forwards them to `write_bridge_file`.
- Bridge gains `wordTimes: {hook:[…], quote:[…], cta:[…]}` (seconds; empty lists
  when unavailable). Best-effort; never blocks.

### 4.5 Karaoke highlight — `remotion/src/lib/wordAt.ts` + text components
- Pure `wordAt(frameInScene, words, fps) -> number` → index of the currently-
  spoken word (or the last revealed), else `-1`.
- `AnimatedQuote` (quote), `HookScene`, `CtaScene`: when the scene's `wordTimes`
  is present, drive the per-word **highlight** (word → `palette.accent` + a small
  scale pop) and reveal from `wordAt` instead of the fixed stagger. When absent,
  keep the current behavior unchanged (full graceful fallback).

## 5. Data flow
```
requirements: edge-tts installed ─► edge_tts_available() true in CI
edge-tts --write-media + --write-subtitles ─► mp3 + per-word SRT
   parse_word_srt ─► [{w,start,end}] per scene
remotion_reel.write_bridge_file ─► reel-data.json {
     …3A keys…, wordTimes:{hook,quote,cta}, sfx:{whoosh,impact} }
   + ffmpeg-synth SFX copied to public/
PovReel: ColorGrade( cameraScale( scenes[ karaoke via wordAt ] ) )
         + SFX <Audio> at boundaries/beats
```

## 6. Error handling
- No edge-tts → no VO/wordTimes (music-only reel, as today); never breaks.
- SRT parse failure / missing subtitles → `wordTimes` empty → text uses the
  fixed-stagger fallback.
- ffmpeg missing → no SFX (`sfx` null); grade/zoom are pure-CSS (always work).
- `generate_remotion_reel` still returns `None`/never raises → ffmpeg-POV fallback.

## 7. Testing
Python (3.11 `.venv`): `parse_word_srt` on a sample SRT; bridge includes
`wordTimes` + `sfx` and copies synth SFX (mock ffmpeg); degrades when tools absent.
Remotion (vitest): `wordAt` (before first word → -1, mid-word → that index,
after → last); `cameraScale` (base push monotonic, beat kick bumps then decays);
per-mood `grade` present. Smoke: render a reel; grade filter + a highlighted word
visible. Full suite green apart from the 2 pre-existing ffmpeg failures.

## 8. Files touched
| File | Change |
|---|---|
| `requirements.txt` | add `edge-tts` |
| `remotion/src/styles/theme.ts` | per-mood `grade` params |
| `remotion/src/components/ColorGrade.tsx` (NEW) | filter + vignette + grain wrapper |
| `remotion/src/lib/cameraZoom.ts` (+test) | `cameraScale` push + beat kick |
| `remotion/src/lib/wordAt.ts` (+test) | active-word index |
| `remotion/src/PovReel.tsx` | wrap in ColorGrade + cameraScale; SFX `<Audio>`; pass wordTimes to scenes |
| `remotion/src/components/{AnimatedQuote,HookScene,CtaScene}.tsx` | word-timed highlight (fallback to stagger) |
| `src/audio/edge_tts_engine.py` | `--write-subtitles`; `parse_word_srt`; return word lists |
| `src/video/remotion_reel.py` | `generate_remotion_reel` word-list params; bridge `wordTimes` + `sfx`; ffmpeg SFX synth |
| `pipeline.py` | `--remotion` branch: capture word lists → pass to `generate_remotion_reel` |
| `tests/…` | parser, bridge, vitest helpers |
