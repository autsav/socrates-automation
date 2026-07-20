# Real-Sync + Animation Director — Design Spec

**Date:** 2026-07-20
**Status:** Approved (Approach A: real timestamps + coded animation director; LLM markup deferred)
**Goal:** Fix voice/on-screen-text desync at the source (real ElevenLabs word timestamps) and make reels fun to watch with a deterministic, timestamp-driven animation technique pack — cinematic-kinetic style.

## Problem

- `elevenlabs_engine._estimate_word_timings` fakes word timings by spreading words evenly across audio duration. Real speech is uneven → karaoke highlights, chunk cuts, and stress-point clip cuts drift from the voice; error compounds across 60–90s stories.
- Text animation today is one pattern (word-by-word spring reveal) — no within-reel variety.

## Locked decisions

| Decision | Choice |
|---|---|
| Style boundary | Cinematic-kinetic (word pops, shakes, color flashes — no emoji/MrBeast effects) |
| Emphasis intelligence | Coded word-class rules; NO LLM animation agent (deferred) |
| Determinism | Per-row seed; same inputs → same render |
| Back-compat | Payloads without `cls` render exactly as today |
| Fallback | with-timestamps failure → current plain endpoint + estimated timings |

## 1. Real word timestamps

**Modify:** `src/audio/elevenlabs_engine.py`
- `generate_voiceover` calls `POST {ELEVENLABS_API}/text-to-speech/{voice_id}/with-timestamps` (same body + model). Response JSON: `audio_base64`, `alignment: {characters, character_start_times_seconds, character_end_times_seconds}`. Decode audio to the output path.
- New `_alignment_to_words(text: str, alignment: dict) -> list[dict]` — walks characters, groups into words at whitespace, excludes `<break .../>` tag characters (tags are narration silence, not display words), returns `[{"w": word, "start": s, "end": e}]`. Malformed/None alignment → `[]`.
- `generate_scene_voiceover` writes the SRT from real timings when available, else falls back to `_estimate_word_timings` (unchanged). Whole call best-effort: any with-timestamps failure retries the plain endpoint once.

## 2. Word classification

**New:** `src/video/word_classes.py`
- `classify_words(words: list[dict]) -> list[dict]` — returns the same list with `cls` added per word:
  - `num`: contains a digit or is a number word (one..hundred, thousand, million).
  - `neg`: in negation set {no, not, never, nobody, nothing, stop, wrong, dead, can't, won't, don't, refuse, quit}.
  - `power`: in emotion lexicon {fear, afraid, broke, alone, rich, poor, die, death, truth, lie, pain, lost, win, fail, weak, strong, enemy, storm} (~30 words).
  - `stress`: longest word of each sentence AND each sentence-final word (when not already tagged).
  - `end`: sentence-terminal word (word ends with . ! ?).
  - default `plain`. Priority when multiple match: num > neg > power > end > stress > plain (single cls per word).
- Pure, never raises (garbage in → all plain).

**Modify:** `src/video/remotion_reel.py` `write_bridge_file` — every `wordTimes` list passes through `classify_words` before writing. Payload additive: `{"w", "start", "end", "cls"}`.

## 3. Technique pack + director (Remotion)

**New:** `remotion/src/lib/animDirector.ts`
- `type WordFx = "pop" | "shake" | "glowpop" | "countup" | "cascade" | "plain"`
- `effectFor(cls: string | undefined, index: number, seed: number): WordFx` — deterministic: `num→countup`, `neg→shake`, `power→glowpop`, `stress→pop` (two pop flavors alternated by `(seed + index) % 2`), else `plain`. Undefined cls → `plain` (back-compat).
- `seed` = row number, passed through the payload as `animSeed` (int, default 0).

**Component wiring (modify):**
- `remotion/src/lib/wordAt.ts` `WordTime` type gains `cls?: string`.
- `AnimatedText.tsx`: per-word, look up `effectFor` → apply: `pop` scale 1→1.18→1 over 8 frames from the word's REAL start + accent color during the pop; `shake` ±3px x-jitter 4 frames + brief desaturate (filter) ; `glowpop` accent color + glow radius ×2 for 10 frames; `countup` renders 0→N rolling over 8 frames (only when the word parses as int ≤ 9999, else falls back to pop); `plain` = current behavior.
- `AnimatedQuote.tsx`: quote scene uses letter-cascade — per-letter stagger derived from the word's real start/end span (letters spread across the word's actual spoken duration), keeping existing emphasis punch.
- Sentence-end tick: `BridgeScene.tsx` — on chunk boundaries that coincide with a `cls==="end"` word, a 2-frame 0.25-opacity white flash (reuses WhiteFlash pattern, smaller).
- Ghost-trail: in `PovReel.tsx` speed-ramp window (quoteStart-12..quoteStart), text layers render a 3-frame echo at 0.3 opacity (single extra div, transform-lagged).
- CTA freeze-pop: `CtaScene.tsx` — after all words settle, one scale pulse 1→1.06→1 at the CTA VO end (from voiceDurations.cta), existing style.

## 4. Payload

`write_bridge_file(..., anim_seed: int = 0)` → `payload["animSeed"]`; pipeline passes `row_number or 0`. All additive.

## 5. Error handling

- with-timestamps HTTP failure/malformed alignment → plain endpoint + estimated timings (log one line).
- classify_words never raises; missing cls in TS → plain rendering.
- countup non-numeric → pop.
- No new failure paths in the render (pure visual code).

## 6. Testing

- Python: `_alignment_to_words` on a fixture alignment (incl. break-tag exclusion, multi-space); classifier word-class cases + priority; payload carries cls + animSeed; fallback path when alignment missing.
- TS: `npx tsc --noEmit`.
- Gate renders: story dry-run — extract frame at a known word's real start (from payload) and assert the word is on screen (sync proof); frame-check a `power` word's color pop and a number's presence; punch dry-run ≤15s intact.
- Live acceptance post.

## Not in scope

LLM animation markup, emoji/meme effects, new arcs, edge-tts changes (already has real boundaries), music-driven effects.
