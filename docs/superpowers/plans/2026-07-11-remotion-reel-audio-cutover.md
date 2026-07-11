# Narrated Remotion Reel + Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Narrate the Remotion reel (hook/quote/cta VO over a ducked music bed, loudness-normalized) and make it the production reel via a CI cutover, with the ffmpeg-POV fallback preserved.

**Architecture:** Task 1 reworks the JSON bridge to carry three VO tracks + a music track + per-scene VO durations. Task 2 adds a best-effort ffmpeg `loudnorm` finishing pass. Task 3 plays per-scene VO and a duck-volume music bed in Remotion. Task 4 wires the pipeline to produce the VO + music. Task 5 flips the CI workflow to `--remotion`.

**Tech Stack:** Python 3.11 (repo `.venv`), Remotion 4 / React / TS, vitest, ffmpeg/ffprobe, edge-tts.

## Global Constraints

- **Run Python tests with the 3.11 venv:** `.venv/bin/python -m pytest …` (system python is 3.9).
- **Graceful fallback is sacred:** `generate_remotion_reel` MUST still return `None` (never raise) on any failure → `pipeline.py` falls back to `generate_pov_reel`. Every audio copy / probe / loudnorm step is best-effort and must never break the render.
- **Bridge schema (new):** replace the old single `audio` key with `voices: {hook,quote,cta}` (basenames or null), `music` (basename or null, omitted when null), `voiceDurations: {hook,quote,cta}` (seconds or null). Keep `beats` (detected from the quote voice).
- **Audio files** are copied next to the bridge (`remotion/public/` in production) as `vo-hook<ext>` / `vo-quote<ext>` / `vo-cta<ext>` / `music<ext>`.
- **loudnorm target:** `loudnorm=I=-14:TP=-1.5:LRA=11` (exact).
- **Duck gains:** base ≈ `0.32`, ducked ≈ `0.12`, ramp ≈ `6` frames (exact defaults).
- Do NOT re-commit `data/pipeline.db`. 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures are unrelated.
- **Branch:** `feat/remotion-reel-audio-cutover` (already checked out).

---

### Task 1: Bridge carries 3 VO tracks + music + durations

**Files:**
- Modify: `src/video/remotion_reel.py` (`write_bridge_file`, `_probe_duration`, `generate_remotion_reel` signature)
- Test: `tests/test_remotion_reel.py` (replace the voiceover/audio tests)

**Interfaces:**
- Produces: `write_bridge_file(hook, quote, attribution, cta, mood, duration, fps, bridge_path=BRIDGE_FILE, hook_voice=None, quote_voice=None, cta_voice=None, music_path=None) -> Path`; `_probe_duration(path) -> float | None`; `generate_remotion_reel(..., hook_voice=None, quote_voice=None, cta_voice=None, music_path=None) -> Path | None` (the old `voiceover_path` param is removed).

- [ ] **Step 1: Replace the failing tests**

In `tests/test_remotion_reel.py`, DELETE these existing tests (they assert the old `voiceover_path`/`audio` schema): `test_write_bridge_file_no_voiceover_has_empty_beats_no_audio`, `test_write_bridge_file_with_voiceover_adds_beats_and_copies_audio`, `test_write_bridge_file_beat_detection_failure_degrades_to_empty`, `test_write_bridge_file_copy_failure_degrades_to_empty`, `test_generate_forwards_voiceover_path_to_bridge`. Also update `test_write_bridge_file_roundtrip` (see Step 5 note). Then ADD:

```python
def test_bridge_no_audio_has_empty_voices_no_music(tmp_path):
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p)
    data = json.loads(p.read_text())
    assert data["voices"] == {"hook": None, "quote": None, "cta": None}
    assert data["voiceDurations"] == {"hook": None, "quote": None, "cta": None}
    assert data["beats"] == []
    assert "music" not in data


def test_bridge_three_voices_and_music_copied(tmp_path, monkeypatch):
    monkeypatch.setattr(rr.beat_sync, "detect_beats", lambda path, **k: [0.4, 1.1])
    monkeypatch.setattr(rr, "_probe_duration", lambda path: 2.5)
    files = {}
    for key in ("hook", "quote", "cta", "music"):
        f = tmp_path / f"{key}.wav"
        f.write_bytes(b"RIFFfake")
        files[key] = f
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file(
        "h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p,
        hook_voice=files["hook"], quote_voice=files["quote"],
        cta_voice=files["cta"], music_path=files["music"],
    )
    data = json.loads(p.read_text())
    assert data["voices"] == {"hook": "vo-hook.wav", "quote": "vo-quote.wav", "cta": "vo-cta.wav"}
    assert data["music"] == "music.wav"
    assert data["voiceDurations"] == {"hook": 2.5, "quote": 2.5, "cta": 2.5}
    assert data["beats"] == [0.4, 1.1]
    for name in ("vo-hook.wav", "vo-quote.wav", "vo-cta.wav", "music.wav"):
        assert (tmp_path / name).read_bytes() == b"RIFFfake"


def test_bridge_copy_failure_degrades(tmp_path, monkeypatch):
    def boom(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(rr.shutil, "copy", boom)
    vo = tmp_path / "q.wav"
    vo.write_bytes(b"x")
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p, quote_voice=vo)
    data = json.loads(p.read_text())
    assert data["voices"]["quote"] is None
    assert "music" not in data


def test_generate_forwards_voices_to_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "remotion_available", lambda: True)
    seen = {}

    def fake_write(*a, **k):
        seen.update(k)
        pth = tmp_path / "reel-data.json"
        pth.write_text("{}")
        return pth

    class _Ok:
        returncode = 0
        stderr = ""
        stdout = ""

    out = tmp_path / "reel.mp4"

    def fake_run(*a, **k):
        out.write_bytes(b"mp4")
        return _Ok()

    monkeypatch.setattr(rr, "write_bridge_file", fake_write)
    monkeypatch.setattr(rr.subprocess, "run", fake_run)
    monkeypatch.setattr(rr.shutil, "which", lambda name: None)  # skip loudnorm
    q = tmp_path / "q.wav"; q.write_bytes(b"x")
    rr.generate_remotion_reel(hook="h", quote="q", cta="c", output_path=out, quote_voice=q)
    assert seen.get("quote_voice") == q
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -k "bridge or forwards_voices" -v`
Expected: FAIL — new params/keys/`_probe_duration` don't exist.

- [ ] **Step 3: Add `_probe_duration`**

In `src/video/remotion_reel.py`, add near the top helpers (module already imports `shutil`, `subprocess`, `json`, `Path`):

```python
def _probe_duration(path: Path) -> float | None:
    """Best-effort media duration in seconds via ffprobe; None if unavailable."""
    if not shutil.which("ffprobe"):
        return None
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        s = (r.stdout or "").strip()
        return round(float(s), 3) if r.returncode == 0 and s else None
    except Exception:  # pragma: no cover - defensive
        return None
```

- [ ] **Step 4: Rewrite the voiceover block in `write_bridge_file`**

Change the signature from `..., bridge_path=BRIDGE_FILE, voiceover_path=None)` to:

```python
    bridge_path: Path = BRIDGE_FILE,
    hook_voice: Path | None = None,
    quote_voice: Path | None = None,
    cta_voice: Path | None = None,
    music_path: Path | None = None,
) -> Path:
```

Replace the entire block from `beats: list[float] = []` down to (but not including) `payload = {` with:

```python
    def _copy_audio(src: Path, name: str) -> str | None:
        try:
            bridge_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, bridge_path.parent / name)
            return name
        except Exception as e:  # pragma: no cover - defensive
            print(f"  [remotion] audio copy failed ({e})")
            return None

    voices: dict[str, str | None] = {"hook": None, "quote": None, "cta": None}
    voice_durations: dict[str, float | None] = {"hook": None, "quote": None, "cta": None}
    for key, p in (("hook", hook_voice), ("quote", quote_voice), ("cta", cta_voice)):
        if p and Path(p).exists():
            p = Path(p)
            nm = _copy_audio(p, f"vo-{key}{p.suffix}")
            if nm:
                voices[key] = nm
                voice_durations[key] = _probe_duration(p)

    music_name: str | None = None
    if music_path and Path(music_path).exists():
        mp = Path(music_path)
        music_name = _copy_audio(mp, f"music{mp.suffix}")

    beats: list[float] = []
    if quote_voice and Path(quote_voice).exists():
        try:
            beats = beat_sync.detect_beats(Path(quote_voice))
        except Exception as e:  # pragma: no cover - defensive
            print(f"  [remotion] beat detection failed ({e}) — reel plays un-synced")
            beats = []
```

- [ ] **Step 5: Update the payload**

Replace the payload block:

```python
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
```

with:

```python
    payload = {
        "hook": hook or "",
        "quote": quote or "",
        "attribution": attribution or "",
        "cta": cta or "",
        "mood": mood,
        "duration": round(float(duration), 3),
        "fps": int(fps),
        "beats": beats,
        "voices": voices,
        "voiceDurations": voice_durations,
    }
    if music_name:
        payload["music"] = music_name
```

Then update `test_write_bridge_file_roundtrip` in the test file: its expected dict must now include `"voices": {"hook": None, "quote": None, "cta": None}` and `"voiceDurations": {"hook": None, "quote": None, "cta": None}` alongside `"beats": []` (and still no `"music"`/`"audio"` keys).

- [ ] **Step 6: Update `generate_remotion_reel` signature + bridge call**

Change its param `voiceover_path: Path | None = None,` to:

```python
    hook_voice: Path | None = None,
    quote_voice: Path | None = None,
    cta_voice: Path | None = None,
    music_path: Path | None = None,
```

And change the `write_bridge_file(...)` call inside it — replace `voiceover_path=voiceover_path,` with:

```python
        hook_voice=hook_voice,
        quote_voice=quote_voice,
        cta_voice=cta_voice,
        music_path=music_path,
```

- [ ] **Step 7: Run tests**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -v`
Expected: PASS (all, including the updated roundtrip test).

- [ ] **Step 8: Commit**

```bash
git add src/video/remotion_reel.py tests/test_remotion_reel.py
git commit -m "feat(remotion): bridge carries 3 VO tracks + music + voiceDurations"
```

---

### Task 2: Loudness-normalize finishing pass

**Files:**
- Modify: `src/video/remotion_reel.py` (`_loudnorm`, call it after a successful render)
- Test: `tests/test_remotion_reel.py`

**Interfaces:**
- Produces: `_loudnorm(path: Path, timeout: int = 120) -> None` (best-effort, never raises).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_remotion_reel.py`:

```python
def test_loudnorm_invokes_ffmpeg_with_filter(tmp_path, monkeypatch):
    src = tmp_path / "reel.mp4"
    src.write_bytes(b"origvideo")
    calls = {}

    def fake_run(cmd, **k):
        calls["cmd"] = cmd
        (tmp_path / "reel.norm.mp4").write_bytes(b"normvideo")

        class _R:
            returncode = 0
            stdout = ""
            stderr = ""
        return _R()

    monkeypatch.setattr(rr.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(rr.subprocess, "run", fake_run)
    rr._loudnorm(src)
    assert "loudnorm=I=-14:TP=-1.5:LRA=11" in calls["cmd"]
    assert src.read_bytes() == b"normvideo"  # replaced in place


def test_loudnorm_skips_without_ffmpeg(tmp_path, monkeypatch):
    src = tmp_path / "reel.mp4"
    src.write_bytes(b"orig")
    monkeypatch.setattr(rr.shutil, "which", lambda name: None)

    def boom(*a, **k):
        raise AssertionError("ffmpeg must not be called")
    monkeypatch.setattr(rr.subprocess, "run", boom)
    rr._loudnorm(src)
    assert src.read_bytes() == b"orig"  # untouched
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -k loudnorm -v`
Expected: FAIL — `_loudnorm` missing.

- [ ] **Step 3: Implement `_loudnorm`**

In `src/video/remotion_reel.py`, add:

```python
def _loudnorm(path: Path, timeout: int = 120) -> None:
    """Best-effort EBU R128 loudness normalization to a social target.

    Replaces `path` in place with a normalized copy. Never raises; if ffmpeg is
    absent or fails, the original render is kept.
    """
    if not shutil.which("ffmpeg"):
        return
    tmp = path.with_suffix(".norm.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", str(path),
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "copy", str(tmp),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(path)
        else:
            tmp.unlink(missing_ok=True)
    except Exception as e:  # pragma: no cover - defensive
        print(f"  [remotion] loudnorm skipped ({e})")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
```

- [ ] **Step 4: Call it after a successful render**

In `generate_remotion_reel`, immediately before the final `return output_path` (after the `size = output_path.stat().st_size` / "Saved" print), add:

```python
    _loudnorm(output_path)
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/video/remotion_reel.py tests/test_remotion_reel.py
git commit -m "feat(remotion): loudnorm finishing pass on rendered reel"
```

---

### Task 3: Remotion per-scene VO + ducked music bed

**Files:**
- Create: `remotion/src/lib/duckVolume.ts`, `remotion/src/lib/duckVolume.test.ts`
- Modify: `remotion/src/PovReel.tsx` (props + audio), `remotion/src/Root.tsx` (default props)

**Interfaces:**
- Produces: `duckVolume(frame, spans, opts?) -> number` with `DuckSpan = {start:number; end:number}` (frames).
- `PovReelProps` gains `voices?: {hook?: string; quote?: string; cta?: string}`, `music?: string`, `voiceDurations?: {hook?: number; quote?: number; cta?: number}`; the old `audio` prop is removed.

- [ ] **Step 1: Write the failing test**

Create `remotion/src/lib/duckVolume.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { duckVolume } from "./duckVolume";

const spans = [{ start: 30, end: 90 }];

describe("duckVolume", () => {
  it("returns the ducked gain inside a VO span", () => {
    expect(duckVolume(60, spans)).toBeCloseTo(0.12, 5);
  });

  it("returns the base gain far outside any span", () => {
    expect(duckVolume(200, spans)).toBeCloseTo(0.32, 5);
  });

  it("ramps down before a span starts", () => {
    const v = duckVolume(27, spans); // 3 frames into a 6-frame pre-ramp
    expect(v).toBeLessThan(0.32);
    expect(v).toBeGreaterThan(0.12);
  });

  it("handles no spans (always base)", () => {
    expect(duckVolume(50, [])).toBeCloseTo(0.32, 5);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd remotion && npm test`
Expected: FAIL — `./duckVolume` missing.

- [ ] **Step 3: Implement `duckVolume`**

Create `remotion/src/lib/duckVolume.ts`:

```ts
export interface DuckSpan {
  start: number; // frame
  end: number; // frame
}

/**
 * Music-bed gain at `frame`: `base` outside VO spans, `duck` inside, with a
 * linear `ramp`-frame edge on each side of every span. Overlapping effects take
 * the lowest gain.
 */
export function duckVolume(
  frame: number,
  spans: DuckSpan[],
  opts?: { base?: number; duck?: number; ramp?: number }
): number {
  const base = opts?.base ?? 0.32;
  const duck = opts?.duck ?? 0.12;
  const ramp = opts?.ramp ?? 6;
  let v = base;
  for (const s of spans) {
    if (frame >= s.start && frame <= s.end) return duck;
    if (frame >= s.start - ramp && frame < s.start) {
      const t = (frame - (s.start - ramp)) / ramp; // 0..1
      v = Math.min(v, base + (duck - base) * t);
    }
    if (frame > s.end && frame <= s.end + ramp) {
      const t = (frame - s.end) / ramp; // 0..1
      v = Math.min(v, duck + (base - duck) * t);
    }
  }
  return v;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd remotion && npm test`
Expected: PASS (4 duckVolume tests + the existing emphasis tests).

- [ ] **Step 5: Rework `PovReel.tsx` props + audio**

In `remotion/src/PovReel.tsx`:

Update `PovReelProps` — remove `audio?: string;` and add:

```ts
  voices?: { hook?: string; quote?: string; cta?: string };
  music?: string;
  voiceDurations?: { hook?: number; quote?: number; cta?: number };
```

Update `povReelDefaultProps` — remove `audio: undefined,` and add:

```ts
  voices: {},
  music: undefined,
  voiceDurations: {},
```

Add the import at the top:

```ts
import { duckVolume, DuckSpan } from "./lib/duckVolume";
```

In the component signature destructure, replace `audio,` with `voices = {}, music, voiceDurations = {},`.

Inside the component (after `const quoteEnd = hookF + quoteF;`), build the duck spans:

```tsx
  const spanFor = (start: number, dur: number | undefined, sceneLen: number): DuckSpan => ({
    start,
    end: start + (dur != null ? Math.round(dur * fps) : sceneLen),
  });
  const duckSpans: DuckSpan[] = [
    spanFor(0, voiceDurations.hook, hookF),
    spanFor(hookF, voiceDurations.quote, quoteF),
    spanFor(quoteEnd, voiceDurations.cta, durationInFrames - quoteEnd),
  ];
```

Replace the old `{audio ? (<Sequence ...QuoteAudio...><Audio src={staticFile(audio)} /></Sequence>) : null}` block with per-scene VO + the music bed:

```tsx
      {voices.hook ? (
        <Sequence from={0} durationInFrames={hookF} name="HookVO">
          <Audio src={staticFile(voices.hook)} />
        </Sequence>
      ) : null}
      {voices.quote ? (
        <Sequence from={hookF} durationInFrames={quoteF} name="QuoteVO">
          <Audio src={staticFile(voices.quote)} />
        </Sequence>
      ) : null}
      {voices.cta ? (
        <Sequence from={quoteEnd} durationInFrames={durationInFrames - quoteEnd} name="CtaVO">
          <Audio src={staticFile(voices.cta)} />
        </Sequence>
      ) : null}
      {music ? (
        <Audio src={staticFile(music)} volume={(f: number) => duckVolume(f, duckSpans)} />
      ) : null}
```

- [ ] **Step 6: Type-check**

Run: `cd remotion && npx tsc --noEmit`
Expected: only the 2 pre-existing `Root.tsx` errors (Composition generics) — no new errors from `PovReel.tsx`/`duckVolume.ts`. If `Root.tsx`'s `povReelDefaultProps` reference errors on the removed `audio`, that's expected to be fixed here since `povReelDefaultProps` lives in `PovReel.tsx` (you already updated it) — confirm `Root.tsx` still compiles to the same 2 pre-existing errors and nothing new.

- [ ] **Step 7: Commit**

```bash
git add remotion/src/lib/duckVolume.ts remotion/src/lib/duckVolume.test.ts remotion/src/PovReel.tsx remotion/src/Root.tsx
git commit -m "feat(remotion): per-scene VO + duck-volume music bed"
```

---

### Task 4: Pipeline produces 3 VO + music for the Remotion path

**Files:**
- Modify: `pipeline.py` (the `if use_remotion:` branch, ~lines 457–495)

**Interfaces:**
- Consumes: `generate_remotion_reel(..., hook_voice, quote_voice, cta_voice, music_path)` (Task 1); `prepare_reel_voiceover_edge_tts(...) -> {hook_voice, quote_voice, cta_voice}`; `download_music_for_mood(mood) -> Path | None`.

- [ ] **Step 1: Read the branch**

Run: `sed -n '457,500p' pipeline.py` — confirm the `if use_remotion:` block currently extracts only `reel_voiceover_path = vo.get("quote_voice")` and calls `generate_remotion_reel(..., voiceover_path=reel_voiceover_path)`.

- [ ] **Step 2: Capture all three voices + music**

Replace the voiceover-extraction block (the `reel_voiceover_path = None` try/except that ends at `reel_voiceover_path = vo.get("quote_voice")`) with:

```python
        # Produce full VO (hook/quote/cta) + a music bed for the narrated
        # Remotion reel. Best-effort: any failure → that piece is simply absent
        # (the reel still renders; the ffmpeg fallback below makes zero TTS calls).
        hook_voice = quote_voice = cta_voice = music_path = None
        try:
            if edge_tts_available():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                vo = prepare_reel_voiceover_edge_tts(
                    hook_text=hook_text,
                    quote_text=quote_data["quote"],
                    cta_text=cta_text,
                    mood=mood,
                    output_dir=OUTPUT_DIR,
                    timestamp=ts,
                )
                if isinstance(vo, dict):
                    hook_voice = vo.get("hook_voice")
                    quote_voice = vo.get("quote_voice")
                    cta_voice = vo.get("cta_voice")
        except Exception as e:
            log.warning(f"  [remotion] reel voiceover unavailable ({e}) — silent reel")
        try:
            from src.audio.trending_audio import download_music_for_mood
            music_path = download_music_for_mood(mood)
        except Exception as e:
            log.warning(f"  [remotion] music bed unavailable ({e}) — VO-only reel")
```

- [ ] **Step 3: Pass them into the render call**

In the `generate_remotion_reel(...)` call, replace `voiceover_path=reel_voiceover_path,` with:

```python
                    hook_voice=hook_voice,
                    quote_voice=quote_voice,
                    cta_voice=cta_voice,
                    music_path=music_path,
```

- [ ] **Step 4: Verify pipeline + suite**

Run: `.venv/bin/python -c "import ast; ast.parse(open('pipeline.py').read()); print('pipeline ok')"`
Expected: `pipeline ok`

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: only the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures; no new failures.

- [ ] **Step 5: Commit**

```bash
git add pipeline.py
git commit -m "feat(pipeline): produce hook/quote/cta VO + music for the Remotion reel"
```

---

### Task 5: CI cutover — Remotion becomes the production reel

**Files:**
- Modify: `.github/workflows/daily_post.yml`
- Test: `tests/test_workflow_reliability.py` (add cutover assertions)

**Interfaces:** none (CI). Depends on Tasks 1–4 so `--remotion` produces a narrated reel.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_workflow_reliability.py`:

```python
def test_daily_post_uses_remotion_for_pov():
    t = _read(".github/workflows/daily_post.yml")
    assert "python pipeline.py --manual --remotion" in t
    assert "actions/setup-node" in t
    assert "npm --prefix remotion ci" in t
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_workflow_reliability.py::test_daily_post_uses_remotion_for_pov -v`
Expected: FAIL.

- [ ] **Step 3: Add Node + Remotion deps to the workflow**

In `.github/workflows/daily_post.yml`, immediately after the existing Python setup step (before "Init/migrate SQLite database"), add:

```yaml
      - name: Set up Node (for Remotion render)
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install Remotion deps
        run: npm --prefix remotion ci
```

- [ ] **Step 4: Switch the POV slot to Remotion**

In the "Run pipeline" step's script, change:

```bash
          elif [ "${{ steps.format.outputs.mode }}" = "pov" ]; then
            echo "🎬 POV Reel (zero-cost, ffmpeg + Pillow) → Telegram for manual upload"
            python pipeline.py --manual --pov
```

to:

```bash
          elif [ "${{ steps.format.outputs.mode }}" = "pov" ]; then
            echo "🎬 POV Reel (Remotion, narrated; auto-falls back to ffmpeg POV) → Telegram for manual upload"
            python pipeline.py --manual --remotion
```

- [ ] **Step 5: Run the test**

Run: `.venv/bin/python -m pytest tests/test_workflow_reliability.py -v`
Expected: PASS (all, including the existing reliability tests).

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/daily_post.yml tests/test_workflow_reliability.py
git commit -m "feat(ci): render the production POV reel with Remotion (ffmpeg fallback)"
```

---

## Self-Review

**Spec coverage:**
- §4.1 cutover (workflow `--remotion` + setup-node + npm ci; pipeline fallback intact) → Task 5 + Task 4. ✓
- §4.2 three VO + bridge `voices`/`voiceDurations` + `generate_remotion_reel` params → Task 1. ✓
- §4.3 music resolution (`download_music_for_mood`) → Task 4. ✓
- §4.4 Remotion per-scene VO + music duck (`duckVolume`, spans from `voiceDurations`) → Task 3. ✓
- §4.5 loudnorm finishing pass → Task 2. ✓
- §6 error handling: copy/probe/loudnorm best-effort + fallback → Tasks 1,2,4 (guards) + preserved in generate_remotion_reel. ✓
- §7 testing: bridge, loudnorm, duckVolume, workflow → Tasks 1,2,3,5 tests. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. Task 4 Step 1 / Task 1 Step 1 include a read/delete instruction with concrete named targets, not placeholders.

**Type consistency:** `write_bridge_file(..., hook_voice, quote_voice, cta_voice, music_path)` and `generate_remotion_reel(..., hook_voice, quote_voice, cta_voice, music_path)` match across Task 1 (def) and Task 4 (call). Bridge keys `voices`/`voiceDurations`/`music` identical across Task 1 (Python) and Task 3 (`PovReelProps`). `duckVolume(frame, spans, opts?)` + `DuckSpan{start,end}` identical across Task 3 impl/test/usage. `_probe_duration`/`_loudnorm` names consistent. The old `voiceover_path` param and `audio` bridge key are fully removed (Task 1) and no later task references them. ✓

**Ordering:** Task 1 (bridge+generate params) → Task 4 (pipeline caller) so the caller matches the new signature; Task 3 (Remotion) consumes the Task 1 bridge schema; Task 5 (CI) last so the narrated reel exists before cutover. ✓
