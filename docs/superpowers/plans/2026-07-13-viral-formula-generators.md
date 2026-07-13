# Viral-Formula Generators + Injection (Sub-project B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make reels formula-compliant (hook length, DM CTAs, 3–5 hashtags, seamless loop), add a `--content <json>` injection path, and add an optional Remotion Bridge scene.

**Architecture:** Pure helper functions in `pipeline.py` enforce the formula; a new `_injected_content` content source feeds hand-crafted/external content; the Remotion project gains an optional 4th `BridgeScene` rendered only when a `bridge` is present.

**Tech Stack:** Python 3.11, React/Remotion (TypeScript), pytest.

## Global Constraints

- Python 3.11; run tests with `.venv/bin/python -m pytest`.
- Remotion reels must stay backward-compatible: a reel with NO `bridge` renders the current 3-scene arc unchanged.
- Never crash a reel; all validators are pure and must not raise.
- Do NOT commit `data/pipeline.db`; if a run dirties it, `git checkout -- data/pipeline.db` first.
- Unrelated uncommitted artifacts exist (quotes.xlsx, remotion/public/*.mp3, reel-data.json) — never stage them. Only `git add` the files each task's commit step names.
- Full suite is green EXCEPT the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures.
- Remotion TS changes must keep `npm --prefix remotion run build` (tsc) passing.

---

### Task 1: Formula generator helpers (pipeline.py)

**Files:**
- Modify: `pipeline.py` (add `_enforce_hook_len`, `_loopify`; extend `_CTA_VARIANTS`; rewrite `_generate_hashtags` clamp)
- Test: `tests/test_formula_generators.py`

**Interfaces:**
- Produces: `_enforce_hook_len(hook: str) -> str`; `_loopify(cta: str, hook: str) -> str`; `_generate_hashtags(audience, mood, max_tags=5) -> str` (now returns 3–5 tags, no generic).

- [ ] **Step 1: Write the failing test**

Create `tests/test_formula_generators.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def test_enforce_hook_len_trims_over_12_words():
    long = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
    out = pipeline._enforce_hook_len(long)
    assert len(out.split()) <= 12


def test_enforce_hook_len_leaves_short_hook():
    h = "Stop scrolling. Start living."
    assert pipeline._enforce_hook_len(h) == h


def test_cta_variants_have_no_follow_or_like():
    joined = " ".join(pipeline._CTA_VARIANTS).lower()
    assert "follow for more" not in joined
    assert "like if" not in joined


def test_cta_variants_include_dm_trigger():
    assert any("dm you" in c.lower() or "comment '" in c.lower() for c in pipeline._CTA_VARIANTS)


def test_generate_hashtags_count_between_3_and_5():
    for aud in ("procrastinator", "unknown_aud"):
        tags = pipeline._generate_hashtags(aud, "dark_philosophical").split()
        assert 3 <= len(tags) <= 5


def test_generate_hashtags_no_generic():
    tags = pipeline._generate_hashtags("stuck", "calm_stoic").lower()
    for bad in ("#fyp", "#viral", "#reels", "#explore"):
        assert bad not in tags


def test_loopify_cta_ends_with_open_connector():
    out = pipeline._loopify("Save this for later.", "Stop wasting your evenings.")
    assert out.rstrip().endswith("—")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_formula_generators.py -v`
Expected: FAIL (`_enforce_hook_len`/`_loopify` undefined; hashtag count 7).

- [ ] **Step 3: Implement**

In `pipeline.py`, add two DM-trigger CTAs to `_CTA_VARIANTS` (append inside the existing list):

```python
    "Comment 'STOIC' and I'll DM you the full reflection.",     # DM trigger
    "Comment 'RESET' and I'll DM you the 3-line Stoic reset.",  # DM trigger
```

Rewrite `_generate_hashtags` to return exactly 3–5 non-generic tags:

```python
_GENERIC_TAGS = {"#fyp", "#viral", "#reels", "#explore", "#foryou", "#trending"}


def _generate_hashtags(audience: str, mood: str, max_tags: int = 5) -> str:
    """Build a 3–5 tag string: base + audience + mood tags, generic tags removed."""
    candidates = list(_BASE_HASHTAGS[:2])
    for t in _HASHTAG_POOL.get(audience, []):
        candidates.append(t)
    candidates.append(f"#{mood.replace('_', '').title()}")
    # Dedupe (case-insensitive), drop generic, preserve order.
    seen, tags = set(), []
    for t in candidates:
        k = t.lower()
        if k in _GENERIC_TAGS or k in seen:
            continue
        seen.add(k)
        tags.append(t)
    tags = tags[:max(3, min(max_tags, 5))]
    # Pad to 3 from the base pool if somehow short.
    for t in _BASE_HASHTAGS:
        if len(tags) >= 3:
            break
        if t.lower() not in seen:
            tags.append(t)
            seen.add(t.lower())
    return " ".join(tags[:5])
```

Add the two new helpers near the other enhancers:

```python
def _enforce_hook_len(hook: str, max_words: int = 12) -> str:
    """Formula rule: hooks are 5–12 words. Trim an over-long hook to its first
    sentence/clause within the word budget (never raises)."""
    if not hook:
        return hook
    words = hook.split()
    if len(words) <= max_words:
        return hook
    # Prefer cutting at the first sentence end within budget.
    trimmed = " ".join(words[:max_words])
    for stop in (".", "?", "!"):
        i = trimmed.find(stop)
        if i != -1:
            return trimmed[: i + 1]
    return trimmed.rstrip(",;:") + "…"


def _loopify(cta: str, hook: str) -> str:
    """Seamless-loop device: end the CTA with an open connector so it flows back
    into the hook. Idempotent."""
    c = (cta or "").rstrip()
    if not c:
        return c
    if c.endswith(("—", "…")):
        return c
    return c.rstrip(".!?") + " —"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_formula_generators.py -v`
Expected: PASS (all 7).

- [ ] **Step 5: Commit**

```bash
git add pipeline.py tests/test_formula_generators.py
git commit -m "feat(formula): hook-len + loop + DM-CTA + 3-5 hashtag generators"
```

---

### Task 2: `--content <json>` injection path

**Files:**
- Modify: `pipeline.py` (`_injected_content`, argparse `--content`, `run_pipeline` wiring)
- Test: `tests/test_content_injection.py`

**Interfaces:**
- Consumes: `_enforce_hook_len`, `_loopify`, `_generate_hashtags` (Task 1).
- Produces: `_injected_content(path: str, cfg) -> tuple[dict, str]` returning `(quote_data, mood)`. `quote_data` keys: `quote, audience, caption, mood, hook, bridge, row_number, source, cta, attribution`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_content_injection.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def _write(tmp_path, obj):
    p = tmp_path / "content.json"
    p.write_text(json.dumps(obj))
    return str(p)


def test_injected_content_full_override(tmp_path):
    p = _write(tmp_path, {
        "hook": "Stop scrolling. Start living.", "bridge": "But Socrates knew this.",
        "quote": "The unexamined life is not worth living.", "attribution": "— Socrates",
        "cta": "Save this for later.", "caption": "A caption.",
        "hashtags": ["#Stoicism", "#Socrates", "#Mindset"], "mood": "dark_philosophical",
        "audience": "stuck", "row_number": None})
    qd, mood = pipeline._injected_content(p, cfg=None)
    assert qd["quote"].startswith("The unexamined")
    assert qd["bridge"] == "But Socrates knew this."
    assert mood == "dark_philosophical"
    assert qd["row_number"] is None
    assert "#Stoicism" in qd["caption"]  # hashtags appended to caption


def test_injected_content_partial_falls_back(tmp_path):
    p = _write(tmp_path, {"quote": "Know thyself.", "audience": "lost", "mood": "calm_stoic"})
    qd, mood = pipeline._injected_content(p, cfg=None)
    # Missing hook/cta -> generators fill them; hashtags -> 3-5 generated.
    assert qd["hook"]  # non-empty
    assert qd["cta"]
    assert 3 <= len([t for t in qd["caption"].split() if t.startswith("#")]) <= 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_content_injection.py -v`
Expected: FAIL (`_injected_content` undefined).

- [ ] **Step 3: Implement `_injected_content`**

Add to `pipeline.py` (near `_legacy_content`):

```python
def _injected_content(path: str, cfg) -> tuple[dict, str]:
    """Load a hand-crafted/external reel content JSON, filling any missing field
    from the existing generators. Bypasses excel + studio. Returns (quote_data, mood)."""
    import json as _json
    data = _json.loads(Path(path).read_text())
    audience = (data.get("audience") or "stuck").strip().lower()
    row_number = data.get("row_number")  # may be None -> excel not marked
    rn_seed = row_number if isinstance(row_number, int) else 0
    mood = data.get("mood") or "dark_philosophical"

    hook = _enforce_hook_len(data.get("hook") or _generate_psychology_hook(audience, rn_seed))
    cta = data.get("cta") or _pick_cta(rn_seed)
    cta = _loopify(cta, hook)

    hashtags = data.get("hashtags")
    if isinstance(hashtags, list) and hashtags:
        tag_str = " ".join(hashtags[:5])
    else:
        tag_str = _generate_hashtags(audience, mood)

    caption = data.get("caption") or data.get("quote", "")
    caption = f"{caption}\n\n{tag_str}"

    quote_data = {
        "quote": data.get("quote", ""),
        "audience": audience,
        "caption": caption,
        "mood": mood,
        "hook": hook,
        "bridge": data.get("bridge", ""),
        "cta": cta,
        "attribution": data.get("attribution", "— Socrates"),
        "row_number": row_number,
        "source": data.get("source", "injected"),
    }
    return quote_data, mood
```

- [ ] **Step 4: Wire the flag + content-stage selection**

In the `argparse` block (near the other `add_argument` calls), add:

```python
    parser.add_argument("--content", type=str, default=None,
                        help="Path to a JSON file of hand-crafted reel content "
                             "(hook/bridge/quote/cta/caption/hashtags/mood); bypasses excel+studio.")
```

Pass it through: change the `run_pipeline(...)` calls in `__main__` to include `content=args.content`, and add `content: str | None = None` to `run_pipeline`'s signature.

In `run_pipeline`, at the top of the content stage (just before `if studio:`), add the injection branch:

```python
    if content:
        log.info(f"Step 1: Injected content from {content}")
        quote_data, mood = _injected_content(content, cfg)
        studio_decision = None
        controversy = ""
        caption_variant = -1
    elif studio:
        ...  # existing studio branch unchanged
```

(Keep the existing `studio` / legacy branches as the `elif` / `else`. Ensure `studio_decision`, `controversy`, `caption_variant` are defined in the injected branch so the downstream code is unaffected.)

- [ ] **Step 5: Run tests + a smoke import**

Run: `.venv/bin/python -m pytest tests/test_content_injection.py -v`
Expected: PASS (both).
Run: `.venv/bin/python -c "import pipeline; print('import OK')"`
Expected: `import OK`.

- [ ] **Step 6: Commit**

```bash
git add pipeline.py tests/test_content_injection.py
git commit -m "feat(inject): --content JSON path bypasses excel+studio content stage"
```

---

### Task 3: Remotion optional Bridge scene

**Files:**
- Create: `remotion/src/components/BridgeScene.tsx`
- Modify: `remotion/src/lib/sceneFrames.ts`, `remotion/src/PovReel.tsx`, `remotion/src/Root.tsx`
- Modify: `src/video/remotion_reel.py` (`write_bridge_file`)
- Test: `tests/test_remotion_reel.py` (append)

**Interfaces:**
- Produces: bridge support in `write_bridge_file(..., bridge="", bridge_voice=None, bridge_words=None)` — writes `bridge`, `voices.bridge`, `voiceDurations.bridge`, `wordTimes.bridge` into `reel-data.json`.
- `sceneFrames(...)` returns an added optional `bridge` frame count.

- [ ] **Step 1: Write the failing test (Python bridge file)**

Append to `tests/test_remotion_reel.py`:

```python
def test_bridge_file_includes_bridge_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "_synth_sfx", lambda d: None)
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p,
                         bridge="But Socrates knew this.")
    data = json.loads(p.read_text())
    assert data["bridge"] == "But Socrates knew this."


def test_bridge_file_omits_bridge_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "_synth_sfx", lambda d: None)
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p)
    data = json.loads(p.read_text())
    assert data.get("bridge", "") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -k bridge_file -v`
Expected: FAIL (`write_bridge_file` has no `bridge` param).

- [ ] **Step 3: Extend `write_bridge_file`**

In `src/video/remotion_reel.py`, add params `bridge: str = ""`, `bridge_voice: Path | None = None`, `bridge_words: list | None = None` to `write_bridge_file`. In the `voices`/`voice_durations` loop, include `("bridge", bridge_voice)` alongside hook/quote/cta. Add to the `payload`:

```python
        "bridge": bridge or "",
```
and add `"bridge"` keys to the `voices`, `voiceDurations`, and `wordTimes` dicts (bridge_words). Beats still derive from `quote_voice` only.

- [ ] **Step 4: Run the Python bridge test**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -k bridge_file -v`
Expected: PASS.

- [ ] **Step 5: Add bridge to `sceneFrames.ts`**

Replace `remotion/src/lib/sceneFrames.ts` interface + function to thread an optional bridge (present only when `voiceDurations.bridge` or a `hasBridge` flag is set):

```typescript
export interface SceneFrames {
  total: number;
  hook: number;
  bridge: number;
  quote: number;
  cta: number;
}

export function sceneFrames(
  durationSec: number,
  fps: number,
  voiceDurations?: { hook?: number; bridge?: number; quote?: number; cta?: number },
  hasBridge = false
): SceneFrames {
  const vd = voiceDurations;
  const bridgeOn = hasBridge || !!(vd && vd.bridge);
  if (vd && (vd.hook || vd.bridge || vd.quote || vd.cta)) {
    const PAD = 0.6;
    const MIN = { hook: 2.5, bridge: 2.5, quote: 3.0, cta: 2.0 };
    const secs = (d: number | undefined, min: number) => Math.max(min, (d ?? 0) + PAD);
    const hook = Math.round(secs(vd.hook, MIN.hook) * fps);
    const bridge = bridgeOn ? Math.round(secs(vd.bridge, MIN.bridge) * fps) : 0;
    const quote = Math.round(secs(vd.quote, MIN.quote) * fps);
    const cta = Math.round(secs(vd.cta, MIN.cta) * fps);
    return { total: hook + bridge + quote + cta, hook, bridge, quote, cta };
  }
  const total = Math.round(durationSec * fps);
  const hook = Math.min(Math.round(3.5 * fps), Math.round(total * 0.3));
  const bridge = bridgeOn ? Math.round(2.5 * fps) : 0;
  const cta = Math.min(Math.round(2.5 * fps), Math.round(total * 0.24));
  const quote = Math.max(total - hook - bridge - cta, Math.round(2 * fps));
  return { total: hook + bridge + quote + cta, hook, bridge, quote, cta };
}
```

- [ ] **Step 6: Create `BridgeScene.tsx`**

Create `remotion/src/components/BridgeScene.tsx` (mirrors `HookScene` but gentler; smaller font):

```tsx
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedText } from "./AnimatedText";
import { Palette } from "../styles/theme";
import { WordTime } from "../lib/wordAt";

/** BridgeScene — the pivot from the trending hook into the timeless quote. */
export const BridgeScene: React.FC<{
  text: string;
  palette: Palette;
  wordTimes?: WordTime[];
}> = ({ text, palette, wordTimes }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const entrance = spring({ frame, fps, config: { damping: 16, mass: 0.9, stiffness: 80 }, durationInFrames: 18 });
  const enterScale = interpolate(entrance, [0, 1], [1.04, 1]);
  const outFade = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", inset: 0, opacity: outFade, transform: `scale(${enterScale})` }}>
      <AnimatedText text={text} palette={palette} fontSize={120} stagger={0.06} wordTimes={wordTimes} />
    </div>
  );
};
```

- [ ] **Step 7: Wire the bridge into `PovReel.tsx`**

Add `bridge?: string` and `voices.bridge?`, `voiceDurations.bridge?`, `wordTimes.bridge?` to `PovReelProps` and `povReelDefaultProps` (default `bridge: ""`). Import `BridgeScene`. Compute frames with the bridge and shift the quote/CTA sequences:

```tsx
  const { hook: hookF, bridge: bridgeF, quote: quoteF } = sceneFrames(
    durationInFrames / fps, fps, voiceDurations, !!bridge
  );
  const quoteStart = hookF + bridgeF;
  const quoteEnd = quoteStart + quoteF;
```

Render a Bridge `<Sequence from={hookF} durationInFrames={bridgeF}>` (only when `bridge` truthy) between the Hook and Quote sequences; change the Quote sequence to `from={quoteStart}` and the CTA to `from={quoteEnd}`. Move the first `WhiteFlash` to `at={hookF}` (hook→bridge or hook→quote) and add one `at={quoteStart}` when bridge is present. Add a bridge VO block mirroring the hook VO:

```tsx
      {bridge ? (
        <Sequence from={hookF} durationInFrames={bridgeF} name="Bridge">
          <BridgeScene text={bridge} palette={palette} wordTimes={wordTimes.bridge} />
        </Sequence>
      ) : null}
      {voices.bridge ? (
        <Sequence from={hookF} durationInFrames={bridgeF} name="BridgeVO">
          <Audio src={staticFile(voices.bridge)} />
        </Sequence>
      ) : null}
```

Update `beatFrames` to offset by `quoteStart` (not `hookF`), and the `duckSpans` to include a bridge span `spanFor(hookF, voiceDurations.bridge, bridgeF)`.

- [ ] **Step 8: Update `Root.tsx` metadata**

Wherever `Root.tsx` calls `sceneFrames(...)` for `durationInFrames`/`calculateMetadata`, pass the props' `voiceDurations` and `!!props.bridge` so the composition length includes the bridge. (Follow the existing `calculateMetadata`/default-props pattern; the default `bridge` is `""` so default length is unchanged.)

- [ ] **Step 9: Build the Remotion project (tsc)**

Run: `npm --prefix remotion run build`
Expected: exits 0 (TypeScript compiles). If there is no `build` script, run `npx --prefix remotion tsc --noEmit -p remotion/tsconfig.json`.

- [ ] **Step 10: Run the Python remotion tests**

Run: `.venv/bin/python -m pytest tests/test_remotion_reel.py -v`
Expected: PASS (existing + the 2 new bridge tests). The optional real-render test stays skipped unless Node+Remotion are present.

- [ ] **Step 11: Commit**

```bash
git add remotion/src/components/BridgeScene.tsx remotion/src/lib/sceneFrames.ts remotion/src/PovReel.tsx remotion/src/Root.tsx src/video/remotion_reel.py tests/test_remotion_reel.py
git commit -m "feat(remotion): optional Bridge scene (Hook->Bridge->Quote->CTA)"
```

---

### Task 4: Wire bridge VO + formula into the reel path

**Files:**
- Modify: `pipeline.py` (`_run_pov_reel`), `src/video/remotion_reel.py` (`generate_remotion_reel` passes bridge)
- Test: `tests/test_pov_reel_bridge.py`

**Interfaces:**
- Consumes: `write_bridge_file` bridge params (Task 3); `_injected_content` bridge field (Task 2); `_enforce_hook_len`/`_loopify` (Task 1).
- Produces: `_run_pov_reel` generates a bridge VO when `quote_data.get("bridge")` and passes `bridge`/`bridge_voice`/`bridge_words` through to Remotion.

- [ ] **Step 1: Write the failing test**

Create `tests/test_pov_reel_bridge.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import inspect
from src.video import remotion_reel


def test_generate_remotion_reel_accepts_bridge_params():
    sig = inspect.signature(remotion_reel.generate_remotion_reel)
    for p in ("bridge", "bridge_voice", "bridge_words"):
        assert p in sig.parameters, f"generate_remotion_reel missing {p}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pov_reel_bridge.py -v`
Expected: FAIL (`generate_remotion_reel` has no `bridge` param).

- [ ] **Step 3: Thread bridge through `generate_remotion_reel`**

In `src/video/remotion_reel.py`, add params `bridge: str = ""`, `bridge_voice=None`, `bridge_words=None` to `generate_remotion_reel`, and pass them into the `write_bridge_file(...)` call it makes.

- [ ] **Step 4: Generate the bridge VO + finalize hook/CTA in `_run_pov_reel`**

In `pipeline.py` `_run_pov_reel`, where the Remotion VO is prepared (the `use_remotion` block that builds `hook_voice`/`quote_voice`/`cta_voice`), also produce a bridge clip when `quote_data.get("bridge")`:
- Reuse `prepare_reel_voiceover_edge_tts`-style generation, OR call `generate_scene_voiceover_edge_tts(bridge_text, REEL_VOICE, bridge_path, REEL_RATE, REEL_PITCH)` from `src.audio.edge_tts_engine` and `parse_word_srt` for `bridge_words`.
- Finalize the hook and CTA before render: `hook_text = _enforce_hook_len(quote_data.get("hook") or hook_text)` and `cta_text = _loopify(cta_text, hook_text)`.
- Pass `bridge=quote_data.get("bridge", "")`, `bridge_voice`, `bridge_words` into `generate_remotion_reel(...)`.

(Keep every existing fallback: no bridge → 3-scene reel; edge-tts unavailable → bridge silent but still shown.)

- [ ] **Step 5: Run the test + a dry-run smoke**

Run: `.venv/bin/python -m pytest tests/test_pov_reel_bridge.py -v`
Expected: PASS.
Run (writes an injected 4-scene reel, no posting): create `/tmp/bridge_demo.json` with a `bridge` field, then
`.venv/bin/python pipeline.py --content /tmp/bridge_demo.json --remotion --dry-run 2>&1 | grep -iE "bridge|remotion|reel"`
Expected: the reel renders; log shows the injected content path. (If Node/Remotion is present, `reel_00x.mp4` is produced.)

- [ ] **Step 6: Full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: only the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures. If `test_committed_db_has_no_token` fails, `git checkout -- data/pipeline.db` and re-run.

- [ ] **Step 7: Commit**

```bash
git add pipeline.py src/video/remotion_reel.py tests/test_pov_reel_bridge.py
git commit -m "feat(reel): bridge VO + formula-finalized hook/CTA through Remotion"
```

---

## Notes for the implementer

- Do NOT change `_run_pov_reel`'s public signature; the bridge is derived from `quote_data`.
- The Remotion changes (Task 3) are the riskiest — build with `npm --prefix remotion run build` (tsc) after each edit and keep the no-bridge path byte-identical in behavior.
- After B lands, Sub-project A is: write a `content.json` for the "AI Burnout × Socrates" demo (from the fork) and run `pipeline.py --content that.json --remotion` to post it. Sub-project NEW then generates that JSON's `hook`/`bridge` from live trends.
