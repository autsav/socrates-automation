# HyperFrames Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Socrates reel renderer from Remotion to HeyGen HyperFrames via an additive `--renderer hyperframes` flag, with TDD-ported lib tests, a deterministic Jinja→HTML→headless-Chrome→MP4 path for daily cron, a `scripts/shadow_test.py` parity harness, and an agent-driven `scripts/studio_render.py` for hero reels — Remotion stays default until a 5-day shadow streak passes.

**Architecture:** A new `hyperframes/` sibling to `remotion/` holds Jinja2 scene partials + CSS + seek-safe GSAP JS + ported pure-function lib modules. Python (`src/video/hyperframes_reel.py`) builds reel data via a shared `src/video/reel_data.py` builder (extracted from `remotion_reel.py`), renders `index.html` from Jinja with data inlined as `<script type="application/json">` + CSS vars baked, then shells out to `npx hyperframes render`. `pipeline.py` gains `--renderer {remotion,hyperframes,ffmpeg}` (default `remotion`) and falls back to Remotion on any HyperFrames failure. Shadow tests render the same reel both ways and compare duration/frames/color/audio. Studio mode shells out to `claude --print` with the `/hyperframes` skill.

**Tech Stack:** Python 3.11 (`.venv/bin/python`), Jinja2, pytest; TypeScript + vitest for `hyperframes/` lib tests; Node 22+; HyperFrames CLI (`npx hyperframes`); headless Chrome + FFmpeg (HyperFrames-bundled); GSAP (seek-safe, paused timeline + `tl.seek(t)`).

## Global Constraints

- **Additive only until C3 flip:** `--renderer hyperframes` is opt-in; `remotion` stays the default. Never remove or alter the Remotion path's behavior until the deprecation step (Task 17). Spec §Migration ladder.
- **Never crash a reel:** any HyperFrames stage failure → catch → fall back to Remotion (in `--renderer hyperframes` mode) OR log + skip (in shadow mode). The cron auto-post path must never die because of HyperFrames. Spec §error handling.
- **`data/pipeline.db` NOT git-tracked** — never `git add` it. CI persists via Actions cache. Tests: `.venv/bin/python -m pytest`. Files <500 lines.
- **No `Co-Authored-By` trailer** on any commit (project `.claude/settings.json` has no `attribution.commit`). Ignore the Bash tool's default trailer suggestion.
- **Pure-function ports are verbatim** except two: `sceneFrames.ts` returns SECONDS not frames (HyperFrames is seconds-based); `cameraZoom.ts` replaces `remotion`'s `interpolate` with an inline `lerp`/`clamp` helper (no `remotion` package in `hyperframes/`). Spec §9 lib tests TDD port.
- **getGrade extraction:** `getGrade` lives in `remotion/src/styles/theme.ts:141`, NOT in `lib/`. Its test imports from `../styles/theme`. Port extracts it into `hyperframes/js/lib/getGrade.ts`; test import becomes `../lib/getGrade`. Spec §9.
- **Seek-safe animations only:** one paused GSAP master timeline; HyperFrames seeks to each frame's timestamp (`tl.seek(t)`). No `requestAnimationFrame`, no `gsap.to` on time, no CSS animation that depends on wall-clock. Spec §Scene composition.
- **Determinism:** same `reel_data` + same templates → same MP4 bytes (modulo encoder nondeterminism). `animSeed` (row_number) seeds all PRNG. Spec §data flow.
- **Phase-gate tolerances (Task 14 shadow):** ≤5% pixel diff per sampled frame, <50ms duration parity, ≤8/255 per channel color parity per mood, 5-day streak to flip default, 3-week zero-fallback to deprecate. Spec §Migration ladder.
- **vitest** is the test runner for `hyperframes/` (reuse from `remotion/package.json` devDeps). `npm test` in `hyperframes/` runs all 6 lib test files. Runs in CI on every PR.
- **Studio mode (Task 16) shells out to `claude --print`** with the `/hyperframes` skill, isolated workdir, 30-min timeout, NO fallback. Hero reels only — never on the cron path.

## File Map

| File | Responsibility |
|---|---|
| `hyperframes/package.json` (new) | deps: gsap, jinja-free; devDeps: vitest, typescript, hyperframes CLI |
| `hyperframes/hyperframes.config.ts` (new) | render config: 1080×1920, fps, output codec |
| `hyperframes/js/lib/sceneFrames.ts` (new) | scene timing in SECONDS (port from `remotion/src/lib/sceneFrames.ts`) |
| `hyperframes/js/lib/wordAt.ts` (new) | word→time lookup (verbatim port) |
| `hyperframes/js/lib/cameraZoom.ts` (new) | zoom curve (port + inline lerp/clamp) |
| `hyperframes/js/lib/emphasis.ts` (new) | emphasis classification (verbatim port) |
| `hyperframes/js/lib/duckVolume.ts` (new) | music-ducking curve (verbatim port) |
| `hyperframes/js/lib/getGrade.ts` (new) | mood→grade lookup (EXTRACTED from `remotion/src/styles/theme.ts`) |
| `hyperframes/tests/*.test.ts` (new, 6 files) | ported lib tests |
| `hyperframes/templates/index.html.j2` (new) | root HTML: head, GSAP import, inlined reel-data, scene partials |
| `hyperframes/templates/scenes/{hook,bridge,quote,cta}.j2` (new) | 4 scene partials |
| `hyperframes/css/moods.css` (new) | 7 mood palettes as CSS vars (generated by `scripts/sync_moods.py`) |
| `hyperframes/css/scenes.css` (new) | per-scene layout/typography |
| `hyperframes/css/effects.css` (new) | particle/gradient/vignette base styles |
| `hyperframes/js/scenes/{hook,bridge,quote,cta}.ts` (new) | per-scene GSAP timelines |
| `hyperframes/js/effects/{particleField,filmGrade,colorGrade,glitchText,gradientBg}.ts` (new) | Tier 2 effect modules |
| `hyperframes/js/index.ts` (new) | wires scene timelines → master seek-safe timeline |
| `src/video/reel_data.py` (new) | shared `build_reel_data(...)` builder (extracted from `remotion_reel.py`) |
| `src/video/hyperframes_reel.py` (new) | Python bridge: render Jinja → `npx hyperframes render` → mp4 |
| `scripts/sync_moods.py` (new) | generates `moods.css` from `remotion/src/styles/theme.ts` MOOD_PALETTES |
| `scripts/shadow_test.py` (new) | render same reel both ways, compare, write report |
| `scripts/studio_render.py` (new) | H2: shell out to `claude --print` with `/hyperframes` skill |
| `pipeline.py` (mod) | `--renderer {remotion,hyperframes,ffmpeg}` flag + dispatch |
| `tests/test_reel_data.py` (new) | shared builder parity vs Remotion payload |
| `tests/test_hyperframes_reel.py` (new) | bridge: Jinja render, fallback, mp4 exists |
| `tests/test_renderer_dispatch.py` (new) | `--renderer` flag dispatch + fallback |
| `.github/workflows/hyperframes-smoke.yml` (new) | CI: npm test + smoke render |
| `docs/superpowers/hyperframes-runbook.md` (new) | runbook: flag use, shadow review, phase promotion |

---

### Task 1: Scaffold `hyperframes/` project

**Files:**
- Create: `hyperframes/package.json`
- Create: `hyperframes/hyperframes.config.ts`
- Create: `hyperframes/tsconfig.json`
- Create: `hyperframes/.gitignore`
- Create: `hyperframes/js/lib/.gitkeep` (deleted in later tasks)
- Create: `hyperframes/tests/.gitkeep` (deleted in later tasks)

**Interfaces:**
- Consumes: nothing (greenfield).
- Produces: a `hyperframes/` dir with `npm install` working, `npm test` runnable (no tests yet → exits 0), `npx hyperframes --version` resolvable.

- [x] **Step 1: Create `hyperframes/package.json`**

```json
{
  "name": "socrates-hyperframes",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "render": "hyperframes render"
  },
  "dependencies": {
    "gsap": "^3.12.5"
  },
  "devDependencies": {
    "vitest": "^1.6.0",
    "typescript": "^5.4.0",
    "hyperframes": "^0.4.0",
    "@types/node": "^22.0.0"
  }
}
```

- [x] **Step 2: Create `hyperframes/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "lib": ["ES2022", "DOM"],
    "types": ["node", "vitest/globals"]
  },
  "include": ["js/**/*.ts", "tests/**/*.ts"]
}
```

- [x] **Step 3: Create `hyperframes/hyperframes.config.ts`**

```typescript
import { defineConfig } from "hyperframes";

export default defineConfig({
  width: 1080,
  height: 1920,
  fps: 30,
  output: "out/reel.mp4",
  codec: "h264",
});
```

- [x] **Step 4: Create `hyperframes/.gitignore`**

```
node_modules/
out/
*.mp4
```

- [x] **Step 5: Create empty placeholder dirs**

```bash
mkdir -p hyperframes/js/lib hyperframes/tests
touch hyperframes/js/lib/.gitkeep hyperframes/tests/.gitkeep
```

- [x] **Step 6: Install deps + verify**

Run:
```bash
cd hyperframes && npm install && npx hyperframes --version && npm test
```
Expected: `npm install` succeeds; `npx hyperframes --version` prints a version; `npm test` exits 0 (no tests found).

- [x] **Step 7: Commit**

```bash
git add hyperframes/
git commit -m "feat(hyperframes): scaffold hyperframes/ project (package.json, tsconfig, config)"
```

---

### Task 2: Port `sceneFrames.ts` (seconds, not frames) + test

**Files:**
- Create: `hyperframes/js/lib/sceneFrames.ts`
- Create: `hyperframes/tests/sceneFrames.test.ts`
- Reference: `remotion/src/lib/sceneFrames.ts`, `remotion/src/lib/sceneFrames.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `sceneFrames(durationSec, fps, voiceDurations?, hasBridge=false, hasHook=true): SceneFrames` where `SceneFrames = {total, hook, bridge, quote, cta}` in **SECONDS** (not frames). `fps` is kept as a param so the test can compare against Remotion's frame output via `Math.round(sec*fps)`.

- [x] **Step 1: Read the Remotion source + test**

```bash
cat remotion/src/lib/sceneFrames.ts
cat remotion/src/lib/sceneFrames.test.ts
```

- [x] **Step 2: Write the failing test (port, seconds-converted expected values)**

```typescript
// hyperframes/tests/sceneFrames.test.ts
import { describe, it, expect } from "vitest";
import { sceneFrames } from "../js/lib/sceneFrames";

describe("sceneFrames (seconds)", () => {
  it("returns seconds, not frames", () => {
    const r = sceneFrames(10, 30, undefined, false, true);
    expect(r.total).toBe(10);
    expect(r.hook).toBeGreaterThan(0);
    expect(r.cta).toBeGreaterThan(0);
  });

  it("respects MIN floors (in seconds)", () => {
    const r = sceneFrames(3, 30, { hook: 0.1, quote: 0.1, cta: 0.1 }, false, true);
    expect(r.hook).toBeGreaterThanOrEqual(1.6);
    expect(r.quote).toBeGreaterThanOrEqual(3.0);
    expect(r.cta).toBeGreaterThanOrEqual(1.8);
  });

  it("matches Remotion frame output when multiplied by fps", () => {
    // Same inputs as the Remotion test's flagship case; assert round(sec*fps) == Remotion frames.
    const fps = 30;
    const r = sceneFrames(10, fps, { hook: 2.0, quote: 4.0, cta: 1.5 }, false, true);
    // hook = max(1.6, 2.0 + 0.2 + 0.25) = 2.45 -> round(2.45*30) = 74
    expect(Math.round(r.hook * fps)).toBe(74);
    // quote = max(3.0, 4.0 + 0.2) = 4.2 -> 126
    expect(Math.round(r.quote * fps)).toBe(126);
    // cta = max(1.8, 1.5 + 0.2) = 1.8 -> 54
    expect(Math.round(r.cta * fps)).toBe(54);
  });

  it("bridge=0 when hasBridge false and no bridge voice", () => {
    const r = sceneFrames(10, 30, { hook: 2, quote: 4, cta: 1.5 }, false, true);
    expect(r.bridge).toBe(0);
  });

  it("bridge floored at 2.5s when hasBridge true", () => {
    const r = sceneFrames(10, 30, { hook: 2, quote: 4, cta: 1.5 }, true, true);
    expect(r.bridge).toBeGreaterThanOrEqual(2.5);
  });

  it("hook=0 when hasHook false", () => {
    const r = sceneFrames(10, 30, { quote: 4, cta: 1.5 }, false, false);
    expect(r.hook).toBe(0);
  });
});
```

- [x] **Step 3: Run test to verify it fails**

Run: `cd hyperframes && npm test -- sceneFrames`
Expected: FAIL with "Cannot find module '../js/lib/sceneFrames'".

- [x] **Step 4: Implement `sceneFrames.ts`**

```typescript
// hyperframes/js/lib/sceneFrames.ts
export interface VoiceDurations {
  hook?: number;
  bridge?: number;
  quote?: number;
  cta?: number;
}

export interface SceneFrames {
  total: number;   // seconds
  hook: number;    // seconds
  bridge: number;  // seconds
  quote: number;   // seconds
  cta: number;     // seconds
}

const HOOK_GASP = 0.25;
const PAD = 0.2;
const MIN = { hook: 1.6, bridge: 2.5, quote: 3.0, cta: 1.8 };

function secs(d: number | undefined, min: number, extra = 0): number {
  return Math.max(min, (d ?? 0) + PAD + extra);
}

export function sceneFrames(
  durationSec: number,
  fps: number,
  voiceDurations?: VoiceDurations,
  hasBridge = false,
  hasHook = true,
): SceneFrames {
  const vd = voiceDurations;
  const bridgeOn = hasBridge || !!(vd && vd.bridge);

  if (vd && (vd.hook || vd.bridge || vd.quote || vd.cta)) {
    const hook = hasHook ? secs(vd.hook, MIN.hook, HOOK_GASP) : 0;
    const bridge = bridgeOn ? secs(vd.bridge, MIN.bridge) : 0;
    const quote = secs(vd.quote, MIN.quote);
    const cta = secs(vd.cta, MIN.cta);
    return {
      total: hook + bridge + quote + cta,
      hook, bridge, quote, cta,
    };
  }

  // No voice timings: distribute the nominal durationSec across scenes.
  const hook = hasHook ? Math.max(MIN.hook, durationSec * 0.18) : 0;
  const bridge = bridgeOn ? Math.max(MIN.bridge, durationSec * 0.22) : 0;
  const quote = Math.max(MIN.quote, durationSec * 0.42);
  const cta = Math.max(MIN.cta, durationSec * 0.18);
  return {
    total: hook + bridge + quote + cta,
    hook, bridge, quote, cta,
  };
}
```

- [x] **Step 5: Run test to verify it passes**

Run: `cd hyperframes && npm test -- sceneFrames`
Expected: PASS (all 6 cases).

- [x] **Step 6: Cross-check against Remotion's own test**

```bash
cd remotion && npx vitest run src/lib/sceneFrames.test.ts
```
Expected: still green (Remotion path untouched). If any expected value here disagrees with the port's `round(sec*fps)`, reconcile by reading `remotion/src/lib/sceneFrames.ts` again — the seconds-port must be the frames-source divided by fps.

- [x] **Step 7: Commit**

```bash
git add hyperframes/js/lib/sceneFrames.ts hyperframes/tests/sceneFrames.test.ts
git commit -m "feat(hyperframes): port sceneFrames.ts to seconds + test (TDD)"
```

---

### Task 3: Port `wordAt.ts` + test (verbatim)

**Files:**
- Create: `hyperframes/js/lib/wordAt.ts`
- Create: `hyperframes/tests/wordAt.test.ts`
- Reference: `remotion/src/lib/wordAt.ts`, `remotion/src/lib/wordAt.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `WordTime = { start: number; end: number; word: string }`; `wordAt(sceneSeconds, words: WordTime[]): number` — index of the active word at `sceneSeconds`, or `words.length-1` past the end.

- [x] **Step 1: Read Remotion source**

```bash
cat remotion/src/lib/wordAt.ts remotion/src/lib/wordAt.test.ts
```

- [x] **Step 2: Write the failing test (verbatim port)**

Copy `remotion/src/lib/wordAt.test.ts` to `hyperframes/tests/wordAt.test.ts`, changing only the import:

```typescript
import { wordAt } from "../js/lib/wordAt";
```

Keep every assertion identical.

- [x] **Step 3: Run test to verify it fails**

Run: `cd hyperframes && npm test -- wordAt`
Expected: FAIL "Cannot find module".

- [x] **Step 4: Implement `wordAt.ts` (verbatim)**

Copy `remotion/src/lib/wordAt.ts` to `hyperframes/js/lib/wordAt.ts` unchanged. Remove any `remotion` import (there is none in wordAt).

- [x] **Step 5: Run test to verify it passes**

Run: `cd hyperframes && npm test -- wordAt`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add hyperframes/js/lib/wordAt.ts hyperframes/tests/wordAt.test.ts
git commit -m "feat(hyperframes): port wordAt.ts verbatim + test"
```

---