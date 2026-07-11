# Narrated Remotion Reel + Production Cutover — Design

**Date:** 2026-07-11
**Status:** Approved (design)
**Sub-project 3A of 3** in the quality program (1: reliability ✅, 2: image+typography ✅; 3B: visual finish = grade/zoom/captions/SFX).

## 1. Goal

Make the Remotion reel the production reel and give it full spoken narration
over a properly ducked music bed, loudness-normalized. This ships a real
upgrade on its own; 3B layers visual finish on top.

## 2. Decisions (locked)

| # | Decision |
|---|---|
| Engine | Remotion becomes the production reel (CI cutover). |
| VO | Full narration: hook + quote + cta via edge-tts (free). |
| Audio | Music bed ducks under VO; final ffmpeg `loudnorm` finishing pass. |
| Fallback | `--remotion` implies `--pov`; if Node/Remotion/render fails → ffmpeg POV reel (unchanged graceful path). |

## 3. Non-goals (YAGNI / deferred to 3B)

- Color grade, beat-timed track+zoom, word-synced captions, SFX.
- No change to the AnimatedQuote text visuals (they stay as-is; beats from
  `quote_voice` still drive the keyword punch).

## 4. Architecture

### 4.1 Production cutover — `.github/workflows/daily_post.yml` + `pipeline.py`
- Workflow POV slot: `python pipeline.py --manual --pov` → `--manual --remotion`.
- Add `actions/setup-node` + `npm --prefix remotion ci` to the job (so `npx
  remotion render` can run; Remotion fetches its own headless shell).
- `pipeline.py`: `--remotion` already implies `--pov` and falls back to
  `generate_pov_reel` when `generate_remotion_reel` returns `None`. **Risk to
  validate on the first CI run:** headless render on the ubuntu runner. The
  fallback guarantees a failed render degrades to the ffmpeg POV reel, never
  breaks the post.

### 4.2 Voiceover for all three scenes — `pipeline.py` + `remotion_reel.py`
- In the `--remotion` branch, generate all three VO tracks via
  `prepare_reel_voiceover_edge_tts(...)` (already returns
  `{hook_voice, quote_voice, cta_voice}` as `Path|None`).
- `generate_remotion_reel(...)` gains params `hook_voice`, `quote_voice`,
  `cta_voice`, `music_path` (all `Path | None`).
- `write_bridge_file` extends `reel-data.json`:
  - copy each present VO mp3 into `remotion/public/` as `vo-hook<ext>` /
    `vo-quote<ext>` / `vo-cta<ext>`; add `voices: {hook, quote, cta}` (basenames
    or null).
  - copy the music track (if resolved) as `music<ext>`; add `music` (basename or null).
  - add `voiceDurations: {hook, quote, cta}` in seconds — probed with `ffprobe`
    (best-effort; null when unavailable) so Remotion can duck precisely.
  - keep `beats` (still detected from `quote_voice`) for the AnimatedQuote punch.
  - The old single `audio` key is replaced by `voices`; the quote-scene audio is
    now `voices.quote`.

### 4.3 Music resolution
- Resolve a per-mood music bed best-effort via the existing helpers
  (`src/audio/trending_audio.download_music_for_mood(mood)` or the pov
  `_resolve_audio` chain). `None` → VO-only reel (no music), never blocks.

### 4.4 Remotion audio — `remotion/src/PovReel.tsx` (+ props in `Root.tsx`)
- New props: `voices?: {hook?, quote?, cta?}`, `music?: string`,
  `voiceDurations?: {hook?, quote?, cta?}`.
- Play each VO under its scene: `<Sequence from=0><Audio src=staticFile(voices.hook)></Sequence>`,
  `<Sequence from=hookF><Audio src=staticFile(voices.quote)></Sequence>`,
  `<Sequence from=quoteEnd><Audio src=staticFile(voices.cta)></Sequence>`.
  Each `<Audio>` rendered only when its filename is present.
- **Music bed + ducking:** one full-composition `<Audio src=staticFile(music)>`
  with a **volume function** `duckVolume(frame)`:
  - Ducked spans = per scene `[sceneStartFrame, sceneStartFrame + round(voDur*fps)]`
    using `voiceDurations`; when a scene's VO duration is missing, duck its whole
    scene span (safe default).
  - `duckVolume` returns a low gain (~0.12) inside any ducked span, a base gain
    (~0.32) outside, with a short linear ramp (a few frames) at each edge to
    avoid clicks. Pure function of frame — unit-testable.

### 4.5 Loudness normalize — `remotion_reel.py`
- After a successful `npx remotion render`, run one ffmpeg finishing pass:
  `ffmpeg -y -i <rendered> -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:v copy <final>`
  and replace the output. Guarded by `ffmpeg_available()`; on any ffmpeg error,
  keep the un-normalized render (never fail the reel).

## 5. Data flow
```
pipeline --remotion ─► prepare_reel_voiceover_edge_tts ─► {hook,quote,cta}.mp3
                    ─► resolve music (best-effort) ─► music track
generate_remotion_reel(hook_voice, quote_voice, cta_voice, music_path)
   write_bridge_file ─► copy VO+music → remotion/public/;
       reel-data.json { …, voices:{…}, music, voiceDurations:{…}, beats:[…] }
   npx remotion render ─► reel.mp4 (VO per scene + ducked music baked in)
   ffmpeg loudnorm ─► final reel.mp4
PovReel: per-scene <Audio> VO + music <Audio volume={duckVolume}>
```

## 6. Error handling
- No Node/Remotion/deps, or render failure → `generate_remotion_reel` returns
  `None` → ffmpeg POV fallback (unchanged).
- Any VO track missing → that scene simply has no VO (others still play).
- Music unresolved → VO-only, no music `<Audio>`.
- `ffprobe`/`ffmpeg` missing → duck whole-scene spans / skip loudnorm; reel still renders.
- All copies best-effort; `write_bridge_file` never raises.

## 7. Testing
Run under 3.11 `.venv` (`.venv/bin/python -m pytest`).
- **Bridge (Python):** with three VO paths + music, payload has
  `voices:{hook,quote,cta}` (basenames), `music`, and each file copied into the
  bridge dir; with all `None`, `voices` values are null and `music` null; probe
  failure → `voiceDurations` null but bridge still written. Mock
  `prepare_reel_voiceover_edge_tts`/`ffprobe`.
- **loudnorm:** the finishing pass is invoked with the loudnorm filter when
  ffmpeg is available and skipped (render kept) when not — mock `subprocess`.
- **Remotion (vitest):** `duckVolume(frame)` is low inside a VO span, base
  outside, and ramps monotonically at edges; missing VO duration → whole-scene
  duck.
- **Smoke:** render a short reel with VO+music; assert the output has an audio
  stream (`ffprobe`), roughly at the loudnorm target.
- Full suite green apart from the 2 pre-existing `test_reel_composer.py` ffmpeg failures.

## 8. Files touched
| File | Change |
|---|---|
| `.github/workflows/daily_post.yml` | setup-node + `npm --prefix remotion ci`; POV slot `--pov` → `--remotion` |
| `pipeline.py` | `--remotion` branch: generate 3 VO + resolve music → pass to `generate_remotion_reel` |
| `src/video/remotion_reel.py` | `generate_remotion_reel` VO/music params; `write_bridge_file` `voices`/`music`/`voiceDurations`; ffprobe durations; loudnorm finishing pass |
| `remotion/src/PovReel.tsx` | per-scene VO `<Audio>` + music bed with `duckVolume` |
| `remotion/src/Root.tsx` | default props for `voices`/`music`/`voiceDurations` |
| `remotion/src/lib/duckVolume.ts` (+ test) | pure duck-volume function + vitest |
| `tests/…` | bridge + loudnorm tests |
