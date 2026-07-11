# AnimatedQuote — Beat-Synced Text Motion for the POV Reel

**Date:** 2026-07-11
**Status:** Approved (design)
**Scope:** Remotion Quote scene only. Hook/CTA unchanged.

## 1. Goal

Add one reusable Remotion component, `AnimatedQuote`, that renders the reel's
payoff quote with four professional text-motion techniques, wired to the reel's
real voiceover audio:

1. **#2 Masked rise** — words rise from behind a clipped edge (premium reveal).
2. **#5 Keyword punch** — the payoff word scale/color-pops, timed to the nearest beat.
3. **#19 Beat sync** — beats detected from the voiceover drive the punch (and the
   reel gains an audible, baked-in audio track).
4. **#20 Quote-mark bloom** — an oversized opening quote mark blooms in before the words.

The remaining 16 brainstormed techniques are explicitly **out of scope**.

## 2. Non-goals (YAGNI)

- No changes to the Hook or CTA scenes (they keep the existing `AnimatedText`).
- No changes to `quotes.xlsx` or the content schema (keyword is auto-detected).
- No new music/soundtrack system — beats come from the existing voiceover only.
- No manual emphasis markers.

## 3. Design decisions (locked)

| Decision | Choice |
|---|---|
| Beat source (#19) | **Real audio.** Detect beats from the voiceover via `beat_sync.detect_beats()`; pass timestamps to Remotion; play `<Audio>` so the render bakes sound in. |
| Keyword pick (#5) | **Auto-heuristic.** Last content word (skip trailing punctuation + stopwords); fallback to the longest content word. |
| Audio mux | **Remotion-native.** `<Audio>` in the composition; `npx remotion render` bakes it into the mp4. No separate ffmpeg mux step. |
| Fallback | **Graceful.** No voiceover / no beats → silent reel exactly as today; motion falls back to spring-only timing. |

> **Amendment (2026-07-11, during execution):** `prepare_reel_voiceover_edge_tts` returns **three separate scene tracks** (`hook_voice`/`quote_voice`/`cta_voice`), not one file. Per the "quote track, aligned" decision we use **`quote_voice` only** as the reel's audio + beat source, played under the quote scene via `<Sequence from={hookF}>`. Consequently **beats are scene-relative seconds** (0 = quote-scene start), so `AnimatedQuote` uses `round(t*fps)` directly with **no `sceneStartFrame` offset**. This supersedes §4.1's "absolute reel-seconds" and §4.3's "`<Audio>` at root" wording.

## 4. Architecture

### 4.1 `remotion/src/components/AnimatedQuote.tsx` (NEW)

Composes three techniques; replaces `AnimatedText` **inside `QuoteScene` only**.

- **Masked rise (#2):** each word wrapped in an `overflow: hidden` mask element;
  the inner word animates `translateY` from `100%` → `0` on a staggered spring
  (reuse the existing spring config feel from `AnimatedText`). Preserve the
  existing legibility treatment (stroke, glow, auto font-size heuristic from
  `AnimatedText.autoFontSize`).
- **Keyword punch (#5):** pure function `pickEmphasisIndex(words: string[]): number`
  — returns the index of the last content word (ignore words that are only
  punctuation; skip a small stopword set: `the,a,an,of,to,is,in,and,it,you,i`);
  fallback to the longest content word; final fallback `words.length - 1`.
  The emphasis word gets an additional scale pop (~1.0 → 1.14 → 1.0 over ~6
  frames) and a shift toward `palette.accent`, triggered at the frame of the
  **nearest beat** at/after its reveal; if no beats, trigger ~8 frames after the
  word finishes revealing.
- **Quote-mark bloom (#20):** an absolutely-positioned oversized `"`
  (open-quote glyph) in `palette.accent`, ~0.25 opacity, springs scale `0.6 → 1`
  and fades in starting ~6 frames **before** the first word's reveal. Positioned
  top-left of the quote block. Purely decorative; sits behind the words.

**Props:** `{ quote: string; palette: Palette; beats?: number[]; sceneStartFrame: number; fps: number }`.
`beats` are absolute reel-seconds; the component converts to scene-relative
frames as `round(t * fps) - sceneStartFrame` and considers only beats within the
scene.

### 4.2 `remotion/src/components/QuoteScene.tsx` (EDIT)

- Swap the `AnimatedText` call for `AnimatedQuote`, passing `beats` and the
  scene start frame (`hookF`, already computed in `PovReel`).
- Keep the existing attribution spring + underline draw-on unchanged.

### 4.3 `remotion/src/PovReel.tsx` (EDIT)

- Extend `PovReelProps` with `beats?: number[]` and `audio?: string`.
- If `audio` is set, render `<Audio src={staticFile(audio)} />` inside the root
  `AbsoluteFill` so the render includes sound.
- Pass `beats` and the quote scene's start frame (`hookF`) into `QuoteScene`.
- Existing `WhiteFlash` scene-boundary interrupts remain unchanged.

### 4.4 `remotion/src/Root.tsx` (EDIT)

- Add `beats: []` and `audio: undefined` to `povReelDefaultProps` (via the
  `PovReel.tsx` default export) so the studio preview and `calculateMetadata`
  keep working with no bridge data.

### 4.5 `src/video/remotion_reel.py` (EDIT)

- `write_bridge_file(...)`: add optional `voiceover_path: Path | None = None`.
  - If provided and readable:
    - `beats = beat_sync.detect_beats(voiceover_path)` (list of float seconds);
      on empty/exception → `beats = []`.
    - Copy the audio file into `remotion/public/reel-audio<ext>` and set
      `payload["audio"] = "reel-audio<ext>"`.
    - Set `payload["beats"] = beats`.
  - If not provided → omit `audio`, set `payload["beats"] = []`.
- `generate_remotion_reel(...)`: thread a new optional `voiceover_path` param
  through to `write_bridge_file`.

### 4.6 `pipeline.py` (EDIT)

- Ensure the voiceover file exists **before** the `generate_remotion_reel` call
  (currently voiceover is produced in Phase 3, after the reel call at ~line 463).
  Reorder so voiceover generation (or at least the reel voiceover) precedes the
  Remotion render, and pass its path as `voiceover_path`.
- If no voiceover is available, call `generate_remotion_reel` without a path →
  silent reel (unchanged behavior).

## 5. Data flow

```
voiceover.wav  ─► beat_sync.detect_beats() ─► [t0, t1, …]  (seconds)
              └─► copy → remotion/public/reel-audio.wav
reel-data.json { hook, quote, attribution, cta, mood, duration, fps,
                 beats:[…], audio:"reel-audio.wav" }
   └─► PovReel ( <Audio src=reel-audio.wav> )
          └─► QuoteScene(beats, sceneStartFrame=hookF)
                 └─► AnimatedQuote
                        MaskedRise(words) + KeywordPunch(nearest beat) + QuoteBloom
```

## 6. Error handling

| Condition | Behavior |
|---|---|
| Node / Remotion not installed | `generate_remotion_reel` returns `None` → ffmpeg POV fallback (unchanged). |
| No voiceover available | `voiceover_path=None` → `beats:[]`, no `audio` → **silent reel as today**; keyword punch fires on spring-default frame. |
| `detect_beats` errors or returns empty | Same as "no voiceover": `beats:[]`, punch on default frame. |
| Long quote | `autoFontSize` heuristic (reused) shrinks text; masked rise still per-word. |
| Beat outside quote scene window | Ignored by the scene-relative filter in `AnimatedQuote`. |

## 7. Testing

- **Python** (`tests/`):
  - `write_bridge_file` includes `beats` + `audio` when `voiceover_path` given
    (mock `detect_beats` to a fixed list; assert the copied public file + payload).
  - `write_bridge_file` omits `audio` and sets `beats:[]` when `voiceover_path=None`.
  - `detect_beats` exception path → `beats:[]`, no crash.
- **Remotion**:
  - Unit-test `pickEmphasisIndex` (stopwords, trailing punctuation, longest-word
    fallback, single-word input).
  - Manual smoke: `npx remotion still PovReel out/frame.png --frame=<mid-quote>`
    to eyeball masked rise + bloom + punch.
- Existing Python test suite must stay green.

## 8. Files touched

| File | Change |
|---|---|
| `remotion/src/components/AnimatedQuote.tsx` | NEW — masked rise + keyword punch + quote bloom |
| `remotion/src/components/QuoteScene.tsx` | EDIT — use `AnimatedQuote`, pass beats + sceneStartFrame |
| `remotion/src/PovReel.tsx` | EDIT — `beats`/`audio` props, `<Audio>`, thread to QuoteScene |
| `remotion/src/Root.tsx` | EDIT — default props for `beats`/`audio` |
| `src/video/remotion_reel.py` | EDIT — `voiceover_path`, detect beats, copy audio, payload fields |
| `pipeline.py` | EDIT — ensure voiceover precedes render, pass `voiceover_path` |
| `tests/…` | NEW — bridge-file + `pickEmphasisIndex` tests |
