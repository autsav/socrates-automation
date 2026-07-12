# Reel Visual Finish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cinematic finish on the narrated Remotion reel — real VO in CI, per-mood color grade, beat-timed camera zoom, ffmpeg-synth SFX, and karaoke-highlighted text synced to the voiceover.

**Architecture:** Ordered low-risk → high-risk. Task 1 installs edge-tts in CI. Tasks 2–3 are pure-Remotion visual (grade, zoom). Task 4 adds SFX (Python synth + Remotion playback). Task 5 captures per-word timings (Python). Task 6 drives the existing text's word highlight from those timings (Remotion), falling back to the current animation when timings are absent.

**Tech Stack:** Python 3.11 (repo `.venv`), edge-tts, ffmpeg, Remotion 4 / React / TS, vitest.

## Global Constraints

- **Run Python tests with the 3.11 venv:** `.venv/bin/python -m pytest …`.
- **Everything additive + graceful:** no `wordTimes`/`sfx` → the reel behaves exactly as 3A (music/VO + fixed-stagger text). `generate_remotion_reel` still returns `None`/never raises → ffmpeg-POV fallback. Every ffmpeg/subtitle/synth step is best-effort.
- **Bridge additions:** `wordTimes: {hook:[{w,start,end}], quote:[…], cta:[…]}` (seconds; empty lists when absent), `sfx: {whoosh, impact}` (basenames; key omitted when ffmpeg absent). Keep all 3A keys.
- **SFX synthesized with ffmpeg** into the bridge dir; no bundled audio assets.
- **Do NOT re-commit** `data/pipeline.db`. 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures are unrelated; "green" = no NEW failures. `remotion/public/reel-data.json` is dirtied by the real-render test — revert before committing.
- **Branch:** `feat/reel-visual-finish` (already checked out).

---

### Task 1: Install edge-tts in CI

**Files:**
- Modify: `requirements.txt`
- Test: `tests/test_workflow_reliability.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_workflow_reliability.py`:

```python
def test_edge_tts_in_requirements():
    assert "edge-tts" in _read("requirements.txt"), "edge-tts must be a dependency so CI can generate voiceover"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_workflow_reliability.py::test_edge_tts_in_requirements -v`
Expected: FAIL.

- [ ] **Step 3: Add the dependency**

Append a line to `requirements.txt`:

```
edge-tts>=6.1.0
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_workflow_reliability.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/test_workflow_reliability.py
git commit -m "fix(ci): install edge-tts so the reel voiceover actually runs"
```

---

### Task 2: Per-mood color grade

**Files:**
- Modify: `remotion/src/styles/theme.ts` (Grade type + `MOOD_GRADES` + `getGrade`)
- Create: `remotion/src/components/ColorGrade.tsx`, `remotion/src/lib/getGrade.test.ts`
- Modify: `remotion/src/PovReel.tsx` (wrap visual layers)

**Interfaces:**
- Produces: `Grade = {filter: string; vignette: number}`; `getGrade(mood) -> Grade`; `<ColorGrade grade>`.

- [ ] **Step 1: Write the failing test**

Create `remotion/src/lib/getGrade.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { getGrade } from "../styles/theme";

describe("getGrade", () => {
  it("returns a grade for a known mood", () => {
    const g = getGrade("dark_philosophical");
    expect(typeof g.filter).toBe("string");
    expect(g.vignette).toBeGreaterThan(0);
  });
  it("falls back to a default grade for unknown moods", () => {
    const g = getGrade("nonsense");
    expect(g.filter).toContain("contrast");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd remotion && npm test`
Expected: FAIL — `getGrade` not exported.

- [ ] **Step 3: Add grade to theme**

In `remotion/src/styles/theme.ts`, append:

```ts
export interface Grade {
  filter: string;
  vignette: number; // 0..1 darkness at the edges
}

export const MOOD_GRADES: Partial<Record<MoodName, Grade>> = {
  dark_philosophical: { filter: "contrast(1.1) saturate(1.05)", vignette: 0.55 },
  dramatic_ancient: { filter: "contrast(1.12) saturate(1.1) sepia(0.08)", vignette: 0.6 },
  cinematic_hopeful: { filter: "contrast(1.06) saturate(1.15) brightness(1.03)", vignette: 0.4 },
  stark_minimal: { filter: "contrast(1.15) saturate(0.9)", vignette: 0.35 },
  epic_warrior: { filter: "contrast(1.14) saturate(1.12)", vignette: 0.55 },
  mystical_greek: { filter: "contrast(1.08) saturate(1.18) hue-rotate(-6deg)", vignette: 0.6 },
  calm_stoic: { filter: "contrast(1.04) saturate(1.06) brightness(1.02)", vignette: 0.4 },
};

const DEFAULT_GRADE: Grade = { filter: "contrast(1.08) saturate(1.1)", vignette: 0.5 };

export function getGrade(mood: string | undefined): Grade {
  return (mood && MOOD_GRADES[mood as MoodName]) || DEFAULT_GRADE;
}
```

- [ ] **Step 4: Create `ColorGrade`**

Create `remotion/src/components/ColorGrade.tsx`:

```tsx
import React from "react";
import { AbsoluteFill } from "remotion";
import { Grade } from "../styles/theme";

const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

/** Cinematic finish: a CSS filter on the content, plus a vignette and a subtle
 *  film-grain overlay. Wrap only the VISUAL layers. */
export const ColorGrade: React.FC<{ grade: Grade; children: React.ReactNode }> = ({ grade, children }) => (
  <AbsoluteFill>
    <AbsoluteFill style={{ filter: grade.filter }}>{children}</AbsoluteFill>
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(0,0,0,${grade.vignette}) 100%)`,
        pointerEvents: "none",
      }}
    />
    <AbsoluteFill
      style={{ background: GRAIN, opacity: 0.06, mixBlendMode: "overlay", pointerEvents: "none" }}
    />
  </AbsoluteFill>
);
```

- [ ] **Step 5: Run to verify the test passes**

Run: `cd remotion && npm test`
Expected: PASS (getGrade tests + all existing).

- [ ] **Step 6: Wrap the visual layers in `PovReel`**

In `remotion/src/PovReel.tsx`, add imports:

```tsx
import { ColorGrade } from "./components/ColorGrade";
import { getGrade } from "./styles/theme";
```

Wrap the **visual** layers (the `PulsingBg` block + the three text `<Sequence>`s + the two `<WhiteFlash>`) in `<ColorGrade grade={getGrade(mood)}> … </ColorGrade>`. Leave every `<Audio>`/VO/music/SFX `<Sequence>` OUTSIDE the `ColorGrade` (audio must not be wrapped). Type-check: `cd remotion && npx tsc --noEmit` → only the 2 pre-existing `Root.tsx` errors.

- [ ] **Step 7: Commit**

```bash
git add remotion/src/styles/theme.ts remotion/src/components/ColorGrade.tsx remotion/src/lib/getGrade.test.ts remotion/src/PovReel.tsx
git commit -m "feat(remotion): per-mood cinematic color grade (filter + vignette + grain)"
```

---

### Task 3: Beat-timed camera zoom

**Files:**
- Create: `remotion/src/lib/cameraZoom.ts`, `remotion/src/lib/cameraZoom.test.ts`
- Modify: `remotion/src/PovReel.tsx`

**Interfaces:**
- Produces: `cameraScale(frame, durationInFrames, beatFrames) -> number`.

- [ ] **Step 1: Write the failing test**

Create `remotion/src/lib/cameraZoom.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { cameraScale } from "./cameraZoom";

describe("cameraScale", () => {
  it("pushes in slowly over the reel", () => {
    expect(cameraScale(300, 300, [])).toBeGreaterThan(cameraScale(0, 300, []));
  });
  it("kicks on a beat then decays", () => {
    const base = cameraScale(100, 300, []);
    const onBeat = cameraScale(100, 300, [100]);
    const afterBeat = cameraScale(105, 300, [100]);
    expect(onBeat).toBeGreaterThan(base);
    expect(afterBeat).toBeLessThan(onBeat);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd remotion && npm test`
Expected: FAIL — `cameraZoom` missing.

- [ ] **Step 3: Implement**

Create `remotion/src/lib/cameraZoom.ts`:

```ts
import { interpolate } from "remotion";

/** Slow camera push (1.0 → 1.06 over the reel) plus a short decaying scale kick
 *  on each beat frame. `beatFrames` are absolute composition frames. */
export function cameraScale(
  frame: number,
  durationInFrames: number,
  beatFrames: number[]
): number {
  const base = interpolate(frame, [0, durationInFrames], [1.0, 1.06], {
    extrapolateRight: "clamp",
  });
  const KICK = 0.02;
  const WIN = 6;
  let kick = 0;
  for (const bf of beatFrames) {
    if (frame >= bf && frame <= bf + WIN) {
      kick = Math.max(kick, KICK * (1 - (frame - bf) / WIN));
    }
  }
  return base + kick;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd remotion && npm test`
Expected: PASS.

- [ ] **Step 5: Apply the scale in `PovReel`**

In `remotion/src/PovReel.tsx`: import `cameraScale` and `useCurrentFrame` (add `useCurrentFrame` to the existing `remotion` import). Inside the component compute:

```tsx
  const frame = useCurrentFrame();
  const beatFrames = beats.map((t) => Math.round(t * fps) + hookF);
  const scale = cameraScale(frame, durationInFrames, beatFrames);
```

Apply `transform: scale(${scale})` to the visual-layer group — put it on a wrapping `<AbsoluteFill style={{ transform: \`scale(${scale})\` }}>` INSIDE `ColorGrade`, around the `PulsingBg` + text sequences + flashes. (Audio stays outside ColorGrade, unaffected.) Type-check (only the 2 pre-existing errors).

- [ ] **Step 6: Commit**

```bash
git add remotion/src/lib/cameraZoom.ts remotion/src/lib/cameraZoom.test.ts remotion/src/PovReel.tsx
git commit -m "feat(remotion): slow camera push + beat-timed zoom kicks"
```

---

### Task 4: SFX — ffmpeg synth + Remotion playback

**Files:**
- Modify: `src/video/remotion_reel.py` (`_synth_sfx`, bridge `sfx`)
- Modify: `remotion/src/PovReel.tsx`, `remotion/src/Root.tsx` (props)
- Test: `tests/test_remotion_reel.py`

**Interfaces:**
- Produces: `_synth_sfx(dest_dir) -> dict | None` (keys `whoosh`/`impact` → basenames); bridge `sfx`; `PovReelProps.sfx?: {whoosh?: string; impact?: string}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_remotion_reel.py`:

```python
def test_synth_sfx_creates_files(tmp_path, monkeypatch):
    monkeypatch.setattr(rr.shutil, "which", lambda n: "/usr/bin/ffmpeg")

    def fake_run(cmd, **k):
        # cmd's last arg is the output path — create it
        Path(cmd[-1]).write_bytes(b"WAV")

        class _R:
            returncode = 0
            stdout = ""
            stderr = ""
        return _R()

    monkeypatch.setattr(rr.subprocess, "run", fake_run)
    out = rr._synth_sfx(tmp_path)
    assert out == {"whoosh": "sfx-whoosh.wav", "impact": "sfx-impact.wav"}
    assert (tmp_path / "sfx-whoosh.wav").exists() and (tmp_path / "sfx-impact.wav").exists()


def test_synth_sfx_none_without_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(rr.shutil, "which", lambda n: None)
    assert rr._synth_sfx(tmp_path) is None


def test_bridge_includes_sfx(tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "_synth_sfx", lambda d: {"whoosh": "sfx-whoosh.wav", "impact": "sfx-impact.wav"})
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p)
    data = json.loads(p.read_text())
    assert data["sfx"] == {"whoosh": "sfx-whoosh.wav", "impact": "sfx-impact.wav"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -k "sfx" -v`
Expected: FAIL.

- [ ] **Step 3: Implement `_synth_sfx`**

In `src/video/remotion_reel.py`, add:

```python
def _synth_sfx(dest_dir: Path) -> dict | None:
    """Synthesize whoosh + impact SFX with ffmpeg into dest_dir. Best-effort;
    returns {'whoosh':name,'impact':name} for the ones produced, else None."""
    if not shutil.which("ffmpeg"):
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    whoosh = dest_dir / "sfx-whoosh.wav"
    impact = dest_dir / "sfx-impact.wav"
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.4:c=pink:a=0.35",
             "-af", "bandpass=f=1400:width_type=h:w=1800,afade=t=in:d=0.06,afade=t=out:st=0.24:d=0.16",
             "-ac", "1", str(whoosh)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and whoosh.exists():
            result["whoosh"] = whoosh.name
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=85:duration=0.22",
             "-af", "afade=t=out:st=0.03:d=0.19", "-ac", "1", str(impact)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and impact.exists():
            result["impact"] = impact.name
    except Exception:  # pragma: no cover - defensive
        pass
    return result or None
```

- [ ] **Step 4: Add `sfx` to the bridge payload**

In `write_bridge_file`, just before the `payload = {` line, add:

```python
    sfx = _synth_sfx(bridge_path.parent)
```

and after the `payload["voices"]`/`voiceDurations` are set (add inside the payload dict a `"sfx"` only when present) — after the existing `if music_name: payload["music"] = music_name` line, add:

```python
    if sfx:
        payload["sfx"] = sfx
```

- [ ] **Step 5: Run the Python tests**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -v`
Expected: PASS.

- [ ] **Step 6: Play SFX in `PovReel`**

In `remotion/src/PovReel.tsx`: add `sfx?: { whoosh?: string; cta?: string; impact?: string }` — actually add `sfx?: { whoosh?: string; impact?: string }` to `PovReelProps`, and `sfx: {}` to `povReelDefaultProps`; destructure `sfx = {}`. After the VO/music `<Audio>` blocks (OUTSIDE ColorGrade), add:

```tsx
      {sfx.whoosh ? (
        <>
          <Sequence from={hookF} durationInFrames={12} name="WhooshQuote">
            <Audio src={staticFile(sfx.whoosh)} volume={0.35} />
          </Sequence>
          <Sequence from={quoteEnd} durationInFrames={12} name="WhooshCta">
            <Audio src={staticFile(sfx.whoosh)} volume={0.35} />
          </Sequence>
        </>
      ) : null}
      {sfx.impact
        ? beatFrames.map((bf, i) => (
            <Sequence key={`impact-${i}`} from={bf} durationInFrames={8} name={`Impact${i}`}>
              <Audio src={staticFile(sfx.impact!)} volume={0.28} />
            </Sequence>
          ))
        : null}
```

Type-check (only the 2 pre-existing errors).

- [ ] **Step 7: Commit**

```bash
git add src/video/remotion_reel.py remotion/src/PovReel.tsx remotion/src/Root.tsx tests/test_remotion_reel.py
git commit -m "feat(reel): ffmpeg-synth whoosh/impact SFX on transitions + beats"
```

---

### Task 5: Per-word voiceover timings (Python)

**Files:**
- Modify: `src/audio/edge_tts_engine.py` (`--write-subtitles`, `parse_word_srt`, `_srt_ts`, return word lists)
- Modify: `src/video/remotion_reel.py` (`generate_remotion_reel` word params; bridge `wordTimes`)
- Modify: `pipeline.py` (capture + pass word lists)
- Test: `tests/test_word_timings.py` (NEW), `tests/test_remotion_reel.py`

**Interfaces:**
- Produces: `parse_word_srt(path) -> list[dict]` (`[{"w","start","end"}]`); `prepare_reel_voiceover_edge_tts` also returns `hook_words`/`quote_words`/`cta_words`; `generate_remotion_reel(..., hook_words=None, quote_words=None, cta_words=None)`; bridge `wordTimes`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_word_timings.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio import edge_tts_engine as e


def test_parse_word_srt(tmp_path):
    srt = tmp_path / "v.srt"
    srt.write_text(
        "1\n00:00:00,100 --> 00:00:00,500\nThe\n\n"
        "2\n00:00:00,500 --> 00:00:01,000\nunexamined\n\n",
        encoding="utf-8",
    )
    words = e.parse_word_srt(srt)
    assert words == [
        {"w": "The", "start": 0.1, "end": 0.5},
        {"w": "unexamined", "start": 0.5, "end": 1.0},
    ]


def test_parse_word_srt_missing_returns_empty(tmp_path):
    assert e.parse_word_srt(tmp_path / "nope.srt") == []
```

Add to `tests/test_remotion_reel.py`:

```python
def test_bridge_includes_wordtimes(tmp_path):
    p = tmp_path / "reel-data.json"
    hw = [{"w": "Hi", "start": 0.0, "end": 0.3}]
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p, hook_words=hw)
    data = json.loads(p.read_text())
    assert data["wordTimes"]["hook"] == hw
    assert data["wordTimes"]["quote"] == [] and data["wordTimes"]["cta"] == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_word_timings.py tests/test_remotion_reel.py -k "word" -v`
Expected: FAIL.

- [ ] **Step 3: Add the SRT parser + subtitles flag**

In `src/audio/edge_tts_engine.py`, add:

```python
def _srt_ts(s: str) -> float:
    s = s.strip().replace(",", ".")
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def parse_word_srt(path: Path) -> list[dict]:
    """Parse an edge-tts word-boundary SRT into [{w,start,end}] (seconds). []
    if the file is missing or unparseable."""
    path = Path(path)
    if not path.exists():
        return []
    words: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    i = 0
    while i < len(lines):
        if "-->" in lines[i]:
            try:
                a, b = lines[i].split("-->")
                text = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if text:
                    words.append({"w": text, "start": _srt_ts(a), "end": _srt_ts(b)})
                i += 2
                continue
            except Exception:
                pass
        i += 1
    return words
```

In `generate_scene_voiceover_edge_tts`, change the command to also write subtitles — replace the `subprocess.run([... "--write-media", str(output_path)], ...)` command list with:

```python
        result = subprocess.run(
            ["edge-tts", "--voice", voice, "--text", text,
             "--write-media", str(output_path),
             "--write-subtitles", str(Path(output_path).with_suffix(".srt"))],
            capture_output=True, text=True, timeout=60,
        )
```

- [ ] **Step 4: Return word lists from `prepare_reel_voiceover_edge_tts`**

In `prepare_reel_voiceover_edge_tts`, change the `return {...}` to include parsed words:

```python
    return {
        "hook_voice": hook_path if hook_ok else None,
        "quote_voice": quote_path if quote_ok else None,
        "cta_voice": cta_path if cta_ok else None,
        "hook_words": parse_word_srt(hook_path.with_suffix(".srt")) if hook_ok else [],
        "quote_words": parse_word_srt(quote_path.with_suffix(".srt")) if quote_ok else [],
        "cta_words": parse_word_srt(cta_path.with_suffix(".srt")) if cta_ok else [],
        "voice": voice,
    }
```

- [ ] **Step 5: Thread word lists through the bridge**

In `src/video/remotion_reel.py` `write_bridge_file`, add params after `music_path`:

```python
    hook_words: list | None = None,
    quote_words: list | None = None,
    cta_words: list | None = None,
```

In the payload dict, add:

```python
        "wordTimes": {
            "hook": hook_words or [],
            "quote": quote_words or [],
            "cta": cta_words or [],
        },
```

In `generate_remotion_reel`, add the same three params (after `music_path`) and forward them in its `write_bridge_file(...)` call:

```python
        hook_words=hook_words,
        quote_words=quote_words,
        cta_words=cta_words,
```
(add `hook_words: list | None = None, quote_words: list | None = None, cta_words: list | None = None,` to its signature).

- [ ] **Step 6: Capture + pass in `pipeline.py`**

In the `--remotion` branch, where the `vo` dict is read, also capture words:

```python
                    hook_words = vo.get("hook_words") or []
                    quote_words = vo.get("quote_words") or []
                    cta_words = vo.get("cta_words") or []
```
(initialize `hook_words = quote_words = cta_words = []` next to the `hook_voice = ... = None` initializers). Then in the `generate_remotion_reel(...)` call add:

```python
                    hook_words=hook_words,
                    quote_words=quote_words,
                    cta_words=cta_words,
```

- [ ] **Step 7: Run tests + suite**

Run: `.venv/bin/python -m pytest tests/test_word_timings.py tests/test_remotion_reel.py -v` → PASS.
Run: `.venv/bin/python -c "import ast; ast.parse(open('pipeline.py').read()); print('pipeline ok')"` → `pipeline ok`.
Run: `.venv/bin/python -m pytest tests/ -q` → only the 2 pre-existing ffmpeg failures.

- [ ] **Step 8: Commit**

```bash
git add src/audio/edge_tts_engine.py src/video/remotion_reel.py pipeline.py tests/test_word_timings.py tests/test_remotion_reel.py
git commit -m "feat(reel): capture per-word VO timings into the bridge (wordTimes)"
```

---

### Task 6: Karaoke word-highlight in Remotion

**Files:**
- Create: `remotion/src/lib/wordAt.ts`, `remotion/src/lib/wordAt.test.ts`
- Modify: `remotion/src/components/AnimatedQuote.tsx`, `remotion/src/components/AnimatedText.tsx`
- Modify: `remotion/src/components/QuoteScene.tsx`, `remotion/src/components/HookScene.tsx`, `remotion/src/components/CtaScene.tsx`, `remotion/src/PovReel.tsx` (thread `wordTimes`)

**Interfaces:**
- Produces: `WordTime = {w: string; start: number; end: number}`; `wordAt(sceneSeconds, words) -> number` (active-word index, -1 before the first).
- `AnimatedText` + `AnimatedQuote` accept an optional `words?: WordTime[]`; when non-empty they reveal/highlight by word timing, else keep the fixed-stagger behavior.

- [ ] **Step 1: Write the failing test**

Create `remotion/src/lib/wordAt.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { wordAt } from "./wordAt";

const words = [
  { w: "a", start: 0.0, end: 0.3 },
  { w: "b", start: 0.3, end: 0.6 },
  { w: "c", start: 0.6, end: 0.9 },
];

describe("wordAt", () => {
  it("is -1 before the first word", () => expect(wordAt(-0.1, words)).toBe(-1));
  it("returns the active word index", () => expect(wordAt(0.4, words)).toBe(1));
  it("stays on the last word after it ends", () => expect(wordAt(5, words)).toBe(2));
  it("empty words -> -1", () => expect(wordAt(1, [])).toBe(-1));
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd remotion && npm test`
Expected: FAIL — `wordAt` missing.

- [ ] **Step 3: Implement `wordAt`**

Create `remotion/src/lib/wordAt.ts`:

```ts
export interface WordTime {
  w: string;
  start: number;
  end: number;
}

/** Index of the word active at `sceneSeconds` (seconds from scene start); the
 *  last-started word after it ends; -1 before the first word or when empty. */
export function wordAt(sceneSeconds: number, words: WordTime[]): number {
  let idx = -1;
  for (let i = 0; i < words.length; i++) {
    if (sceneSeconds >= words[i].start) idx = i;
    else break;
  }
  return idx;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd remotion && npm test`
Expected: PASS.

- [ ] **Step 5: Word-timed reveal in `AnimatedQuote`**

In `remotion/src/components/AnimatedQuote.tsx`: import `wordAt, WordTime` from `../lib/wordAt`; add `words?: WordTime[]` to `AnimatedQuoteProps` and destructure `words = []`. Replace the per-word `const wordStart = startFrame + i * staggerFrames;` line with a word-timing-aware start:

```tsx
          const wordStart =
            words.length > i
              ? Math.round(words[i].start * fps)
              : startFrame + i * staggerFrames;
```

And make the active spoken word the emphasis: after computing `enter`/`scale`, compute the active index once (above the `.map`, using the component `frame`):

```tsx
  const activeWord = wordAt(frame / fps, words);
```
and change the emphasis test used for color/punch from `i === emphasis` to `i === (activeWord >= 0 ? activeWord : emphasis)` so the currently-spoken word gets the accent highlight (falls back to the heuristic emphasis when there are no word times).

- [ ] **Step 6: Word-timed reveal in `AnimatedText` (hook/cta)**

In `remotion/src/components/AnimatedText.tsx`: import `wordAt, WordTime`; add `words?: WordTime[]` to `AnimatedTextProps` and destructure `words = []`. Where it computes each word's `wordStart` (the `startFrame + i * staggerFrames` expression), apply the same word-timing override:

```tsx
        const wordStart =
          words.length > i
            ? Math.round(words[i].start * fps)
            : startFrame + i * staggerFrames;
```

If `AnimatedText` also has an emphasis/highlight concept, highlight `wordAt(frame/fps, words)` when `words` is non-empty; otherwise leave its current styling unchanged.

- [ ] **Step 7: Thread `wordTimes` through scenes + PovReel**

- `PovReel.tsx`: add `wordTimes?: { hook?: WordTime[]; quote?: WordTime[]; cta?: WordTime[] }` to `PovReelProps` (+ `wordTimes: {}` default), destructure `wordTimes = {}`. Pass `words={wordTimes.hook}` to `HookScene`, `words={wordTimes.quote}` to `QuoteScene`, `words={wordTimes.cta}` to `CtaScene`.
- `QuoteScene.tsx`: add `words?: WordTime[]` prop; pass it to `AnimatedQuote`.
- `HookScene.tsx` / `CtaScene.tsx`: add `words?: WordTime[]` prop; pass it to their `AnimatedText` (CtaScene: if it renders text without `AnimatedText`, pass `words` into the same word-start override it uses; otherwise thread to `AnimatedText`).

Import `WordTime` where needed. Type-check: `cd remotion && npx tsc --noEmit` → only the 2 pre-existing `Root.tsx` errors, nothing new.

- [ ] **Step 8: Run all Remotion tests + smoke**

Run: `cd remotion && npm test` → all pass (wordAt + prior).
Run a smoke still with word times in the bridge:
```bash
cd remotion
cat > public/reel-data.json <<'JSON'
{"hook":"Purpose finds you","quote":"The unexamined life is not worth living","attribution":"— Socrates","cta":"Save this","mood":"dark_philosophical","duration":10.5,"fps":30,"beats":[4.0,5.2],"voices":{},"voiceDurations":{},"wordTimes":{"hook":[],"quote":[{"w":"The","start":0.0,"end":0.3},{"w":"unexamined","start":0.3,"end":0.9}],"cta":[]}}
JSON
npx remotion still src/index.ts PovReel out/karaoke.png --frame=140 --props=public/reel-data.json --log=error
```
Expected: `out/karaoke.png` written; the active quote word is accent-highlighted, grade + vignette visible. Revert `public/reel-data.json` afterward: `git checkout -- public/reel-data.json`.

- [ ] **Step 9: Commit**

```bash
git add remotion/src/lib/wordAt.ts remotion/src/lib/wordAt.test.ts remotion/src/components/AnimatedQuote.tsx remotion/src/components/AnimatedText.tsx remotion/src/components/QuoteScene.tsx remotion/src/components/HookScene.tsx remotion/src/components/CtaScene.tsx remotion/src/PovReel.tsx
git commit -m "feat(remotion): karaoke word-highlight driven by VO word timings"
```

---

## Self-Review

**Spec coverage:**
- §4.0 edge-tts in requirements → Task 1. ✓
- §4.1 per-mood grade (theme + ColorGrade + wrap) → Task 2. ✓
- §4.2 camera zoom + beat kick → Task 3. ✓
- §4.3 SFX synth + bridge + playback → Task 4. ✓
- §4.4 word timings (subtitles + parser + return + generate/bridge params + pipeline) → Task 5. ✓
- §4.5 karaoke (`wordAt` + AnimatedQuote/AnimatedText retime + scene/PovReel threading) → Task 6. ✓
- §7 testing (parser, bridge sfx/wordTimes, getGrade, cameraScale, wordAt, smoke) → Tasks 1-6. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. Task 6 Step 7's CtaScene note gives a concrete conditional (thread to AnimatedText, or apply the same override) — not a placeholder.

**Type consistency:** `WordTime{w,start,end}` identical in `wordAt.ts` (TS) and the Python `{"w","start","end"}` dict (Task 5) and bridge `wordTimes`. `getGrade`/`Grade`, `cameraScale`, `_synth_sfx`, `parse_word_srt`/`_srt_ts` names consistent across def/test/use. `generate_remotion_reel`/`write_bridge_file` gain `hook_words`/`quote_words`/`cta_words` in Task 5 (both signatures) and pipeline passes them. `sfx`/`wordTimes`/`grade` bridge keys match the Remotion props. ✓

**Ordering:** low-risk first (1 req → 2 grade → 3 zoom → 4 sfx → 5 word-timings → 6 karaoke). Task 6 consumes Task 5's `wordTimes`; Task 4's `beatFrames` reuse the Task 3 computation. ✓
