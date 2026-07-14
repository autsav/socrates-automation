# FLUX-Backed Remotion Reel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reels render as Remotion animated text over a fal.ai (FLUX) photo background, prompted smartly from the quote + trending topic + mood, narrated in the edge-tts sage voice — and this becomes the only reel renderer.

**Architecture:** Generate the FLUX photo in Python (`PromptArchitect` → `generate_background`), pass its path through the existing `reel-data.json` bridge, and add a `<BackgroundPhoto>` layer to the Remotion composition. Reels always route to `_run_pov_reel`; the ffmpeg `generate_reel` + OpenAI-TTS reel path is removed from the reel flow (edge-tts ffmpeg POV remains as the Node-unavailable fallback).

**Tech Stack:** Python 3.11, Remotion (React/TypeScript), fal.ai FLUX, edge-tts, SQLite. Run via `.venv/bin/python`.

## Global Constraints

- Python 3.11 venv: `.venv/bin/python`.
- **Never crash a reel:** FLUX generation is best-effort — any failure → `background=None` → particle/gradient bg; the reel still renders with the sage voice.
- **No payload regression:** a bridge file written without a `background` must be byte-for-byte identical to today's (no `background` key), so existing reels/tests are unaffected.
- edge-tts sage voice only on the reel path — never OpenAI TTS.
- `data/pipeline.db` is git-tracked and must contain no Meta token; `git checkout -- data/pipeline.db` before committing after a run.
- Remotion assets live under `remotion/public/`; the composition reads `reel-data.json` there.

---

### Task 1: PromptArchitect accepts a trend topic

**Files:**
- Modify: `src/prompts/architect.py` (`build`, ~line 98)
- Test: `tests/test_prompt_architect_trend.py`

**Interfaces:**
- Produces: `PromptArchitect.build(quote, mood, base_prompt="", style="mixed", season="", seed=0, trend_topic="") -> str` — when `trend_topic` is non-empty, the returned prompt includes a subject clause evoking it; unchanged when empty.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prompt_architect_trend.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.prompts.architect import PromptArchitect


def test_trend_topic_appears_in_prompt():
    p = PromptArchitect().build(quote="Know thyself.", mood="dark_philosophical",
                                trend_topic="World Cup final", seed=1)
    assert "World Cup" in p


def test_no_trend_topic_unchanged():
    a = PromptArchitect().build(quote="Know thyself.", mood="dark_philosophical", seed=1)
    b = PromptArchitect().build(quote="Know thyself.", mood="dark_philosophical",
                                trend_topic="", seed=1)
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_prompt_architect_trend.py -q`
Expected: FAIL (`build() got an unexpected keyword argument 'trend_topic'`).

- [ ] **Step 3: Implement**

In `src/prompts/architect.py`, add `trend_topic: str = ""` to `build`'s signature (after `seed`). Near where the subject/quote metaphor is assembled into the final prompt string, prepend a trend clause when present. Find the `return` that assembles the prompt and insert before it:

```python
        # Weave a trending-topic subject in when supplied (mood still drives style).
        if trend_topic:
            prompt = f"a cinematic scene evoking {trend_topic}, {prompt}"
```

(Place this so `prompt` is the fully-built string being returned. If `build` returns a joined list, insert the clause as the first subject element instead.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_prompt_architect_trend.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/prompts/architect.py tests/test_prompt_architect_trend.py
git commit -m "feat(reel): PromptArchitect weaves trend topic into FLUX subject"
```

---

### Task 2: `write_bridge_file` accepts a background image

**Files:**
- Modify: `src/video/remotion_reel.py` (`write_bridge_file`, `generate_remotion_reel`)
- Test: `tests/test_remotion_reel_background.py`

**Interfaces:**
- Consumes: existing `_copy_audio` helper (copies a file next to the bridge; despite the name it works for any file).
- Produces: `write_bridge_file(..., background: Path | None = None)` — when `background` exists, copies it next to the bridge as `bg<ext>` and sets `payload["background"] = "bg<ext>"`; when `None`, no `background` key. `generate_remotion_reel(..., background: Path | None = None)` threads it through.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_remotion_reel_background.py
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.video import remotion_reel


def _bridge(tmp_path):
    return tmp_path / "public" / "reel-data.json"


def test_background_included_when_given(tmp_path):
    bg = tmp_path / "bg.jpg"
    bg.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    out = remotion_reel.write_bridge_file(
        hook="h", quote="q", attribution="a", cta="c", mood="dark_philosophical",
        duration=8.0, fps=30, bridge_path=_bridge(tmp_path), background=bg)
    payload = json.loads(Path(out).read_text())
    assert payload["background"] == "bg.jpg"
    assert (Path(out).parent / "bg.jpg").exists()


def test_background_omitted_when_none(tmp_path):
    out = remotion_reel.write_bridge_file(
        hook="h", quote="q", attribution="a", cta="c", mood="dark_philosophical",
        duration=8.0, fps=30, bridge_path=_bridge(tmp_path), background=None)
    payload = json.loads(Path(out).read_text())
    assert "background" not in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel_background.py -q`
Expected: FAIL (`write_bridge_file() got an unexpected keyword argument 'background'`).

- [ ] **Step 3: Implement**

In `write_bridge_file`, add `background: Path | None = None` to the signature (alongside the other optional params). After the `music_name` block and before assembling `payload`, add:

```python
    bg_name: str | None = None
    if background and Path(background).exists():
        bp = Path(background)
        bg_name = _copy_audio(bp, f"bg{bp.suffix}")   # _copy_audio copies any file
```

Then, where optional keys are conditionally added to `payload` (near `if music_name: payload["music"] = music_name`), add:

```python
    if bg_name:
        payload["background"] = bg_name
```

In `generate_remotion_reel`, add `background: Path | None = None` to its signature and pass `background=background` in its call to `write_bridge_file`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel_background.py tests/test_remotion_reel.py -q`
Expected: PASS (new tests pass; existing remotion_reel tests unaffected — no `background` key when not given).

- [ ] **Step 5: Commit**

```bash
git add src/video/remotion_reel.py tests/test_remotion_reel_background.py
git commit -m "feat(reel): reel-data.json carries an optional FLUX background image"
```

---

### Task 3: Remotion `<BackgroundPhoto>` layer

**Files:**
- Create: `remotion/src/components/BackgroundPhoto.tsx`
- Modify: `remotion/src/PovReel.tsx`
- Test: `tests/test_remotion_background_prop.py` (payload-level; visual confirmed by live render in Task 6)

**Interfaces:**
- Consumes: the `background` prop from `reel-data.json` (Remotion passes JSON props to the composition).
- Produces: `PovReel` renders `<BackgroundPhoto src={background}>` (full-bleed Img + Ken-Burns + scrim) as the base layer when `background` is set; otherwise the existing gradient/particle base. Particle field + text render on top in both cases.

- [ ] **Step 1: Write the failing test** (payload contract the component depends on)

```python
# tests/test_remotion_background_prop.py
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.video import remotion_reel


def test_defaultprops_and_payload_agree_on_background_key(tmp_path):
    bg = tmp_path / "bg.jpg"; bg.write_bytes(b"\xff\xd8\xffx")
    out = remotion_reel.write_bridge_file(
        hook="h", quote="q", attribution="a", cta="c", mood="dark_philosophical",
        duration=8.0, fps=30, bridge_path=tmp_path / "public" / "reel-data.json", background=bg)
    payload = json.loads(Path(out).read_text())
    # The Remotion component reads props.background; the key must be exactly "background".
    assert payload.get("background") == "bg.jpg"
```

- [ ] **Step 2: Run test to verify it fails/passes**

Run: `.venv/bin/python -m pytest tests/test_remotion_background_prop.py -q`
Expected: PASS if Task 2 is done (this pins the contract the .tsx relies on). If it fails, fix Task 2 first.

- [ ] **Step 3: Implement the component**

Create `remotion/src/components/BackgroundPhoto.tsx`:

```tsx
import { AbsoluteFill, Img, staticFile, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export const BackgroundPhoto: React.FC<{ src: string }> = ({ src }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // Slow Ken-Burns zoom across the whole reel.
  const scale = interpolate(frame, [0, durationInFrames], [1.06, 1.14], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%", height: "100%", objectFit: "cover",
          transform: `scale(${scale})`, transformOrigin: "center",
        }}
      />
      {/* Bottom-weighted dark scrim so the animated text stays legible. */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.25) 0%, rgba(0,0,0,0.55) 55%, rgba(0,0,0,0.8) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
```

- [ ] **Step 4: Wire it into `PovReel.tsx`**

In `remotion/src/PovReel.tsx`: import the component, add `background` to the props type and `povReelDefaultProps` (`background: undefined`), and at the base of the render stack (where `GradientBg`/`PulsingBg` render, ~line 133-136) branch:

```tsx
import { BackgroundPhoto } from "./components/BackgroundPhoto";
// ...in props type:
  background?: string;
// ...in povReelDefaultProps:
  background: undefined,
// ...at the base layer, replacing/guarding the existing gradient base:
  {background ? <BackgroundPhoto src={background} /> : (
    /* existing GradientBg / PulsingBg base layer, unchanged */
  )}
```

Keep the particle field and text layers exactly as they are, rendered after the base.

- [ ] **Step 5: Type-check + payload test**

Run: `cd remotion && npx tsc --noEmit 2>&1 | tail -5` (expect no new errors), then
`cd .. && .venv/bin/python -m pytest tests/test_remotion_background_prop.py -q` → PASS.

- [ ] **Step 6: Commit**

```bash
git add remotion/src/components/BackgroundPhoto.tsx remotion/src/PovReel.tsx tests/test_remotion_background_prop.py
git commit -m "feat(reel): Remotion BackgroundPhoto layer (FLUX img + Ken-Burns + scrim)"
```

---

### Task 4: `_run_pov_reel` generates + passes the FLUX background

**Files:**
- Modify: `pipeline.py` (`_run_pov_reel`, ~line 623-710; `_apply_trend_scout`, ~line 560)
- Test: `tests/test_run_pov_reel_background.py`

**Interfaces:**
- Consumes: `PromptArchitect.build(..., trend_topic=...)` (Task 1), `generate_background(mood, api_key, output_dir, quote, prompt_override, ...)`, `generate_remotion_reel(..., background=...)` (Task 2).
- Produces: `_run_pov_reel` best-effort builds a FLUX bg and passes `background=<path>` to `generate_remotion_reel`; on any FLUX failure passes `background=None`. `_apply_trend_scout` stashes `quote_data["trend_topic"]` when it sets a trending hook.

- [ ] **Step 1: Write the failing test** (isolated helper, not the whole pipeline)

Add a small extractable helper so the FLUX step is unit-testable. In `pipeline.py`, add:

```python
def _reel_background(cfg, quote_data, mood):
    """Best-effort FLUX background for a Remotion reel. Returns a Path or None."""
    try:
        prompt = PromptArchitect().build(
            quote=quote_data.get("quote", ""), mood=mood,
            trend_topic=quote_data.get("trend_topic", ""))
        from src.visual.image_generator import generate_background
        path, _seed = generate_background(
            mood=mood, api_key=cfg.FAL_API_KEY, output_dir=str(OUTPUT_DIR),
            quote=quote_data.get("quote", ""), prompt_override=prompt)
        return path
    except Exception as e:
        log.warning(f"  [reel] FLUX background unavailable ({e}) — particle bg")
        return None
```

Test:

```python
# tests/test_run_pov_reel_background.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pipeline


class _Cfg:
    FAL_API_KEY = "k"


def test_reel_background_returns_path_on_success(monkeypatch, tmp_path):
    img = tmp_path / "bg.jpg"; img.write_bytes(b"x")
    monkeypatch.setattr("src.visual.image_generator.generate_background",
                        lambda **k: (img, 7))
    out = pipeline._reel_background(_Cfg(), {"quote": "Q", "trend_topic": "World Cup"}, "dark_philosophical")
    assert out == img


def test_reel_background_none_on_failure(monkeypatch):
    def boom(**k):
        raise RuntimeError("fal down")
    monkeypatch.setattr("src.visual.image_generator.generate_background", boom)
    assert pipeline._reel_background(_Cfg(), {"quote": "Q"}, "dark_philosophical") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_run_pov_reel_background.py -q`
Expected: FAIL (`module 'pipeline' has no attribute '_reel_background'`).

- [ ] **Step 3: Implement**

Add `_reel_background` (above) near `_run_pov_reel`. Inside `_run_pov_reel`, before the `generate_remotion_reel(...)` call (pipeline.py ~703), compute the bg and pass it:

```python
        bg_path = _reel_background(cfg, quote_data, mood)
        # ... existing generate_remotion_reel(...) call, add the kwarg:
                background=bg_path,
```

In `_apply_trend_scout` (where it sets `quote_data["hook"]`/`["bridge"]` from `th`), also set:

```python
                quote_data["trend_topic"] = th.topic
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_run_pov_reel_background.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git checkout -- data/pipeline.db 2>/dev/null || true
git add pipeline.py tests/test_run_pov_reel_background.py
git commit -m "feat(reel): _run_pov_reel generates + passes a FLUX background; trend topic wired"
```

---

### Task 5: Route all reels to the Remotion path; retire the ffmpeg/OpenAI reel path

**Files:**
- Modify: `pipeline.py` (`run_pipeline` reel branch, ~line 905-1155)
- Modify: `.github/workflows/daily_post.yml` (reel commands)
- Test: `tests/test_reel_routing.py`

**Interfaces:**
- Consumes: `_run_pov_reel`.
- Produces: when the pipeline output is a reel, `run_pipeline` calls `_run_pov_reel` (Remotion+FLUX), never `generate_reel`/`generate_enhanced_voiceover`. The Node-unavailable fallback inside `_run_pov_reel` (ffmpeg `generate_pov_reel` with edge-tts) is preserved.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reel_routing.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pipeline


def test_reel_invocation_uses_pov_reel_not_ffmpeg(monkeypatch):
    calls = {"pov": 0, "ffmpeg_reel": 0, "openai_vo": 0}
    monkeypatch.setattr(pipeline, "_run_pov_reel",
                        lambda *a, **k: (calls.__setitem__("pov", calls["pov"] + 1) or "done"))
    monkeypatch.setattr(pipeline, "generate_reel",
                        lambda *a, **k: calls.__setitem__("ffmpeg_reel", calls["ffmpeg_reel"] + 1))
    monkeypatch.setattr(pipeline, "generate_enhanced_voiceover",
                        lambda *a, **k: calls.__setitem__("openai_vo", calls["openai_vo"] + 1))
    # Neutralize network/DB side-effects up to the reel branch.
    monkeypatch.setattr(pipeline, "init_db", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "get_valid_token_with_fallback", lambda *a, **k: "tok")
    monkeypatch.setattr(pipeline, "has_posted_today", lambda *a, **k: False)
    # A studio/manual reel run (previously the buggy path) must now take POV.
    try:
        pipeline.run_pipeline(dry_run=True, studio=False, manual=True, reel=True)
    except SystemExit:
        pass
    assert calls["pov"] >= 1
    assert calls["ffmpeg_reel"] == 0 and calls["openai_vo"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reel_routing.py -q`
Expected: FAIL (ffmpeg/openai called, or pov not called) — proving the bug.

- [ ] **Step 3: Implement**

In `run_pipeline`, make the reel branch route to `_run_pov_reel`. At the top of the function (after `if remotion: pov = True`, ~line 834) add:

```python
    # All reels render via Remotion+FLUX (edge-tts). The ffmpeg generate_reel +
    # OpenAI-TTS path is retired for reels; POV falls back to ffmpeg+edge-tts only
    # if Node/Remotion is unavailable.
    if reel and not carousel:
        pov = True
```

This makes the existing `if pov:` branch (line 905) handle all reels via `_run_pov_reel`. Remove/guard the now-dead FLUX reel branch (the `generate_enhanced_voiceover` + `generate_reel` block, ~1103-1155) so it is unreachable for reels — leave it only under a non-reel condition if it also serves images, else delete it. Verify by reading the branch conditions that images/carousels are unaffected.

`daily_post.yml`: change the two reel commands for clarity/robustness:

```yaml
-            python pipeline.py --studio --manual
+            python pipeline.py --studio --manual --remotion
```
(both the `workflow_dispatch` and scheduled `else` reel lines).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_reel_routing.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git checkout -- data/pipeline.db 2>/dev/null || true
git add pipeline.py .github/workflows/daily_post.yml tests/test_reel_routing.py
git commit -m "fix(reel): route all reels to Remotion+edge-tts; retire ffmpeg/OpenAI reel path"
```

---

### Task 6: Safety allows sports + live end-to-end verification

**Files:**
- Test: `tests/test_trend_safety_sports.py`
- Modify (only if the test fails): `src/content/trend_sources.py` denylist

**Interfaces:**
- Consumes: `src.content.trend_sources.is_unsafe`.

- [ ] **Step 1: Write the test**

```python
# tests/test_trend_safety_sports.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.content.trend_sources import is_unsafe


def test_sports_topics_allowed():
    for t in ["World Cup final", "football transfer news", "Olympic gold medal"]:
        assert is_unsafe(t) is False, t


def test_unsafe_topics_rejected():
    for t in ["war casualties", "fatal crash", "shooting victims"]:
        assert is_unsafe(t) is True, t
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/test_trend_safety_sports.py -q`
Expected: PASS. If a sports term is wrongly rejected, narrow the offending denylist term in `trend_sources.py` (e.g. ensure "goal"/"shot"/"kill" football senses aren't over-matched) and re-run.

- [ ] **Step 3: Full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 4: Live render + eyeball**

Run: `.venv/bin/python pipeline.py --remotion --dry-run 2>&1 | tee logs/flux_reel_verify.log`
Then confirm from the log + output MP4:
- a FLUX background was generated (a `reel-data.json` `background` key / an `output/*.jpg`),
- the render used Remotion (`[remotion] Rendering Reel`),
- the VO used the sage voice (`en-US-AndrewNeural`),
- extract a frame (`ffmpeg -ss 4 -i output/reel_XXX.mp4 -frames:v 1 /tmp/f.png`) and verify the photo background shows behind the text.
Revert the DB: `git checkout -- data/pipeline.db`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_trend_safety_sports.py src/content/trend_sources.py
git commit -m "test(reel): sports trend topics pass the safety gate; live FLUX reel verified"
```

---

## Self-review notes

- Spec §4.1–4.6 each map to a task (4.4 PromptArchitect→T1, 4.2 bridge→T2, 4.1 PovReel→T3, 4.3 _run_pov_reel→T4, 4.5 routing→T5, 4.6 safety→T6).
- Every step has real code; no placeholders.
- Signatures verified against source: `generate_background(mood, api_key, output_dir, quote, prompt_override, seed)`, `PromptArchitect.build(quote, mood, base_prompt, style, season, seed)`, `generate_remotion_reel(...)`, `generate_pov_reel(...)`.
- "Never crash a reel" honored: FLUX and Node both have fallbacks that keep the sage voice.
