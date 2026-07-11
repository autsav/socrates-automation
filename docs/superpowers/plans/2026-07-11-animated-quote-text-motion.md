# AnimatedQuote Beat-Synced Text Motion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable Remotion `AnimatedQuote` component (masked word rise + auto keyword punch + voiceover beat sync + quote-mark bloom) and the Python plumbing to feed it real beats and audio.

**Architecture:** Python detects beats from the reel's voiceover (`beat_sync.detect_beats`), writes them plus an audio filename into the `reel-data.json` bridge, and copies the audio into `remotion/public/`. The Remotion composition plays the audio via `<Audio>` (baking sound into the render) and drives the quote scene's motion off the beat timestamps. Everything degrades to today's silent behavior when no voiceover is present.

**Tech Stack:** Python 3.11 (repo `.venv`), pytest; Remotion 4 / React 18 / TypeScript 5; vitest (added for one pure-function test).

## Global Constraints

- **Scope:** Only the Remotion **Quote scene** changes. Hook and CTA scenes keep the existing `AnimatedText` component. (spec §1, §2)
- **Graceful fallback:** `generate_remotion_reel` MUST never raise and MUST return `None` when Remotion is unavailable. No voiceover / empty beats → silent reel exactly as today, `beats: []`, `audio` omitted. (spec §3, §6)
- **No schema changes:** Do not touch `quotes.xlsx` or content props. Keyword is auto-detected. (spec §2)
- **Audio mux is Remotion-native:** use `<Audio>` in the composition; do NOT add an ffmpeg mux step. (spec §3)
- **Moods invariant:** the 7 Python `SUPPORTED_MOODS` must keep matching the `theme.ts` palette keys (an existing test enforces this — don't break it).
- **Run Python tests with the 3.11 venv:** `.venv/bin/python -m pytest …` (the system Python is 3.9 and cannot import the repo).
- **Beats are absolute reel-seconds** in the bridge; Remotion converts to scene-relative frames as `round(t*fps) - sceneStartFrame`.
- **Branch:** `feat/animated-quote-text-motion` (already checked out).

---

### Task 1: Bridge file carries beats + audio (Python)

Add beat detection and audio-copy to `write_bridge_file`, keeping the existing signature backward-compatible and the no-voiceover path unchanged.

**Files:**
- Modify: `src/video/remotion_reel.py` (`write_bridge_file`)
- Test: `tests/test_remotion_reel.py`

**Interfaces:**
- Consumes: `beat_sync.detect_beats(audio_path: Path, min_peak_distance=1.2) -> list[float]`
- Produces: `write_bridge_file(..., bridge_path=BRIDGE_FILE, voiceover_path: Path | None = None) -> Path`. When `voiceover_path` is given, the JSON payload gains `beats: list[float]` and `audio: str` (basename of the copied file, e.g. `"reel-audio.wav"`), and the audio is copied to `bridge_path.parent / audio`. When `None`, payload has `beats: []` and no `audio` key.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_remotion_reel.py`:

```python
def test_write_bridge_file_no_voiceover_has_empty_beats_no_audio(tmp_path):
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p)
    data = json.loads(p.read_text())
    assert data["beats"] == []
    assert "audio" not in data


def test_write_bridge_file_with_voiceover_adds_beats_and_copies_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(rr.beat_sync, "detect_beats", lambda path, **k: [0.4, 1.1, 2.7])
    vo = tmp_path / "voiceover.wav"
    vo.write_bytes(b"RIFF....fake-wav")
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file(
        "h", "q", "a", "c", "calm_stoic", 10.0, 30,
        bridge_path=p, voiceover_path=vo,
    )
    data = json.loads(p.read_text())
    assert data["beats"] == [0.4, 1.1, 2.7]
    assert data["audio"] == "reel-audio.wav"
    assert (tmp_path / "reel-audio.wav").read_bytes() == b"RIFF....fake-wav"


def test_write_bridge_file_beat_detection_failure_degrades_to_empty(tmp_path, monkeypatch):
    def boom(path, **k):
        raise RuntimeError("librosa exploded")
    monkeypatch.setattr(rr.beat_sync, "detect_beats", boom)
    vo = tmp_path / "voiceover.wav"
    vo.write_bytes(b"x")
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file(
        "h", "q", "a", "c", "calm_stoic", 10.0, 30,
        bridge_path=p, voiceover_path=vo,
    )
    data = json.loads(p.read_text())
    assert data["beats"] == []
    # audio is still copied even if beat detection failed
    assert data["audio"] == "reel-audio.wav"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -k "beats or voiceover" -v`
Expected: FAIL — `AttributeError: module 'src.video.remotion_reel' has no attribute 'beat_sync'` / unexpected `voiceover_path` kwarg / `KeyError: 'beats'`.

- [ ] **Step 3: Implement**

In `src/video/remotion_reel.py`, add the import near the top (after the existing imports):

```python
from src.video import beat_sync
```

Replace the `write_bridge_file` function with:

```python
def write_bridge_file(
    hook: str,
    quote: str,
    attribution: str,
    cta: str,
    mood: str,
    duration: float,
    fps: int,
    bridge_path: Path = BRIDGE_FILE,
    voiceover_path: Path | None = None,
) -> Path:
    """Write the reel-data.json bridge file the Remotion composition reads.

    When ``voiceover_path`` is supplied, its beats are detected and written as
    ``beats`` (absolute seconds), and the audio is copied next to the bridge as
    ``reel-audio<ext>`` and referenced by the ``audio`` key so Remotion's
    ``<Audio>`` (via ``staticFile``) can play — and bake — it into the render.
    With no voiceover, ``beats`` is ``[]`` and ``audio`` is omitted, giving the
    original silent-reel behavior.

    Returns the path written. Exposed separately so tests can exercise it
    without invoking Node.
    """
    if mood not in SUPPORTED_MOODS:
        mood = SUPPORTED_MOODS[0]

    beats: list[float] = []
    audio_name: str | None = None
    if voiceover_path is not None and Path(voiceover_path).exists():
        voiceover_path = Path(voiceover_path)
        audio_name = "reel-audio" + voiceover_path.suffix
        bridge_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(voiceover_path, bridge_path.parent / audio_name)
        try:
            beats = beat_sync.detect_beats(voiceover_path)
        except Exception as e:  # pragma: no cover - defensive
            print(f"  [remotion] beat detection failed ({e}) — reel stays un-synced")
            beats = []

    payload = {
        "hook": hook or "",
        "quote": quote or "",
        "attribution": attribution or "",
        "cta": cta or "",
        "mood": mood,
        "duration": round(float(duration), 3),
        "fps": int(fps),
        "beats": beats,
    }
    if audio_name:
        payload["audio"] = audio_name

    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return bridge_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -v`
Expected: PASS (new tests + all existing bridge tests, including `test_write_bridge_file_roundtrip`, which still passes because it doesn't assert on absent keys).

- [ ] **Step 5: Commit**

```bash
git add src/video/remotion_reel.py tests/test_remotion_reel.py
git commit -m "feat(remotion): bridge file carries voiceover beats + audio"
```

---

### Task 2: Thread `voiceover_path` through `generate_remotion_reel` (Python)

Let callers pass a voiceover file that flows into the bridge.

**Files:**
- Modify: `src/video/remotion_reel.py` (`generate_remotion_reel`)
- Test: `tests/test_remotion_reel.py`

**Interfaces:**
- Produces: `generate_remotion_reel(..., fps=30, timeout=600, voiceover_path: Path | None = None) -> Path | None`. Forwards `voiceover_path` to `write_bridge_file`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_remotion_reel.py`:

```python
def test_generate_forwards_voiceover_path_to_bridge(tmp_path, monkeypatch):
    """generate_remotion_reel must pass voiceover_path into write_bridge_file."""
    monkeypatch.setattr(rr, "remotion_available", lambda: True)
    seen = {}

    def fake_write(*args, **kwargs):
        seen["voiceover_path"] = kwargs.get("voiceover_path")
        p = tmp_path / "reel-data.json"
        p.write_text("{}")
        return p

    class _Ok:
        returncode = 0
        stderr = ""
        stdout = ""

    out = tmp_path / "reel.mp4"

    def fake_run(*a, **k):
        out.write_bytes(b"fake-mp4")
        return _Ok()

    monkeypatch.setattr(rr, "write_bridge_file", fake_write)
    monkeypatch.setattr(rr.subprocess, "run", fake_run)

    vo = tmp_path / "vo.wav"
    vo.write_bytes(b"x")
    rr.generate_remotion_reel(
        hook="h", quote="q", cta="c", output_path=out, voiceover_path=vo,
    )
    assert seen["voiceover_path"] == vo
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py::test_generate_forwards_voiceover_path_to_bridge -v`
Expected: FAIL — `generate_remotion_reel() got an unexpected keyword argument 'voiceover_path'`.

- [ ] **Step 3: Implement**

In `src/video/remotion_reel.py`, add the parameter to `generate_remotion_reel`'s signature (after `timeout: int = 600,`):

```python
    voiceover_path: Path | None = None,
```

And pass it through in the `write_bridge_file(...)` call inside `generate_remotion_reel` — add this line to the existing kwargs:

```python
        voiceover_path=voiceover_path,
```

(so the call reads `hook=..., quote=..., attribution=..., cta=..., mood=..., duration=..., fps=..., voiceover_path=voiceover_path`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/video/remotion_reel.py tests/test_remotion_reel.py
git commit -m "feat(remotion): generate_remotion_reel forwards voiceover_path"
```

---

### Task 3: Pipeline passes the voiceover to the Remotion render (Python)

Ensure a reel voiceover is produced before the Remotion call and its path is handed to `generate_remotion_reel`. If no voiceover can be produced, the call is made without a path (silent reel — unchanged).

**Files:**
- Modify: `pipeline.py` (around the `generate_remotion_reel` call at ~line 458–470)

**Interfaces:**
- Consumes: `generate_remotion_reel(..., voiceover_path=...)` from Task 2; `prepare_reel_voiceover` / `edge_tts` voiceover helpers already imported at the top of `pipeline.py`.

- [ ] **Step 1: Read the current call site**

Run: `sed -n '455,475p' pipeline.py`
Confirm the `if use_remotion:` block calls `generate_remotion_reel(hook=..., quote=..., attribution=..., cta=..., mood=..., output_path=...)` with no voiceover.

- [ ] **Step 2: Add a local voiceover-for-reel helper call before the render**

Immediately **before** the `if use_remotion:` line, insert:

```python
    # Produce a short voiceover up front so the Remotion path can beat-sync to it
    # and bake it into the render. Best-effort: any failure → silent reel.
    reel_voiceover_path = None
    try:
        from src.audio.edge_tts_engine import prepare_reel_voiceover_edge_tts, edge_tts_available
        if edge_tts_available():
            vo = prepare_reel_voiceover_edge_tts(
                hook=hook_text, quote=quote_data["quote"], cta=cta_text,
            )
            if isinstance(vo, dict):
                reel_voiceover_path = vo.get("audio_path") or vo.get("path")
            elif vo:
                reel_voiceover_path = vo
    except Exception as e:
        log.warning(f"  [remotion] reel voiceover unavailable ({e}) — silent reel")
```

> **Note for the implementer:** verify the return shape of `prepare_reel_voiceover_edge_tts` by reading `src/audio/edge_tts_engine.py`. The snippet handles both a dict (`audio_path`/`path` key) and a bare path/str. If it returns something else, adapt the extraction so `reel_voiceover_path` ends up as a filesystem path to the `.mp3`/`.wav`, or `None`.

- [ ] **Step 3: Pass the path into the render call**

In the `generate_remotion_reel(...)` call, add the argument:

```python
                    voiceover_path=reel_voiceover_path,
```

- [ ] **Step 4: Verify pipeline still imports and the reel path runs**

Run: `.venv/bin/python -c "import ast; ast.parse(open('pipeline.py').read()); print('pipeline.py parses')"`
Expected: `pipeline.py parses`

Run the existing suite to confirm nothing regressed:
Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (no new failures vs. the pre-change baseline).

- [ ] **Step 5: Commit**

```bash
git add pipeline.py
git commit -m "feat(pipeline): feed reel voiceover to Remotion render for beat sync"
```

---

### Task 4: `pickEmphasisIndex` pure function + vitest (Remotion)

Add the keyword-selection helper with a real unit test. This task also introduces vitest to the Remotion project (needed to test the pure function TDD-style).

**Files:**
- Create: `remotion/src/lib/emphasis.ts`
- Create: `remotion/src/lib/emphasis.test.ts`
- Modify: `remotion/package.json` (add vitest devDep + `test` script)

**Interfaces:**
- Produces: `pickEmphasisIndex(words: string[]): number` — index of the last content word (has a letter/number, not in a small stopword set); fallback to the longest content word; final fallback `words.length - 1` (or `0` for empty-ish input).

- [ ] **Step 1: Add vitest to the Remotion project**

Run:
```bash
cd remotion && npm install -D vitest@^2.0.0
```

Then add a `test` script to `remotion/package.json` `"scripts"`:

```json
    "test": "vitest run",
```

- [ ] **Step 2: Write the failing test**

Create `remotion/src/lib/emphasis.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { pickEmphasisIndex } from "./emphasis";

describe("pickEmphasisIndex", () => {
  it("picks the last content word, skipping trailing punctuation", () => {
    const words = "The beginning of wisdom is the desire to learn.".split(/\s+/);
    // last word is "learn." -> index 8
    expect(pickEmphasisIndex(words)).toBe(words.length - 1);
  });

  it("skips a trailing stopword to reach a content word", () => {
    const words = ["Know", "thyself", "and", "the"];
    // "the" is a stopword -> fall back to "and"? no, "and" is a stopword too -> "thyself"
    expect(pickEmphasisIndex(words)).toBe(1);
  });

  it("falls back to the longest content word when all trailing are stopwords", () => {
    const words = ["Wisdom", "is", "the", "of"];
    // only "wisdom" is a content word -> index 0
    expect(pickEmphasisIndex(words)).toBe(0);
  });

  it("handles a single word", () => {
    expect(pickEmphasisIndex(["Courage"])).toBe(0);
  });

  it("handles empty input without throwing", () => {
    expect(pickEmphasisIndex([])).toBe(0);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd remotion && npm test`
Expected: FAIL — cannot resolve `./emphasis` (module does not exist yet).

- [ ] **Step 4: Implement**

Create `remotion/src/lib/emphasis.ts`:

```ts
const STOPWORDS = new Set([
  "the", "a", "an", "of", "to", "is", "in", "and", "it", "you", "i",
]);

/** Strip everything but letters/numbers and lowercase, for classification. */
function clean(word: string): string {
  return word.replace(/[^\p{L}\p{N}]/gu, "").toLowerCase();
}

/**
 * Choose the word to emphasize in a quote:
 *  1. the last content word (has letters/numbers, not a stopword), else
 *  2. the longest content word, else
 *  3. the last word (index length-1), or 0 for empty input.
 */
export function pickEmphasisIndex(words: string[]): number {
  if (words.length === 0) return 0;

  for (let i = words.length - 1; i >= 0; i--) {
    const c = clean(words[i]);
    if (c && !STOPWORDS.has(c)) return i;
  }

  let best = -1;
  let bestLen = 0;
  for (let i = 0; i < words.length; i++) {
    const c = clean(words[i]);
    if (c.length > bestLen) {
      bestLen = c.length;
      best = i;
    }
  }
  return best >= 0 ? best : words.length - 1;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd remotion && npm test`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add remotion/src/lib/emphasis.ts remotion/src/lib/emphasis.test.ts remotion/package.json remotion/package-lock.json
git commit -m "feat(remotion): pickEmphasisIndex keyword helper + vitest"
```

---

### Task 5: `AnimatedQuote` component (Remotion)

The visual core: masked word rise (#2) + keyword punch (#5) + quote-mark bloom (#20), consuming beats for the punch timing.

**Files:**
- Modify: `remotion/src/components/AnimatedText.tsx` (export `autoFontSize` for reuse)
- Create: `remotion/src/components/AnimatedQuote.tsx`

**Interfaces:**
- Consumes: `pickEmphasisIndex` (Task 4); `autoFontSize(text: string, base: number): number` (now exported from `AnimatedText.tsx`); `FONT_FAMILY`, `Palette` from `../styles/theme`.
- Produces: `AnimatedQuote: React.FC<{ quote: string; palette: Palette; beats?: number[]; sceneStartFrame: number; startFrame?: number; fontSize?: number; stagger?: number }>`.

- [ ] **Step 1: Export `autoFontSize` from `AnimatedText.tsx`**

In `remotion/src/components/AnimatedText.tsx`, change the helper declaration:

```ts
function autoFontSize(text: string, base: number): number {
```

to:

```ts
export function autoFontSize(text: string, base: number): number {
```

- [ ] **Step 2: Create the component**

Create `remotion/src/components/AnimatedQuote.tsx`:

```tsx
import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FONT_FAMILY, Palette } from "../styles/theme";
import { autoFontSize } from "./AnimatedText";
import { pickEmphasisIndex } from "../lib/emphasis";

export interface AnimatedQuoteProps {
  quote: string;
  palette: Palette;
  /** Absolute reel-seconds of detected beats. */
  beats?: number[];
  /** Absolute (reel-global) frame at which this scene starts. */
  sceneStartFrame: number;
  /** Scene-relative frame at which the reveal starts. */
  startFrame?: number;
  fontSize?: number;
  /** Stagger between words, seconds. */
  stagger?: number;
}

/** Smallest scene-relative beat frame at or after `notBefore`, else null. */
function nearestBeatFrame(
  beats: number[],
  fps: number,
  sceneStartFrame: number,
  notBefore: number
): number | null {
  let best: number | null = null;
  for (const t of beats) {
    const rel = Math.round(t * fps) - sceneStartFrame;
    if (rel >= notBefore) best = best === null ? rel : Math.min(best, rel);
  }
  return best;
}

export const AnimatedQuote: React.FC<AnimatedQuoteProps> = ({
  quote,
  palette,
  beats = [],
  sceneStartFrame,
  startFrame = 0,
  fontSize = 146,
  stagger = 0.065,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = quote.trim().split(/\s+/);
  const size = autoFontSize(quote, fontSize);
  const staggerFrames = stagger * fps;
  const emphasis = pickEmphasisIndex(words);

  // Frame at which the emphasis word has finished revealing.
  const emphasisRevealEnd = startFrame + emphasis * staggerFrames + 24;
  // Punch fires on the nearest beat after that, else ~8 frames after reveal.
  const beatFrame = nearestBeatFrame(beats, fps, sceneStartFrame, emphasisRevealEnd);
  const triggerFrame = beatFrame ?? emphasisRevealEnd + 8;
  const punch = interpolate(
    frame,
    [triggerFrame - 3, triggerFrame, triggerFrame + 6],
    [1, 1.14, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Quote-mark bloom: springs in ~6 frames before the first word.
  const bloomSpring = spring({
    frame: frame - (startFrame - 6),
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 90 },
    durationInFrames: 22,
  });
  const bloomScale = interpolate(bloomSpring, [0, 1], [0.6, 1]);
  const bloomOpacity = interpolate(bloomSpring, [0, 1], [0, 0.22]);

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {/* #20 Quote-mark bloom — decorative, behind the words. */}
      <div
        style={{
          position: "absolute",
          top: "16%",
          left: "8%",
          fontFamily: FONT_FAMILY,
          fontWeight: 900,
          fontSize: size * 2.6,
          lineHeight: 1,
          color: palette.accent,
          opacity: bloomOpacity,
          transform: `scale(${bloomScale})`,
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        &ldquo;
      </div>

      {/* #2 Masked rise + #5 keyword punch. */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexWrap: "wrap",
          alignContent: "center",
          justifyContent: "center",
          alignItems: "center",
          gap: `${size * 0.04}px ${size * 0.16}px`,
          padding: "0 6%",
          textAlign: "center",
        }}
      >
        {words.map((word, i) => {
          const wordStart = startFrame + i * staggerFrames;
          const enter = spring({
            frame: frame - wordStart,
            fps,
            config: { damping: 14, mass: 0.7, stiffness: 90 },
            durationInFrames: 24,
          });
          // Mask rise: word translates up from one line-height below.
          const rise = interpolate(enter, [0, 1], [size * 1.1, 0]);
          const opacity = interpolate(enter, [0, 0.5], [0, 1], {
            extrapolateRight: "clamp",
          });
          const isEmphasis = i === emphasis;
          const scale = isEmphasis ? punch : 1;
          const color = isEmphasis ? palette.accent : palette.text;

          return (
            <span
              key={`${word}-${i}`}
              style={{
                display: "inline-block",
                overflow: "hidden",
                paddingBottom: size * 0.12,
                marginBottom: -size * 0.12,
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  fontFamily: FONT_FAMILY,
                  fontWeight: 900,
                  fontSize: size,
                  lineHeight: 1.02,
                  letterSpacing: "-0.01em",
                  color,
                  opacity,
                  transform: `translateY(${rise}px) scale(${scale})`,
                  WebkitTextStroke: `${Math.max(2, size * 0.02)}px ${palette.stroke}`,
                  paintOrder: "stroke fill",
                  textShadow: palette.dark
                    ? `0 0 28px ${palette.glow}, 0 ${size * 0.03}px ${size * 0.05}px rgba(0,0,0,0.85)`
                    : `0 ${size * 0.02}px ${size * 0.04}px rgba(0,0,0,0.25)`,
                }}
              >
                {word}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
};
```

- [ ] **Step 3: Type-check**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add remotion/src/components/AnimatedText.tsx remotion/src/components/AnimatedQuote.tsx
git commit -m "feat(remotion): AnimatedQuote — masked rise, keyword punch, quote bloom"
```

---

### Task 6: Wire beats + audio through the composition (Remotion)

Give `PovReel` the `beats`/`audio` props, play the audio, and route beats into `QuoteScene` → `AnimatedQuote`.

**Files:**
- Modify: `remotion/src/PovReel.tsx` (props interface, defaults, `<Audio>`, pass beats + scene start to `QuoteScene`)
- Modify: `remotion/src/components/QuoteScene.tsx` (accept `beats` + `sceneStartFrame`, render `AnimatedQuote`)

**Interfaces:**
- Consumes: `AnimatedQuote` (Task 5).
- Produces: `PovReelProps` gains `beats?: number[]` and `audio?: string`; `QuoteScene` gains props `beats?: number[]` and `sceneStartFrame: number`.

- [ ] **Step 1: Extend `PovReelProps` and defaults**

In `remotion/src/PovReel.tsx`, add to `PovReelProps`:

```ts
  beats?: number[];
  audio?: string;
```

and to `povReelDefaultProps`:

```ts
  beats: [],
  audio: undefined,
```

- [ ] **Step 2: Import `Audio` + `staticFile` and destructure new props**

Change the remotion import to include `Audio` and `staticFile`:

```tsx
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
```

In the `PovReel` component signature, destructure `beats` and `audio`:

```tsx
export const PovReel: React.FC<PovReelProps> = ({
  hook,
  quote,
  attribution,
  cta,
  mood,
  beats = [],
  audio,
}) => {
```

- [ ] **Step 3: Play the audio and pass beats into the Quote sequence**

Inside the root `<AbsoluteFill …>`, add near the top (after the opening tag, before `PulsingBg`):

```tsx
      {audio ? <Audio src={staticFile(audio)} /> : null}
```

Change the Quote `<Sequence>` body to pass beats + the scene start frame (`hookF`):

```tsx
      <Sequence from={hookF} durationInFrames={quoteF} name="Quote">
        <QuoteScene
          quote={quote}
          attribution={attribution}
          palette={palette}
          beats={beats}
          sceneStartFrame={hookF}
        />
      </Sequence>
```

- [ ] **Step 4: Update `QuoteScene` to use `AnimatedQuote`**

In `remotion/src/components/QuoteScene.tsx`:

Replace the import of `AnimatedText`:

```tsx
import { AnimatedText } from "./AnimatedText";
```

with:

```tsx
import { AnimatedQuote } from "./AnimatedQuote";
```

Extend the component's prop type:

```tsx
export const QuoteScene: React.FC<{
  quote: string;
  attribution: string;
  palette: Palette;
  beats?: number[];
  sceneStartFrame: number;
}> = ({ quote, attribution, palette, beats = [], sceneStartFrame }) => {
```

Replace the `<AnimatedText … />` block with:

```tsx
        <AnimatedQuote
          quote={quote}
          palette={palette}
          beats={beats}
          sceneStartFrame={sceneStartFrame}
          fontSize={146}
          stagger={0.065}
        />
```

(Leave the attribution spring + underline block below it unchanged.)

- [ ] **Step 5: Type-check the whole project**

Run: `cd remotion && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add remotion/src/PovReel.tsx remotion/src/components/QuoteScene.tsx
git commit -m "feat(remotion): play voiceover audio + route beats into AnimatedQuote"
```

---

### Task 7: End-to-end smoke render

Verify the composition renders a frame and (if Node is present) a full reel, exercising bloom + masked rise + punch.

**Files:** none (verification only).

- [ ] **Step 1: Render a mid-quote still**

Write a bridge with beats + a tiny audio file, then render a still. Run:

```bash
cd remotion
cat > public/reel-data.json <<'JSON'
{"hook":"Purpose doesn't find you. You find it.","quote":"The beginning of wisdom is the desire to learn.","attribution":"— Socrates","cta":"Save this.","mood":"dark_philosophical","duration":10.5,"fps":30,"beats":[4.0,4.8,5.6,6.4]}
JSON
npx remotion still src/index.ts PovReel out/quote-frame.png --frame=170 --props=public/reel-data.json --log=error
```

Expected: `out/quote-frame.png` is written. Open it and confirm: words are masked/legible, the emphasis word ("learn") is accent-colored, and the faint large opening quote mark is visible top-left.

- [ ] **Step 2: (If Node + deps present) run the Python real-render test**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -v`
Expected: PASS. (`test_real_render_produces_mp4` runs only when Remotion deps are installed; otherwise it's skipped — both are acceptable.)

- [ ] **Step 3: Full suite green**

Run: `.venv/bin/python -m pytest tests/ -q` and `cd remotion && npm test`
Expected: PASS on both.

- [ ] **Step 4: Commit any fixups**

If Step 1 revealed a visual glitch you fixed (positioning, sizes), commit it:

```bash
git add remotion/src
git commit -m "fix(remotion): AnimatedQuote visual tuning from smoke render"
```

---

## Self-Review

**Spec coverage:**
- §4.1 AnimatedQuote (masked rise / keyword punch / bloom) → Task 5 (+ helper Task 4). ✓
- §4.2 QuoteScene uses AnimatedQuote, passes beats → Task 6 Step 4. ✓
- §4.3 PovReel beats/audio props + `<Audio>` + thread beats → Task 6 Steps 1–3. ✓
- §4.4 Root/default props for beats/audio → Task 6 Step 1 (defaults live in `PovReel.tsx`'s `povReelDefaultProps`, which `Root.tsx` imports — no separate Root edit needed). ✓
- §4.5 remotion_reel.py voiceover_path, detect beats, copy audio, payload → Tasks 1–2. ✓
- §4.6 pipeline ensures voiceover precedes render + passes path → Task 3. ✓
- §5 data flow → Tasks 1–6 combined. ✓
- §6 error handling: Node absent (existing), no voiceover (Task 1 empty-beats path + test), detect_beats failure (Task 1 test), beats outside scene window (`nearestBeatFrame` filter, Task 5) → covered. ✓
- §7 testing: bridge tests (Task 1), pickEmphasisIndex tests (Task 4), smoke still (Task 7) → covered. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. Task 3 Step 2 contains a genuine implementer note to verify a return shape — the code handles the documented shapes, which is concrete, not a placeholder.

**Type consistency:** `pickEmphasisIndex(words: string[]): number`, `autoFontSize(text, base): number`, `write_bridge_file(..., voiceover_path=None)`, `generate_remotion_reel(..., voiceover_path=None)`, `QuoteScene(... beats, sceneStartFrame)`, `AnimatedQuote(... beats, sceneStartFrame)` — names/signatures match across tasks. `beats` are absolute seconds everywhere; conversion to scene frames happens only in `nearestBeatFrame`. ✓
