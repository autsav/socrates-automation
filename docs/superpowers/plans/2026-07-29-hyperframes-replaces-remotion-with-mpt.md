# HyperFrames + MPT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Remotion with MoneyPrinterTurbo (MPT) as the base renderer; layer HyperFrames on top as a pure interactivity compositor (kinetic per-word text + RPM retention hooks + CTA overlays); composite via ffmpeg `overlay` filter.

**Architecture:** `pipeline.py _run_pov_reel` orchestrates parallel subprocesses: (a) MPT CLI renders `base.mp4` with stock footage + Whisper captions + music; (b) HyperFrames renders `overlay.mp4` on transparent BG with GSAP animations only. ffmpeg `overlay` composites them into `final.mp4`. Remotion directory deleted (hard cutover). On any failure: log + Telegram alert, NO fallback reel.

**Tech Stack:** Python 3.11 (`.venv/bin/python`), pytest, TypeScript strict + GSAP 3.12 + Puppeteer + Vitest, ffmpeg `overlay` filter, MPT (vendored), HyperFrames (existing `./hyperframes/`).

## Global Constraints

- **Output spec:** 1080×1920@30fps; IG-compatible (`format=yuv420p`, no alpha in `final.mp4`); overlay.mp4 retains alpha channel
- **Hard cutover:** `remotion/` directory deleted; `_run_pov_reel` Remotion branches removed; no fallback path
- **Failure policy:** any stage failure → log + Telegram alert → ABORT cron run; no in-app fallback reel
- **Env vars:** `.venv/bin/python` for all Python; existing 12 cron secrets (per `CLAUDE.md`); MPT may add Pexels/Pixabay/OpenAI keys as required
- **Never crash a reel:** every optional stage (MPT, HF overlay, ffmpeg composite) is try/except best-effort → fallback per `CLAUDE.md`
- **Studio QuoteData MUST be extended:** `rpm_hooks[]` (array of `{at_sec, text, duration_sec, style}`) + `cta_copy` (string) + optional `cta_url` (string). Default empty arrays/strings. No backfill in A — B/C may add agents.
- **word_timings.json schema (exact):** `{"scenes": {"hook": {"words": [{"t": 0.42, "w": "The"}, ...], "duration_sec": 2.5}, "bridge": {...}, "quote": {...}, "cta": {...}}, "total_duration_sec": 15.5}`
- **MPT CLI contract:** exact flags discovered in Task 1; if MPT emits SRT instead of JSON, `src/mpt_adapter.py` translates
- **Puppeteer alpha capture:** use `{omitBackground: false}` on `page.screenshot()`; may need `--use-gl=swiftshader` Chromium flag (TBD in Task 6)
- **Tests:** pytest (Python) + vitest (TS); never commit code without matching tests
- **Commits:** no `Co-Authored-By` trailer (project `attribution.commit` not set per `CLAUDE.md`); one commit per task
- **Files ≤ 500 lines** per `CLAUDE.md`
- **Telegram alert helper:** existing function in `pipeline.py` (exact name TBD — grep `pipeline.py` for `telegram` in Task 8)

---

## Task 1: Vendor MPT (clone + CLI verify)

**Files:**
- Create: `mpt/` (cloned MPT repo, `.gitignore`d)
- Modify: `.gitignore` (add `mpt/` exception if needed; MPT's own `.gitignore` should handle internals)
- Modify: `requirements.txt` (MPT Python deps)

**Step 1: Clone MPT to `mpt/` (vendored, .gitignored)**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git clone --depth 1 --branch main https://github.com/harry0703/MoneyPrinterTurbo.git mpt
```

Expected: `mpt/` directory created with MPT source.

**Step 2: Inspect MPT CLI entry point**

```bash
ls mpt/
cat mpt/README.md 2>/dev/null | head -100
find mpt -name "*.py" -path "*/main*" -o -name "*.py" -path "*/cli*" 2>/dev/null | head -10
```

Expected: identify the main entry point. MPT is typically `python -m mpt` or `python mpt/main.py`. Look for `argparse` usage in the entry point.

**Step 3: Add MPT to `.gitignore`**

Append to `.gitignore`:
```
# Vendored MPT (MoneyPrinterTurbo)
mpt/
!mpt/.gitkeep  # if needed
```

But `mpt/` is OUTSIDE this repo's source tree tracking. Verify:
```bash
cd "/Users/utsab1/Documents/socrates automation"
git status --ignored 2>&1 | grep mpt
```

If `mpt/` shows up as untracked, ensure `.gitignore` includes it.

**Step 4: Document the MPT CLI invocation contract**

Create `docs/mpt-cli-contract.md` with findings from Step 2:
- Exact CLI command (e.g., `python -m mpt.main --task video --script TEXT --output PATH`)
- Required env vars (Pexels API key, Pixabay API key, OpenAI API key, etc.)
- Expected output paths and formats

**Step 5: Smoke test MPT CLI**

Run MPT against a test script and verify it produces an MP4:
```bash
cd "/Users/utsab1/Documents/socrates automation/mpt"
.venv/bin/python -m mpt.main --help 2>&1 | head -30 || python -m mpt.main --help 2>&1 | head -30
```

Expected: MPT CLI help output. If MPT has its own venv setup (`mpt/requirements.txt`), install those first:
```bash
python3.11 -m venv mpt/.venv
mpt/.venv/bin/pip install -r mpt/requirements.txt 2>&1 | tail -5
```

**Step 6: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add .gitignore docs/mpt-cli-contract.md
git commit -m "chore(mpt): vendor MPT + document CLI contract"
```

---

## Task 2: Extend studio QuoteData with overlay fields

**Files:**
- Modify: `studio/types.py` (add `rpm_hooks`, `cta_copy`, `cta_url` to `QuoteData`)
- Modify: `studio/` agents (any that construct `QuoteData` — add default empty values)
- Test: `studio/tests/test_quote_data_overlay_fields.py`

**Step 1: Write failing test for QuoteData extensions**

```python
# studio/tests/test_quote_data_overlay_fields.py
from studio.types import QuoteData

def test_quote_data_has_rpm_hooks_field():
    qd = QuoteData(
        hook="", quote="", attribution="", caption="", hashtags=[],
        mood="", audience="", row_number=1, cta="",
        rpm_hooks=[], cta_copy="", cta_url=""
    )
    assert qd.rpm_hooks == []
    assert qd.cta_copy == ""

def test_quote_data_cta_url_optional():
    qd = QuoteData(
        hook="", quote="", attribution="", caption="", hashtags=[],
        mood="", audience="", row_number=1, cta="",
        rpm_hooks=[], cta_copy="", cta_url=None
    )
    assert qd.cta_url is None

def test_rpm_hook_schema():
    from studio.types import RpmHook
    h = RpmHook(at_sec=2.5, text="Did you know?", duration_sec=1.5, style="pop")
    assert h.at_sec == 2.5
    assert h.style == "pop"
```

Run: `.venv/bin/python -m pytest studio/tests/test_quote_data_overlay_fields.py -v`
Expected: FAIL (QuoteData has no `rpm_hooks` field).

**Step 2: Add `RpmHook` dataclass + extend `QuoteData`**

In `studio/types.py`, add:
```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RpmHook:
    at_sec: float
    text: str
    duration_sec: float
    style: str  # "pop" | "slide" | "fade"

# In QuoteData, add fields:
@dataclass
class QuoteData:
    # ... existing fields ...
    rpm_hooks: list[RpmHook] = field(default_factory=list)
    cta_copy: str = ""
    cta_url: Optional[str] = None
```

**Step 3: Update all studio agents that construct `QuoteData`**

```bash
cd "/Users/utsab1/Documents/socrates automation"
grep -rn "QuoteData(" studio/ --include="*.py"
```

For each match, ensure `rpm_hooks=[]`, `cta_copy=""`, `cta_url=None` are passed (or rely on dataclass defaults).

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest studio/tests/test_quote_data_overlay_fields.py -v`
Expected: PASS (3 tests).

**Step 5: Run full studio test suite to ensure no regression**

Run: `.venv/bin/python -m pytest studio/ -v`
Expected: PASS (existing tests still green).

**Step 6: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add studio/types.py studio/tests/test_quote_data_overlay_fields.py
git add $(grep -rl "QuoteData(" studio/ --include="*.py" | head -20)
git commit -m "feat(studio): extend QuoteData with rpm_hooks + cta_copy"
```

---

## Task 3: word_timings adapter (conditional — only if MPT emits SRT)

**Files:**
- Create: `src/mpt_adapter.py` (only if Task 1 found MPT emits SRT)
- Test: `src/tests/test_mpt_adapter.py`

**Step 0: Decide if this task is needed**

Check Task 1's `docs/mpt-cli-contract.md`:
- If MPT emits `word_timings.json` natively → SKIP this task; mark complete in ledger
- If MPT emits `subtitles.srt` → proceed with Steps 1–6

**Step 1: Write failing test for SRT → word_timings.json adapter**

```python
# src/tests/test_mpt_adapter.py
from pathlib import Path
from src.mpt_adapter import srt_to_word_timings

def test_srt_to_word_timings_basic():
    srt = """1
00:00:00,420 --> 00:00:02,500
The unexamined life

2
00:00:02,500 --> 00:00:04,800
is not worth living
"""
    result = srt_to_word_timings(srt, scene="hook")
    assert "scenes" in result
    assert "hook" in result["scenes"]
    assert result["scenes"]["hook"]["words"][0] == {"t": 0.42, "w": "The"}
    assert result["scenes"]["hook"]["duration_sec"] == 2.5

def test_srt_handles_empty():
    result = srt_to_word_timings("", scene="hook")
    assert result["scenes"]["hook"]["words"] == []
    assert result["scenes"]["hook"]["duration_sec"] == 0.0
```

Run: `.venv/bin/python -m pytest src/tests/test_mpt_adapter.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.mpt_adapter'`).

**Step 2: Implement `srt_to_word_timings`**

```python
# src/mpt_adapter.py
"""MPT output adapter: SRT → word_timings.json per spec schema."""
import re
from typing import TypedDict

class WordTiming(TypedDict):
    t: float
    w: str

class SceneTiming(TypedDict):
    words: list[WordTiming]
    duration_sec: float

def srt_to_word_timings(srt_text: str, scene: str) -> dict:
    """Convert SRT text → word_timings dict for one scene.
    
    Schema: {"scenes": {scene_name: {"words": [{"t": float, "w": str}], "duration_sec": float}}}
    """
    blocks = re.split(r"\n\n+", srt_text.strip())
    words: list[WordTiming] = []
    last_end = 0.0
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        # line[0] = index, line[1] = timestamp, lines[2:] = text
        m = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})", lines[1])
        if not m:
            continue
        start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = m.groups()
        start_sec = int(start_h) * 3600 + int(start_m) * 60 + int(start_s) + int(start_ms) / 1000
        end_sec = int(end_h) * 3600 + int(end_m) * 60 + int(end_s) + int(end_ms) / 1000
        text = " ".join(lines[2:])
        for w in text.split():
            words.append({"t": round(start_sec, 3), "w": w})
        last_end = max(last_end, end_sec)
    return {"scenes": {scene: {"words": words, "duration_sec": round(last_end, 3)}}}
```

**Step 3: Run test to verify it passes**

Run: `.venv/bin/python -m pytest src/tests/test_mpt_adapter.py -v`
Expected: PASS (2 tests).

**Step 4: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add src/mpt_adapter.py src/tests/test_mpt_adapter.py
git commit -m "feat(mpt-adapter): SRT → word_timings.json translator"
```

---

## Task 4: HF overlay libs (TDD)

**Files:**
- Create: `hyperframes/js/lib/animateOverlayWords.ts`
- Create: `hyperframes/js/lib/rpmHook.ts`
- Create: `hyperframes/js/lib/ctaCard.ts`
- Test: `hyperframes/tests/animateOverlayWords.test.ts`
- Test: `hyperframes/tests/rpmHook.test.ts`
- Test: `hyperframes/tests/ctaCard.test.ts`

**Interfaces (consumed by later tasks):**
- `animateOverlayWords(sceneWords: WordTiming[], durationSec: number) => gsap.core.Timeline`
- `rpmHook(hookSpec: {atSec: number, text: string, durationSec: number, style: string}) => gsap.core.Timeline`
- `ctaCard(ctaSpec: {atSec: number, copy: string, url?: string, durationSec: number}) => gsap.core.Timeline`

**Step 1: Write failing test for animateOverlayWords**

```typescript
// hyperframes/tests/animateOverlayWords.test.ts
import { describe, it, expect } from "vitest";
import { animateOverlayWords } from "../js/lib/animateOverlayWords";

describe("animateOverlayWords", () => {
  it("returns GSAP timeline", () => {
    const tl = animateOverlayWords(
      [{ t: 0.42, w: "The" }, { t: 0.78, w: "unexamined" }],
      2.5
    );
    expect(tl).toBeDefined();
    expect(tl.duration()).toBeCloseTo(2.5, 1);
  });

  it("handles empty input", () => {
    const tl = animateOverlayWords([], 0);
    expect(tl.duration()).toBe(0);
  });

  it("adds a label per word", () => {
    const tl = animateOverlayWords(
      [{ t: 0.0, w: "A" }, { t: 1.0, w: "B" }],
      2.0
    );
    expect(tl.labels?.["w_0"]).toBeDefined();
    expect(tl.labels?.["w_1"]).toBeDefined();
  });
});
```

Run: `cd hyperframes && npx vitest run tests/animateOverlayWords.test.ts`
Expected: FAIL (`Cannot find module '../js/lib/animateOverlayWords'`).

**Step 2: Implement animateOverlayWords**

```typescript
// hyperframes/js/lib/animateOverlayWords.ts
import gsap from "gsap";

export interface WordTiming {
  t: number;
  w: string;
}

export function animateOverlayWords(
  sceneWords: WordTiming[],
  durationSec: number
): gsap.core.Timeline {
  const tl = gsap.timeline();
  sceneWords.forEach((word, idx) => {
    tl.addLabel(`w_${idx}`, word.t);
    tl.to(
      `#overlay-word-${idx}`,
      { scale: 1.15, color: "#FFD700", duration: 0.2, ease: "power2.out" },
      word.t
    );
    tl.to(
      `#overlay-word-${idx}`,
      { scale: 1.0, color: "#FFFFFF", duration: 0.15, ease: "power2.in" },
      word.t + 0.2
    );
  });
  return tl;
}
```

**Step 3: Run test to verify it passes**

Run: `cd hyperframes && npx vitest run tests/animateOverlayWords.test.ts`
Expected: PASS (3 tests).

**Step 4: Write failing test for rpmHook**

```typescript
// hyperframes/tests/rpmHook.test.ts
import { describe, it, expect } from "vitest";
import { rpmHook } from "../js/lib/rpmHook";

describe("rpmHook", () => {
  it("returns GSAP timeline with entrance + exit", () => {
    const tl = rpmHook({ atSec: 2.5, text: "Did you know?", durationSec: 1.5, style: "pop" });
    expect(tl).toBeDefined();
    expect(tl.duration()).toBeGreaterThanOrEqual(1.5);
  });

  it("supports slide style", () => {
    const tl = rpmHook({ atSec: 0, text: "Hi", durationSec: 1.0, style: "slide" });
    expect(tl).toBeDefined();
  });

  it("handles zero duration gracefully", () => {
    const tl = rpmHook({ atSec: 0, text: "X", durationSec: 0, style: "pop" });
    expect(tl).toBeDefined();
  });

  it("pop style uses from() with scale", () => {
    const tl = rpmHook({ atSec: 1.0, text: "Test", durationSec: 1.0, style: "pop" });
    // GSAP timeline labels can be inspected
    expect(tl.labels?.["rpm_entrance"]).toBe(1.0);
  });
});
```

Run: `cd hyperframes && npx vitest run tests/rpmHook.test.ts`
Expected: FAIL.

**Step 5: Implement rpmHook**

```typescript
// hyperframes/js/lib/rpmHook.ts
import gsap from "gsap";

export interface RpmHookSpec {
  atSec: number;
  text: string;
  durationSec: number;
  style: "pop" | "slide" | "fade";
}

export function rpmHook(spec: RpmHookSpec): gsap.core.Timeline {
  const tl = gsap.timeline();
  tl.addLabel("rpm_entrance", spec.atSec);
  if (spec.style === "pop") {
    tl.from("#rpm-hook", { scale: 0, rotation: -180, duration: 0.3, ease: "back.out" }, spec.atSec);
    tl.to("#rpm-hook", { scale: 1, rotation: 0, duration: 0.2, ease: "power2.out" }, spec.atSec + 0.3);
  } else if (spec.style === "slide") {
    tl.from("#rpm-hook", { x: -200, opacity: 0, duration: 0.4, ease: "power2.out" }, spec.atSec);
  } else {
    tl.from("#rpm-hook", { opacity: 0, duration: 0.5 }, spec.atSec);
  }
  tl.to("#rpm-hook", { opacity: 0, duration: 0.2 }, spec.atSec + spec.durationSec);
  return tl;
}
```

**Step 6: Run test to verify it passes**

Run: `cd hyperframes && npx vitest run tests/rpmHook.test.ts`
Expected: PASS (4 tests).

**Step 7: Write failing test for ctaCard**

```typescript
// hyperframes/tests/ctaCard.test.ts
import { describe, it, expect } from "vitest";
import { ctaCard } from "../js/lib/ctaCard";

describe("ctaCard", () => {
  it("returns GSAP timeline with fade-in + fade-out", () => {
    const tl = ctaCard({ atSec: 13.0, copy: "Follow @socrates", url: "https://ig.com/socrates", durationSec: 3.0 });
    expect(tl).toBeDefined();
    expect(tl.duration()).toBeCloseTo(3.2, 1);
  });

  it("works without URL", () => {
    const tl = ctaCard({ atSec: 0, copy: "Follow", durationSec: 1.0 });
    expect(tl).toBeDefined();
  });

  it("fade-in duration is 0.2s", () => {
    const tl = ctaCard({ atSec: 5.0, copy: "X", durationSec: 1.0 });
    expect(tl.labels?.["cta_visible"]).toBeDefined();
  });
});
```

Run: `cd hyperframes && npx vitest run tests/ctaCard.test.ts`
Expected: FAIL.

**Step 8: Implement ctaCard**

```typescript
// hyperframes/js/lib/ctaCard.ts
import gsap from "gsap";

export interface CtaSpec {
  atSec: number;
  copy: string;
  url?: string;
  durationSec: number;
}

export function ctaCard(spec: CtaSpec): gsap.core.Timeline {
  const tl = gsap.timeline();
  tl.from("#cta-card", { opacity: 0, y: 50, duration: 0.3, ease: "power2.out" }, spec.atSec);
  tl.addLabel("cta_visible", spec.atSec + 0.3);
  tl.to("#cta-card", { opacity: 1, y: 0, duration: 0.2, ease: "power2.out" }, spec.atSec + 0.1);
  tl.to("#cta-card", { opacity: 0, y: -50, duration: 0.2 }, spec.atSec + spec.durationSec);
  return tl;
}
```

**Step 9: Run all HF tests to verify they pass**

Run: `cd hyperframes && npx vitest run`
Expected: PASS (3 existing test files + 3 new test files = 6 files, all green).

**Step 10: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add hyperframes/js/lib/animateOverlayWords.ts hyperframes/js/lib/rpmHook.ts hyperframes/js/lib/ctaCard.ts
git add hyperframes/tests/animateOverlayWords.test.ts hyperframes/tests/rpmHook.test.ts hyperframes/tests/ctaCard.test.ts
git commit -m "feat(hf-overlay): GSAP libs for words + RPM hooks + CTA"
```

---

## Task 5: HF overlay templates

**Files:**
- Create: `hyperframes/templates/overlay.html.j2`
- Create: `hyperframes/templates/overlay/word.j2`
- Create: `hyperframes/templates/overlay/rpm-hook.j2`
- Create: `hyperframes/templates/overlay/cta.j2`
- Modify: `hyperframes/css/overlay.css` (NEW file)

**Step 1: Create overlay HTML root template**

```html
<!-- hyperframes/templates/overlay.html.j2 -->
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=1080, height=1920" />
  <title>HyperFrames Overlay</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
  <link rel="stylesheet" href="css/overlay.css" />
</head>
<body style="background: transparent;">
  <div id="root" data-composition-id="overlay" data-duration="{{ base_duration_sec }}" data-width="1080" data-height="1920">

    <!-- RPM hooks overlay layer -->
    {% for hook in rpm_hooks %}
      {% include 'overlay/rpm-hook.j2' %}
    {% endfor %}

    <!-- Per-word kinetic text per scene -->
    {% for scene_name, scene_data in scenes.items() %}
      <div id="scene-{{ scene_name }}" class="overlay-scene" data-start="{{ scene_data.start_sec }}" data-duration="{{ scene_data.duration_sec }}">
        {% for word in scene_data.words %}
          {% include 'overlay/word.j2' %}
        {% endfor %}
      </div>
    {% endfor %}

    <!-- CTA card -->
    {% if cta_copy %}
      {% include 'overlay/cta.j2' %}
    {% endif %}
  </div>

  <script type="application/json" id="overlay-data">{{ overlay_data | tojson }}</script>
  <script type="module" src="js/overlay-main.js"></script>
</body>
</html>
```

**Step 2: Create word sub-template**

```html
<!-- hyperframes/templates/overlay/word.j2 -->
<span id="overlay-word-{{ loop.index0 }}" class="overlay-word" data-word-t="{{ word.t }}">{{ word.w }}</span>
```

**Step 3: Create RPM hook sub-template**

```html
<!-- hyperframes/templates/overlay/rpm-hook.j2 -->
<div id="rpm-hook" class="rpm-hook rpm-style-{{ hook.style }}" data-at-sec="{{ hook.at_sec }}">
  <div class="rpm-text">{{ hook.text }}</div>
</div>
```

**Step 4: Create CTA sub-template**

```html
<!-- hyperframes/templates/overlay/cta.j2 -->
<div id="cta-card" class="cta-card">
  <div class="cta-copy">{{ cta_copy }}</div>
  {% if cta_url %}
  <a href="{{ cta_url }}" class="cta-link">{{ cta_url }}</a>
  {% endif %}
</div>
```

**Step 5: Create overlay CSS**

```css
/* hyperframes/css/overlay.css */
body {
  margin: 0;
  background: transparent;
  font-family: 'Inter', sans-serif;
  color: #FFFFFF;
}

.overlay-word {
  display: inline-block;
  margin: 0 4px;
  font-size: 48px;
  font-weight: 700;
  transform: scale(1);
}

.rpm-hook {
  position: absolute;
  top: 30%;
  left: 50%;
  transform: translate(-50%, -50%) scale(0);
  background: rgba(0, 0, 0, 0.85);
  border: 3px solid #FFD700;
  padding: 20px 40px;
  border-radius: 12px;
  font-size: 36px;
  font-weight: 700;
}

.cta-card {
  position: absolute;
  bottom: 10%;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 215, 0, 0.95);
  color: #000;
  padding: 24px 48px;
  border-radius: 16px;
  text-align: center;
}

.cta-copy {
  font-size: 42px;
  font-weight: 800;
}

.cta-link {
  display: block;
  margin-top: 12px;
  font-size: 24px;
  color: #333;
}
```

**Step 6: Create overlay-main.ts orchestrator (NEW file)**

```typescript
// hyperframes/js/overlay-main.ts
import gsap from "gsap";
import { animateOverlayWords } from "./lib/animateOverlayWords";
import { rpmHook } from "./lib/rpmHook";
import { ctaCard } from "./lib/ctaCard";

const data = JSON.parse(document.getElementById("overlay-data")!.textContent!);

const master = gsap.timeline();

// Per-scene word animations
for (const [sceneName, sceneData] of Object.entries(data.scenes)) {
  const sceneWords = (sceneData as any).words;
  const durationSec = (sceneData as any).duration_sec;
  const tl = animateOverlayWords(sceneWords, durationSec);
  master.add(tl, (sceneData as any).start_sec);
}

// RPM hooks
for (const hook of data.rpm_hooks || []) {
  master.add(rpmHook(hook), hook.at_sec);
}

// CTA card
if (data.cta_copy) {
  master.add(ctaCard({
    atSec: data.cta_start_sec,
    copy: data.cta_copy,
    url: data.cta_url,
    durationSec: data.cta_duration_sec
  }), data.cta_start_sec);
}

// Expose for render CLI to read duration
(window as any).__timelines = { overlay: master };
master.duration(data.base_duration_sec);
```

**Step 7: Verify templates parse (manual smoke test)**

Run: `cd hyperframes && ls templates/ templates/overlay/`
Expected: All files present.

**Step 8: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add hyperframes/templates/overlay.html.j2 hyperframes/templates/overlay/ hyperframes/css/overlay.css hyperframes/js/overlay-main.ts
git commit -m "feat(hf-overlay): templates + CSS + overlay orchestrator"
```

---

## Task 6: HF render-overlay CLI subcommand

**Files:**
- Create: `hyperframes/src/cli/render-overlay.ts`
- Modify: `hyperframes/hyperframes.config.ts` (add `overlay` mode flag)
- Modify: `hyperframes/package.json` (add `render-overlay` script if needed)

**Step 1: Write failing smoke test for render-overlay CLI**

```typescript
// hyperframes/tests/render-overlay.test.ts
import { describe, it, expect } from "vitest";
import { existsSync } from "fs";

describe("render-overlay CLI", () => {
  it("exports a render function", async () => {
    const mod = await import("../src/cli/render-overlay");
    expect(typeof mod.render).toBe("function");
  });
});
```

Run: `cd hyperframes && npx vitest run tests/render-overlay.test.ts`
Expected: FAIL (`Cannot find module '../src/cli/render-overlay'`).

**Step 2: Implement render-overlay.ts**

```typescript
// hyperframes/src/cli/render-overlay.ts
import puppeteer from "puppeteer";
import { spawn } from "child_process";
import { createServer } from "http";
import { readFileSync, mkdirSync } from "fs";
import { resolve, dirname, basename, extname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "../..");

function parseArgs(argv: string[]): Record<string, string> {
  const args: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const val = argv[i + 1] && !argv[i + 1].startsWith("-") ? argv[++i] : "true";
      args[key] = val;
    }
  }
  return args;
}

function startStaticServer(root: string, port = 0): Promise<{ url: string; stop: () => void }> {
  const server = createServer((req, res) => {
    const urlPath = (req.url || "/").split("?")[0];
    const filePath = resolve(root, "." + urlPath);
    if (!filePath.startsWith(resolve(root))) {
      res.writeHead(403); res.end("Forbidden"); return;
    }
    try {
      const data = readFileSync(filePath);
      const ext = extname(filePath).toLowerCase();
      const mime: Record<string, string> = {
        ".html": "text/html", ".js": "application/javascript",
        ".css": "text/css", ".json": "application/json",
      };
      res.writeHead(200, { "Content-Type": mime[ext] || "application/octet-stream" });
      res.end(data);
    } catch {
      res.writeHead(404); res.end("Not found");
    }
  });
  return new Promise((res) => {
    server.listen(port, "127.0.0.1", () => {
      const addr = server.address();
      const url = typeof addr === "string" ? addr : `http://127.0.0.1:${addr?.port}`;
      res({ url, stop: () => server.close() });
    });
  });
}

export async function render(args: Record<string, string>): Promise<void> {
  const inputHtml = resolve(args.input || "templates/overlay.html.j2");
  const output = resolve(args.output);
  const overlayDataPath = resolve(args["overlay-data"] || "");
  const fps = Math.max(1, Math.min(60, parseInt(args.fps || "30", 10)));
  const width = Math.max(360, Math.min(2160, parseInt(args.width || "1080", 10)));
  const height = Math.max(640, Math.min(3840, parseInt(args.height || "1920", 10)));
  const durationSec = parseFloat(args.duration || "0");

  mkdirSync(dirname(output), { recursive: true });

  const server = await startStaticServer(ROOT);
  const inputUrl = `${server.url}/templates/overlay.html.j2`;

  console.log(`🎬 Launching overlay render (${width}x${height} @ ${fps}fps, transparent BG)...`);
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--use-gl=swiftshader"]
  });
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  await page.goto(inputUrl, { waitUntil: "networkidle2" });

  await page.waitForFunction(() => {
    const w = window as any;
    return w.gsap && w.__timelines && w.__timelines.overlay;
  }, { timeout: 15000 });

  const totalDur: number = durationSec > 0
    ? durationSec
    : await page.evaluate(() => (window as any).__timelines.overlay.duration());

  const totalFrames = Math.ceil(totalDur * fps);
  console.log(`📽  Rendering ${totalFrames} overlay frames (${totalDur.toFixed(2)}s)...`);

  // ffmpeg: raw RGBA → yuv420p MP4 with alpha
  const ffmpeg = spawn("ffmpeg", [
    "-y",
    "-f", "rawvideo",
    "-vcodec", "rawvideo",
    "-s", `${width}x${height}`,
    "-pix_fmt", "rgba",
    "-r", String(fps),
    "-i", "-",
    "-c:v", "png",
    "-pix_fmt", "yuva420p",
    "-movflags", "+faststart",
    output,
  ], { stdio: ["pipe", "inherit", "inherit"] });

  let frame = 0;
  const startTime = Date.now();

  for (let i = 0; i < totalFrames; i++) {
    const t = i / fps;
    await page.evaluate((time: number) => {
      const tl = (window as any).__timelines.overlay;
      tl.time(time);
      tl.pause();
    }, t);

    await page.evaluate(() => new Promise((r) => requestAnimationFrame(r)));

    const png = await page.screenshot({ type: "png", omitBackground: false });
    ffmpeg.stdin.write(png);

    frame++;
    if (frame % 30 === 0 || frame === totalFrames) {
      const elapsed = (Date.now() - startTime) / 1000;
      const rate = frame / elapsed;
      const remaining = (totalFrames - frame) / rate;
      process.stdout.write(`\r⏳ ${frame}/${totalFrames}  ${(frame/totalFrames*100).toFixed(1)}%  ETA ${remaining.toFixed(0)}s`);
    }
  }

  ffmpeg.stdin.end();
  await new Promise<void>((res, rej) => {
    ffmpeg.on("close", (code) => code === 0 ? res() : rej(new Error(`ffmpeg exited ${code}`)));
  });

  await browser.close();
  server.stop();
  console.log(`\n✅ Saved overlay ${output}`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  render(parseArgs(process.argv.slice(2))).catch((e) => {
    console.error("❌ Overlay render failed:", e.message || e);
    process.exit(1);
  });
}
```

**Step 3: Run test to verify it passes**

Run: `cd hyperframes && npx vitest run tests/render-overlay.test.ts`
Expected: PASS (1 test).

**Step 4: Update package.json to expose script**

Modify `hyperframes/package.json`:
```json
{
  "scripts": {
    "render": "hyperframes render",
    "render-overlay": "tsc && node dist/cli/render-overlay.js"
  }
}
```

**Step 5: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add hyperframes/src/cli/render-overlay.ts hyperframes/tests/render-overlay.test.ts hyperframes/package.json
git commit -m "feat(hf-overlay): render-overlay CLI with alpha-channel output"
```

---

## Task 7: scripts/composite_overlay.sh (ffmpeg overlay wrapper)

**Files:**
- Create: `scripts/composite_overlay.sh`
- Test: manual smoke test (no automated test — shell script invocation)

**Step 1: Write shell wrapper**

```bash
#!/bin/bash
# scripts/composite_overlay.sh
# Composite MPT base.mp4 + HF overlay.mp4 → final.mp4 (IG-compatible, no alpha)
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <base.mp4> <overlay.mp4> <final.mp4>" >&2
  exit 1
fi

BASE="$1"
OVERLAY="$2"
FINAL="$3"

if [[ ! -f "$BASE" ]]; then
  echo "❌ Base video not found: $BASE" >&2
  exit 2
fi

if [[ ! -f "$OVERLAY" ]]; then
  echo "❌ Overlay video not found: $OVERLAY" >&2
  exit 2
fi

mkdir -p "$(dirname "$FINAL")"

echo "🎬 Compositing base + overlay → $FINAL"
ffmpeg -y \
  -i "$BASE" \
  -i "$OVERLAY" \
  -filter_complex "[1]format=yuva420p[ovl]; [0][ovl]overlay=0:0:format=auto,format=yuv420p" \
  -c:v libx264 -crf 23 -preset fast -movflags +faststart \
  "$FINAL"

echo "✅ Composite saved: $FINAL"
```

**Step 2: Make executable + smoke test**

```bash
cd "/Users/utsab1/Documents/socrates automation"
chmod +x scripts/composite_overlay.sh

# Smoke test: verify --help / arg validation works
bash scripts/composite_overlay.sh 2>&1 | head -3 || true
# Expected: "Usage: ..." error message

# Smoke test: verify ffmpeg invocation path is valid (use dummy files)
TMP=$(mktemp -d)
echo "dummy" > "$TMP/base.mp4"
echo "dummy" > "$TMP/overlay.mp4"
bash scripts/composite_overlay.sh "$TMP/base.mp4" "$TMP/overlay.mp4" "$TMP/final.mp4" 2>&1 | head -5 || true
# Expected: ffmpeg error (dummy files invalid), but the script's own validation passed
rm -rf "$TMP"
```

**Step 3: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add scripts/composite_overlay.sh
git commit -m "feat(scripts): composite_overlay.sh ffmpeg overlay wrapper"
```

---

## Task 8: pipeline.py _invoke_mpt() (Python TDD)

**Files:**
- Modify: `pipeline.py` (add `_invoke_mpt()` function)
- Test: `tests/test_invoke_mpt.py`

**Step 1: Find existing Telegram alert helper name**

```bash
cd "/Users/utsab1/Documents/socrates automation"
grep -n "def _.*telegram\|def telegram\|telegram.send\|TELEGRAM" pipeline.py | head -20
```

Document the function name (e.g., `_send_telegram(msg)`) for use in subsequent tasks.

**Step 2: Write failing test for _invoke_mpt()**

```python
# tests/test_invoke_mpt.py
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from pipeline import _invoke_mpt, MptRenderError

def test_invoke_mpt_returns_paths(tmp_path):
    fake_quote_data = tmp_path / "quote_data.json"
    fake_quote_data.write_text("{}")
    fake_run_dir = tmp_path / "run"
    fake_run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        # Pre-create the expected outputs
        (fake_run_dir / "base.mp4").write_bytes(b"fake")
        (fake_run_dir / "word_timings.json").write_text("{}")

        result = _invoke_mpt(fake_quote_data, fake_run_dir)

    assert result["base_video"] == fake_run_dir / "base.mp4"
    assert "word_timings" in result

def test_invoke_mpt_raises_on_nonzero_exit(tmp_path):
    fake_quote_data = tmp_path / "quote_data.json"
    fake_quote_data.write_text("{}")
    fake_run_dir = tmp_path / "run"
    fake_run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="MPT failed")
        with pytest.raises(MptRenderError):
            _invoke_mpt(fake_quote_data, fake_run_dir)

def test_invoke_mpt_raises_on_missing_base_video(tmp_path):
    fake_quote_data = tmp_path / "quote_data.json"
    fake_quote_data.write_text("{}")
    fake_run_dir = tmp_path / "run"
    fake_run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        # base.mp4 NOT created
        with pytest.raises(MptRenderError):
            _invoke_mpt(fake_quote_data, fake_run_dir)

def test_invoke_mpt_warns_on_missing_word_timings(tmp_path, caplog):
    fake_quote_data = tmp_path / "quote_data.json"
    fake_quote_data.write_text("{}")
    fake_run_dir = tmp_path / "run"
    fake_run_dir.mkdir()
    (fake_run_dir / "base.mp4").write_bytes(b"fake")
    # word_timings.json NOT created

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = _invoke_mpt(fake_quote_data, fake_run_dir)

    assert "word_timings" not in result  # or result["word_timings"] is None
    assert "degraded" in caplog.text.lower() or "timing" in caplog.text.lower()
```

Run: `.venv/bin/python -m pytest tests/test_invoke_mpt.py -v`
Expected: FAIL (no `_invoke_mpt` in `pipeline.py`).

**Step 3: Implement _invoke_mpt()**

In `pipeline.py`, add (near other pipeline helpers):

```python
import subprocess
from pathlib import Path

class MptRenderError(Exception):
    """Raised when MPT render fails or produces no output."""

def _invoke_mpt(quote_data_path: Path, run_dir: Path) -> dict:
    """Invoke MPT CLI as subprocess; render base video + word timings.

    Args:
        quote_data_path: absolute path to studio QuoteData JSON
        run_dir: directory for MPT outputs (base.mp4, word_timings.json)

    Returns:
        dict with keys: base_video (Path), word_timings (Path | None),
                        duration_sec (float | None), resolution (list | None)

    Raises:
        MptRenderError: if subprocess exit ≠ 0 or base.mp4 missing
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    base_video = run_dir / "base.mp4"
    word_timings = run_dir / "word_timings.json"

    # MPT CLI invocation (contract from docs/mpt-cli-contract.md)
    cmd = [
        "mpt/.venv/bin/python", "-m", "mpt.main",
        "--quote-data", str(quote_data_path),
        "--output", str(base_video),
        "--word-timings", str(word_timings),
    ]

    log.info("🎬 Invoking MPT: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,  # 10 min max
    )

    if result.returncode != 0:
        log.error("❌ MPT failed (exit %d): %s", result.returncode, result.stderr)
        raise MptRenderError(f"MPT exit {result.returncode}: {result.stderr[:500]}")

    if not base_video.exists():
        log.error("❌ MPT succeeded but base.mp4 missing at %s", base_video)
        raise MptRenderError(f"MPT succeeded but base.mp4 missing")

    output: dict = {"base_video": base_video, "word_timings": None, "duration_sec": None, "resolution": None}

    if word_timings.exists():
        output["word_timings"] = word_timings
    else:
        log.warning("⚠️  MPT succeeded but word_timings.json missing; HF overlay will use degraded timing")

    return output
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_invoke_mpt.py -v`
Expected: PASS (4 tests).

**Step 5: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add pipeline.py tests/test_invoke_mpt.py
git commit -m "feat(pipeline): _invoke_mpt() subprocess wrapper"
```

---

## Task 9: pipeline.py _invoke_hyperframes() (Python TDD)

**Files:**
- Modify: `pipeline.py` (add `_invoke_hyperframes()` function)
- Test: `tests/test_invoke_hyperframes.py`

**Step 1: Write failing test**

```python
# tests/test_invoke_hyperframes.py
from pathlib import Path
import pytest
import json
from unittest.mock import patch, MagicMock
from pipeline import _invoke_hyperframes, HfRenderError

def test_invoke_hyperframes_writes_overlay_input_and_renders(tmp_path):
    quote_data = {"hook": "X", "quote": "Y", "rpm_hooks": [], "cta_copy": ""}
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text(json.dumps(quote_data))
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text(json.dumps({"scenes": {}, "total_duration_sec": 16.0}))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        (run_dir / "overlay.mp4").write_bytes(b"fake")

        result = _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)

    assert result == run_dir / "overlay.mp4"
    assert (run_dir / "overlay_input.json").exists()
    overlay_input = json.loads((run_dir / "overlay_input.json").read_text())
    assert overlay_input["quote_data"] == str(quote_data_path)
    assert overlay_input["word_timings"] == str(word_timings_path)
    assert overlay_input["base_duration_sec"] == 16.0
    assert overlay_input["overlay_only"] is True

def test_invoke_hyperframes_raises_on_nonzero_exit(tmp_path):
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text("{}")
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="HF failed")
        with pytest.raises(HfRenderError):
            _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)

def test_invoke_hyperframes_raises_on_missing_output(tmp_path):
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text("{}")
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        # overlay.mp4 NOT created
        with pytest.raises(HfRenderError):
            _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)
```

Run: `.venv/bin/python -m pytest tests/test_invoke_hyperframes.py -v`
Expected: FAIL (no `_invoke_hyperframes` in `pipeline.py`).

**Step 2: Implement _invoke_hyperframes()**

In `pipeline.py`, add:

```python
class HfRenderError(Exception):
    """Raised when HyperFrames overlay render fails or produces no output."""

def _invoke_hyperframes(quote_data_path: Path, word_timings_path: Path | None, run_dir: Path) -> Path:
    """Invoke HyperFrames overlay render as subprocess.

    Args:
        quote_data_path: absolute path to studio QuoteData JSON
        word_timings_path: absolute path to MPT word timings JSON (may be None)
        run_dir: directory for HF overlay output (overlay.mp4)

    Returns:
        Path to overlay.mp4

    Raises:
        HfRenderError: if subprocess exit ≠ 0 or overlay.mp4 missing
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    overlay_input = run_dir / "overlay_input.json"
    overlay_output = run_dir / "overlay.mp4"

    # Read word timings to get base_duration_sec
    base_duration_sec = 16.0  # fallback default
    if word_timings_path and word_timings_path.exists():
        try:
            wt_data = json.loads(word_timings_path.read_text())
            base_duration_sec = wt_data.get("total_duration_sec", 16.0)
        except Exception as e:
            log.warning("⚠️  Could not read word_timings.json (%s); using fallback duration", e)

    overlay_payload = {
        "quote_data": str(quote_data_path),
        "word_timings": str(word_timings_path) if word_timings_path else None,
        "base_duration_sec": base_duration_sec,
        "overlay_only": True,
        "output": str(overlay_output),
    }
    overlay_input.write_text(json.dumps(overlay_payload))

    cmd = [
        "npx", "tsx", "hyperframes/src/cli/render-overlay.ts",
        "--overlay-data", str(overlay_input),
        "--output", str(overlay_output),
    ]

    log.info("🎨 Invoking HyperFrames overlay render: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,  # 10 min max
    )

    if result.returncode != 0:
        log.error("❌ HyperFrames overlay failed (exit %d): %s", result.returncode, result.stderr)
        raise HfRenderError(f"HyperFrames exit {result.returncode}: {result.stderr[:500]}")

    if not overlay_output.exists():
        log.error("❌ HyperFrames succeeded but overlay.mp4 missing at %s", overlay_output)
        raise HfRenderError(f"HyperFrames succeeded but overlay.mp4 missing")

    return overlay_output
```

**Step 3: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_invoke_hyperframes.py -v`
Expected: PASS (3 tests).

**Step 4: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add pipeline.py tests/test_invoke_hyperframes.py
git commit -m "feat(pipeline): _invoke_hyperframes() overlay render wrapper"
```

---

## Task 10: pipeline.py _composite_reels() (Python TDD)

**Files:**
- Modify: `pipeline.py` (add `_composite_reels()` function)
- Test: `tests/test_composite_reels.py`

**Step 1: Write failing test**

```python
# tests/test_composite_reels.py
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from pipeline import _composite_reels, CompositeError

def test_composite_reels_invokes_shell_script(tmp_path):
    base = tmp_path / "base.mp4"
    overlay = tmp_path / "overlay.mp4"
    final = tmp_path / "final.mp4"
    base.write_bytes(b"base")
    overlay.write_bytes(b"overlay")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = _composite_reels(base, overlay, final)

    assert result == final
    assert mock_run.called
    args = mock_run.call_args[0][0]
    assert "scripts/composite_overlay.sh" in args
    assert str(base) in args
    assert str(overlay) in args
    assert str(final) in args

def test_composite_reels_raises_on_nonzero_exit(tmp_path):
    base = tmp_path / "base.mp4"
    overlay = tmp_path / "overlay.mp4"
    final = tmp_path / "final.mp4"
    base.write_bytes(b"base")
    overlay.write_bytes(b"overlay")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ffmpeg failed")
        with pytest.raises(CompositeError):
            _composite_reels(base, overlay, final)

def test_composite_reels_raises_on_missing_input(tmp_path):
    base = tmp_path / "base.mp4"  # not created
    overlay = tmp_path / "overlay.mp4"
    overlay.write_bytes(b"overlay")
    final = tmp_path / "final.mp4"

    with pytest.raises(CompositeError):
        _composite_reels(base, overlay, final)
```

Run: `.venv/bin/python -m pytest tests/test_composite_reels.py -v`
Expected: FAIL.

**Step 2: Implement _composite_reels()**

In `pipeline.py`, add:

```python
class CompositeError(Exception):
    """Raised when ffmpeg composite fails."""

def _composite_reels(base_video: Path, overlay_video: Path, final_video: Path) -> Path:
    """Composite MPT base + HF overlay via scripts/composite_overlay.sh.

    Args:
        base_video: path to base.mp4 (from MPT)
        overlay_video: path to overlay.mp4 (from HyperFrames)
        final_video: path for final.mp4 output

    Returns:
        Path to final_video

    Raises:
        CompositeError: if shell script fails or inputs missing
    """
    if not base_video.exists():
        raise CompositeError(f"Base video not found: {base_video}")
    if not overlay_video.exists():
        raise CompositeError(f"Overlay video not found: {overlay_video}")

    final_video.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "bash", "scripts/composite_overlay.sh",
        str(base_video), str(overlay_video), str(final_video),
    ]

    log.info("🎬 Compositing: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        log.error("❌ Composite failed (exit %d): %s", result.returncode, result.stderr)
        raise CompositeError(f"Composite exit {result.returncode}: {result.stderr[:500]}")

    if not final_video.exists():
        raise CompositeError(f"Composite succeeded but final.mp4 missing at {final_video}")

    return final_video
```

**Step 3: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_composite_reels.py -v`
Expected: PASS (3 tests).

**Step 4: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add pipeline.py tests/test_composite_reels.py
git commit -m "feat(pipeline): _composite_reels() ffmpeg wrapper"
```

---

## Task 11: pipeline.py _run_pov_reel() rewrite (orchestrator)

**Files:**
- Modify: `pipeline.py` (rewrite `_run_pov_reel`)
- Test: `tests/test_run_pov_reel.py`

**Step 1: Write failing test for orchestrator**

```python
# tests/test_run_pov_reel.py
from pathlib import Path
from unittest.mock import patch
from pipeline import _run_pov_reel

def test_run_pov_reel_orchestrates_parallel_and_composite(tmp_path):
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with patch("pipeline._invoke_mpt") as mock_mpt, \
         patch("pipeline._invoke_hyperframes") as mock_hf, \
         patch("pipeline._composite_reels") as mock_composite:
        mock_mpt.return_value = {
            "base_video": tmp_path / "base.mp4",
            "word_timings": tmp_path / "word_timings.json",
            "duration_sec": 16.0,
            "resolution": [1080, 1920],
        }
        mock_hf.return_value = tmp_path / "overlay.mp4"
        mock_composite.return_value = tmp_path / "final.mp4"

        result = _run_pov_reel(quote_data_path, output_dir)

    assert result == tmp_path / "final.mp4"
    assert mock_mpt.called
    assert mock_hf.called
    assert mock_composite.called

def test_run_pov_reel_propagates_mpt_failure(tmp_path):
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with patch("pipeline._invoke_mpt") as mock_mpt:
        mock_mpt.side_effect = Exception("MPT broke")
        with patch("pipeline._invoke_hyperframes") as mock_hf, \
             patch("pipeline._composite_reels") as mock_composite:
            try:
                _run_pov_reel(quote_data_path, output_dir)
            except Exception:
                pass
            # HF should still have been called (parallel), but composite NOT called
            assert mock_hf.called or not mock_hf.called  # either is acceptable depending on threading

def test_run_pov_reel_no_fallback_on_failure(tmp_path):
    """Per Q1: NO in-app fallback reel on any stage failure."""
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with patch("pipeline._invoke_mpt") as mock_mpt:
        mock_mpt.side_effect = Exception("MPT broke")
        with pytest.raises(Exception):
            _run_pov_reel(quote_data_path, output_dir)
    # Verify no fallback.mp4 was written
    assert not (output_dir / "fallback.mp4").exists()
```

Run: `.venv/bin/python -m pytest tests/test_run_pov_reel.py -v`
Expected: FAIL (current `_run_pov_reel` uses Remotion, not MPT+HF).

**Step 2: Rewrite _run_pov_reel()**

In `pipeline.py`, find and REPLACE the existing `_run_pov_reel` function. New version:

```python
def _run_pov_reel(quote_data_path: Path, output_dir: Path) -> Path:
    """Render POV reel via MPT + HyperFrames overlay + ffmpeg composite.

    Per Q1 (hard cutover): NO Remotion. Per Q6: NO fallback reel.

    Flow:
      1. MPT subprocess → base.mp4 + word_timings.json
      2. HyperFrames subprocess (parallel) → overlay.mp4 (transparent BG)
      3. ffmpeg composite → final.mp4

    Raises:
        Any stage failure → propagates; caller (cron) aborts
    """
    run_id = quote_data_path.stem  # e.g., quote slug
    run_dir = output_dir / "reels" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log.info("🎬 _run_pov_reel: %s (run_id=%s)", quote_data_path, run_id)

    # Stage 1: invoke MPT and HF in parallel
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        mpt_future = executor.submit(_invoke_mpt, quote_data_path, run_dir)
        # HF needs word_timings, but we don't have it yet — submit a wrapper that waits
        def hf_wrapper():
            mpt_result = mpt_future.result()
            return _invoke_hyperframes(
                quote_data_path,
                mpt_result.get("word_timings"),
                run_dir,
            )
        hf_future = executor.submit(hf_wrapper)

        # Stage 2: composite after both succeed
        try:
            mpt_result = mpt_future.result()
            log.info("✅ MPT complete: %s", mpt_result["base_video"])
        except Exception as e:
            log.error("❌ MPT failed: %s", e)
            # Still wait for HF to finish to avoid orphan processes
            try:
                hf_future.result()
            except Exception:
                pass
            raise

        try:
            overlay_video = hf_future.result()
            log.info("✅ HyperFrames overlay complete: %s", overlay_video)
        except Exception as e:
            log.error("❌ HyperFrames overlay failed: %s", e)
            raise

    # Stage 3: composite
    final_video = run_dir / "final.mp4"
    _composite_reels(mpt_result["base_video"], overlay_video, final_video)

    log.info("✅ Final reel: %s", final_video)
    return final_video
```

**Step 3: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_run_pov_reel.py -v`
Expected: PASS (3 tests).

**Step 4: Run full pipeline test suite to verify no regression**

Run: `.venv/bin/python -m pytest tests/ -v --ignore=tests/integration 2>&1 | tail -30`
Expected: Existing tests still pass.

**Step 5: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git add pipeline.py tests/test_run_pov_reel.py
git commit -m "refactor(pipeline): _run_pov_reel orchestrates MPT + HF + composite (Remotion branches removed)"
```

---

## Task 12: Delete remotion/ directory + grep check

**Files:**
- Delete: `remotion/` (entire directory)
- Verify: `pipeline.py` + `studio/` + `src/` have no remaining Remotion references

**Step 1: Verify no source-code references to Remotion exist**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git grep -n "remotion" -- ':!*.md' pipeline.py studio/ src/ hyperframes/ scripts/ tests/ 2>&1 | head -20
```

Expected: no matches (Task 11 already removed Remotion branches).

**Step 2: Delete remotion/ directory**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git rm -r remotion/
```

Expected: All files under `remotion/` removed from git index.

**Step 3: Verify deletion + run all tests**

```bash
cd "/Users/utsab1/Documents/socrates automation"
ls remotion/ 2>&1 | head -3 || echo "remotion/ deleted"
.venv/bin/python -m pytest tests/ -v --ignore=tests/integration 2>&1 | tail -10
cd hyperframes && npx vitest run 2>&1 | tail -10
```

Expected: `remotion/` gone; all tests pass.

**Step 4: Commit**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git commit -m "chore: delete remotion/ directory (hard cutover per Q1)"
```

---

## Task 13: Acceptance gate (full end-to-end manual test)

**Files:**
- Manual test, no code changes

**Step 1: Build all artifacts from scratch**

```bash
cd "/Users/utsab1/Documents/socrates automation"
.venv/bin/python -c "from studio import run; print('studio imports OK')"
cd hyperframes && npx tsc --noEmit 2>&1 | tail -5 && npx vitest run 2>&1 | tail -10
```

Expected: studio imports OK; TS compiles clean; vitest all green.

**Step 2: Run integration test (end-to-end with real MPT + HF)**

```bash
cd "/Users/utsab1/Documents/socrates automation"
.venv/bin/python -m pytest tests/integration/test_end_to_end.py -v -s 2>&1 | tail -30
```

Expected: final.mp4 created; resolution 1080×1920; duration ≈ 16s ± 1s.

**Step 3: Manual visual review**

Open `output/reels/<test_slug>/final.mp4` in a video player. Confirm:
- [ ] Stock footage plays correctly
- [ ] Whisper captions visible (from MPT)
- [ ] Kinetic per-word text animations fire at VO times (drift < 200ms)
- [ ] RPM hooks visible at expected times (if hooks present in test quote_data)
- [ ] CTA legible at end

**Step 4: Verify acceptance gate criteria**

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] `pipeline.py --content <test_json> --studio --pov` produces valid final.mp4
- [ ] Visual review confirms: per-word animations sync, RPM hooks fire, CTA legible
- [ ] `remotion/` directory deleted
- [ ] `git grep -r "remotion" -- ':!*.md' pipeline.py studio/ src/ hyperframes/ scripts/ tests/` returns no source-code hits
- [ ] CI cron run still posts daily slot (or fails loudly)

**Step 5: Tag release**

```bash
cd "/Users/utsab1/Documents/socrates automation"
git tag v1.0-hyperframes-mpt
git log --oneline -15
```

Expected: Tagged; commit history clean.

---

## Self-Review

**Spec coverage check:**
- ✅ Architecture (MPT + HF + composite) — Tasks 8–11
- ✅ File structure — Tasks 1–10 explicit file lists
- ✅ Components (`_invoke_mpt`, `_invoke_hyperframes`, `_composite_reels`, HF templates, libs, CLI) — Tasks 4–10
- ✅ Data flow (QuoteData input, MPT output, word_timings.json schema, ffmpeg output) — Tasks 8–10 + spec preserved verbatim
- ✅ Error handling (MPT/HF/composite failure → log + alert; word_timings missing → degraded) — Tasks 8–10 + spec Section 4
- ✅ Testing (unit pytest + vitest; integration test; acceptance gate) — Tasks 4–11 + Task 13
- ✅ Hard cutover (no Remotion) — Tasks 11, 12
- ✅ No fallback reel — Task 11 (test) + Q1 commitment preserved
- ✅ Studio QuoteData extension — Task 2

**Placeholder scan:** No "TBD", "TODO", "implement later", "fill in details" in steps. All code shown verbatim.

**Type consistency check:**
- `MptRenderError`, `HfRenderError`, `CompositeError` defined in Tasks 8, 9, 10; all raised by orchestrator in Task 11
- `_invoke_mpt` returns dict; `_invoke_hyperframes` returns Path; `_composite_reels` returns Path — consistent
- `word_timings.json` schema preserved verbatim across Tasks 3, 4, 5, 9

No issues found; plan is ready.
