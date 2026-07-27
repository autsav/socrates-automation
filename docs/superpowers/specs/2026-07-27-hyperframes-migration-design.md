# HyperFrames Migration — Design

**Date:** 2026-07-27
**Status:** Approved (brainstormed 2026-07-27)
**Supersedes:** none — adds a parallel renderer; `remotion/` is deprecated through a phased ladder
**Related:** `2026-07-14-flux-remotion-reel-design.md` (current Remotion path), `2026-07-20-realsync-animation-director-design.md` (animation director)

## Summary

Migrate the Socrates reel pipeline's renderer from Remotion (React, source-available) to HeyGen HyperFrames (plain HTML + GSAP, Apache-2.0, deterministic, agent-friendly). Run both renderers in parallel for a phased C2 → C3 → C1 rollout, then delete Remotion. Add a separate agent-driven "studio mode" for one-off hero reels where an AI invents fresh visuals via the `/hyperframes` skill.

## Decisions (locked during brainstorm)

| Dimension | Choice |
|---|---|
| Operating mode | **C — Hybrid**: deterministic CLI path (daily cron) + agent-driven studio mode (hero reels) |
| Migration ladder | **C2 → shadow → C3 → C1**: additive flag → parallel compare → flip default → deprecate Remotion |
| v1 scope | **S2 + tests**, TDD-ordered: port 9 lib tests → Tier 1 skeleton → Tier 2 GSAP polish → shadow tests |
| Bridge contract | **B2**: Python generates `hyperframes/index.html` from a Jinja2 template, reel data inlined as `<script type="application/json">` + CSS vars baked; no `file://` fetch at render time |
| Composition structure | **Approach B — Scene-modular**: 4 Jinja scene partials + per-scene GSAP timelines + reusable effect modules; 9 lib tests ported to `hyperframes/tests/` |
| Studio mode | **H2**: `scripts/studio_render.py` shells out to `claude --print` with the `/hyperframes` skill; isolated workdir, 30-min timeout, no fallback |

## Background

### Current render path

`pipeline.py::_run_pov_reel` → `src/video/remotion_reel.py::generate_remotion_reel` writes `remotion/public/reel-data.json` → `npx remotion render PovReel` produces a deterministic MP4. No AI in the render loop — AI is *upstream* (studio agents write hook/quote/cta text). The React composition (`remotion/src/PovReel.tsx`, 431 lines + 14 scene components + 9 lib helpers + 6 test files) supports:

- 4 scenes: Hook → [Bridge] → Quote → CTA, with `sceneFrames` timing math
- 7 mood palettes (`remotion/src/styles/theme.ts`)
- Word-by-word VO timing (`wordTimes` → spring reveals)
- Multi-clip cinematic backgrounds (Pexels), FilmGrade + ColorGrade, ParticleField, GradientBg, breathing vignette
- AnimatedText, GlitchText, cameraZoom, emphasis, silence_drop, duckVolume, animSeed
- Fallback: Remotion → ffmpeg POV generator (if Node/Remotion missing)

The pipeline auto-posts daily via GitHub Actions cron.

### What HyperFrames is

HeyGen HyperFrames (`github.com/heygen-com/hyperframes`, Apache-2.0) is **both** an npm CLI (`npx hyperframes init/preview/render` — non-interactive by default, CI-friendly) **and** a set of agent skills (`/hyperframes`, `/faceless-explainer`, `/remotion-to-hyperframes`, etc.). It renders plain HTML + `data-*` timing attrs + seek-safe animations (GSAP/CSS) → headless Chrome → FFmpeg → MP4. Deterministic ("same input, same frames, same output"). No React, no bundler — `index.html` plays as-is. Requires Node 22+ (satisfied: v22.23.1) and FFmpeg (satisfied: 7.1.1).

### Critical distinction

HyperFrames can be driven two ways:

- **(A) Deterministic CLI mode** — Python generates HTML, `npx hyperframes render` produces a deterministic MP4. $0/render. Cron-safe. **This is the daily-cron path.**
- **(B) Agent-driven mode** — Claude Code runs the `/hyperframes` skill per reel; AI writes fresh HTML/GSAP each time. ~$/render (tokens). Not cron-safe. **This is the studio/hero-reel path.**

This design uses both: (A) for daily cron, (B) for hero reels.

## Architecture overview

Two render paths coexist. Only the deterministic path is cron-driven; the studio path is human-triggered.

```
                        Socrates reel pipeline
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
        DETERMINISTIC PATH                   AGENT-DRIVEN STUDIO PATH
        (daily cron, --renderer flag)         (hero reels, manual trigger)
                  │                                   │
   pipeline.py _run_pov_reel                   scripts/studio_render.py
     ├─ VO (ElevenLabs/edge-tts)                ├─ builds /hyperframes prompt
     ├─ Jamendo music                           │   from quote_data + mood
     ├─ Pexels multi-clip bg                    ├─ shells out: claude --print
     │                                          │   with /hyperframes skill
     └─ renderer branch:                       ├─ agent writes HTML + GSAP
        ├─ hyperframes (new)                    │   per reel (non-deterministic)
        │   1. render Jinja2 template           │
        │   2. inline reel data + CSS vars       └─ output/studio_*.mp4
        │   3. npx hyperframes render
        │      → headless Chrome → FFmpeg → MP4
        └─ fallback chain:
            hyperframes → Remotion → ffmpeg POV

   SHARED: src/video/hyperframes_reel.py (Python bridge, sibling to remotion_reel.py)
           hyperframes/ composition project (templates, css, js, tests)
```

**Key properties:**

- **Deterministic path** = Python generates a self-contained `index.html` from Jinja + inlined reel data → `npx hyperframes render`. Same input → same MP4. $0/render. Cron-safe. Activated by `--renderer hyperframes`.
- **Studio path** = `scripts/studio_render.py` shells out to `claude --print` running the `/hyperframes` skill with a prompt built from quote_data/mood. AI writes fresh HTML/GSAP per reel. ~$/render (tokens). Not cron-safe. Output lands in `output/studio_*.mp4`, separate from the daily numbered reels.
- **Fallback chain (deterministic path only)**: HyperFrames fails → Remotion runs → Remotion fails → ffmpeg POV generator. Remotion stays installed throughout C2/C3; only C1 deletes it.
- **Studio path has no fallback** — a failed agent run exits non-zero with the transcript saved for debugging. Studio reels are one-off creative work; a fallback to deterministic would defeat the point.

## Repo layout

The `hyperframes/` composition project sits as a sibling to `remotion/` at the repo root. Python bridge files live in `src/video/` next to `remotion_reel.py`.

```
socrates automation/
├── remotion/                          # EXISTING — stays through C2/C3, deleted at C1
│   └── ... (unchanged during migration)
│
├── hyperframes/                        # NEW — the HyperFrames composition project
│   ├── package.json                   # hyperframes, gsap, vitest devDeps
│   ├── hyperframes.config.ts          # render config (fps, 1080×1920, codec)
│   ├── templates/
│   │   ├── index.html.j2              # root: <html>, <head>, GSAP/Timeline imports,
│   │   │                              #   inlined reel-data <script json>, scene partials
│   │   └── scenes/
│   │       ├── hook.j2
│   │       ├── bridge.j2              # optional, rendered only when bridge set
│   │       ├── quote.j2
│   │       └── cta.j2
│   ├── css/
│   │   ├── moods.css                  # 7 mood palettes as CSS vars (ports theme.ts)
│   │   ├── scenes.css                 # per-scene layout/typography
│   │   └── effects.css                # particle/gradient/vignette base styles
│   ├── js/
│   │   ├── lib/                       # PURE FUNCTIONS — ported from remotion/src/lib
│   │   │   ├── sceneFrames.ts         #   scene timing math (returns seconds, not frames)
│   │   │   ├── wordAt.ts              #   word→time lookup
│   │   │   ├── cameraZoom.ts          #   zoom curve
│   │   │   ├── emphasis.ts           #   emphasis classification
│   │   │   ├── duckVolume.ts         #   music-ducking curve
│   │   │   └── getGrade.ts           #   mood→grade lookup (EXTRACTED from remotion/src/styles/theme.ts)
│   │   ├── scenes/                    # GSAP timelines, one per scene
│   │   │   ├── hook.ts
│   │   │   ├── bridge.ts
│   │   │   ├── quote.ts
│   │   │   └── cta.ts
│   │   ├── effects/                   # Tier 2 GSAP modules
│   │   │   ├── particleField.ts       #   3-tint drift
│   │   │   ├── filmGrade.ts           #   FilmGrade equivalent
│   │   │   ├── colorGrade.ts          #   ColorGrade equivalent
│   │   │   ├── glitchText.ts          #   pattern-interrupt flash
│   │   │   └── gradientBg.ts          #   breathing radial gradient
│   │   └── index.ts                   # wires timelines → master seek-safe timeline
│   ├── tests/                         # 6 ported lib test files (9 describe blocks)
│   │   ├── sceneFrames.test.ts
│   │   ├── wordAt.test.ts
│   │   ├── cameraZoom.test.ts
│   │   ├── emphasis.test.ts
│   │   ├── duckVolume.test.ts
│   │   └── getGrade.test.ts
│   └── out/                           # rendered MP4s (gitignored)
│
├── src/video/
│   ├── remotion_reel.py               # EXISTING — unchanged
│   └── hyperframes_reel.py            # NEW — Python bridge (B2 contract)
│       ├─ render_jinja(reel_data) → index.html
│       ├─ invoke `npx hyperframes render` headless
│       └─ returns mp4 path or None (→ Remotion fallback)
│
├── scripts/
│   └── studio_render.py               # NEW — H2 studio mode
│       ├─ build_hyperframes_prompt(quote_data, mood)
│       ├─ shell out: `claude --print` with /hyperframes skill
│       └─ output/studio_*.mp4
│
├── pipeline.py                        # MODIFIED — add --renderer flag, route in _run_pov_reel
└── docs/superpowers/
    ├── specs/
    │   └── 2026-07-27-hyperframes-migration-design.md   # this spec
    └── hyperframes-runbook.md         # NEW — setup + cron + studio + phase-promotion runbook
```

**Notes:**

- `hyperframes/` mirrors `remotion/`'s role but is plain HTML+GSAP, no React/bundler. `index.html` "plays as-is" (HyperFrames' no-build-step property).
- `js/lib/` ports the 6 pure-function modules from `remotion/src/lib/`. The "9 tests" count covers 6 test files (some have multiple describe blocks). Tests move to `hyperframes/tests/`.
- The Jinja templates render at *Python runtime* (not at `npx hyperframes render` time) — by the time HyperFrames sees it, `index.html` is fully baked with inlined data and CSS vars for the chosen mood.
- `out/` gitignored (same as `remotion/out/`).
- No changes to `remotion/` during C2 — it is frozen as the comparison baseline.

## Deterministic path data flow

End-to-end contract for one cron reel rendered via HyperFrames. This is what `--renderer hyperframes` activates inside `_run_pov_reel`.

```
1. pipeline.py _run_pov_reel(renderer="hyperframes")
      │
      ├─ Build quote_data as today (hook/quote/cta/bridge, mood, word_times)
      ├─ Generate VO (ElevenLabs → edge-tts fallback), Jamendo music, Pexels clips
      │   — IDENTICAL to current Remotion path, no changes upstream
      │
2. src/video/hyperframes_reel.py  generate_hyperframes_reel(...)
      │
      ├─ Assemble reel_data dict — SAME shape Remotion reads today:
      │     {hook, quote, attribution, cta, bridge?, mood, duration, fps,
      │      animSeed, beats, voices, voiceDurations, wordTimes,
      │      background?, backgrounds?, silence_drop_sec}
      │
      ├─ render_jinja(reel_data, mood) → hyperframes/index.html
      │     │  - load index.html.j2 + scene partials (bridge partial only if bridge set)
      │     │  - inline reel_data as <script type="application/json" id="reel-data">…</script>
      │     │  - set <html data-mood="dark_philosophical"> + CSS var block from moods.css
      │     │  - resolve bg paths to file:// URIs (Pexels clips / FLUX image)
      │     │  - emit self-contained index.html (no fetch, no network at render)
      │     │
      ├─ Invoke:  npx hyperframes render --config hyperframes.config.ts
      │     cwd=hyperframes/, env inherited, capture stdout/stderr
      │     - headless Chrome seeks each frame per data-start/data-duration attrs
      │     - FFmpeg encodes → out/reel_<counter:03d>.mp4
      │     - deterministic: same index.html → byte-identical MP4
      │
      ├─ On success: return Path("hyperframes/out/reel_NNN.mp4")
      ├─ On failure (non-zero exit, timeout, missing output): log warning, return None
      │
3. pipeline.py
      ├─ if reel_path is not None: post to Instagram (same as today)
      └─ if reel_path is None: fall through to Remotion → ffmpeg POV (existing chain)
```

**Key contract points:**

- **One source of truth for reel data.** `hyperframes_reel.py` builds the *same* dict `remotion_reel.py` builds — no schema drift. Enforced by a shared dict builder (see "Shared reel-data builder" under Error handling).
- **Jinja renders at Python runtime, not render time.** HyperFrames never sees Jinja — it sees a fully baked `index.html`. This keeps the render command trivial and the HTML self-contained.
- **`data-mood` attribute on `<html>`** is the single mood switch. `moods.css` uses `[data-mood="dark_philosophical"] { --bg: ...; --text: ...; }`. No JS needed to pick the palette.
- **Backgrounds resolved to `file://` URIs** in the Jinja render (Pexels multi-clip or single FLUX image). HyperFrames' headless Chrome loads them locally — no network, no CI sandbox breakage.
- **Determinism guarantee:** the render is a pure function of `index.html`. For shadow tests, hash the rendered MP4 and compare across runs — same hash expected.
- **Fallback is the Python bridge's job**, not HyperFrames'. `hyperframes_reel.py` returns `None` on any failure; `pipeline.py`'s existing fallback chain catches it.
- **Concurrency:** only one `npx hyperframes render` runs per cron slot (slots are serial). If parallelization is ever added, the bridge writes to a unique temp dir per render to avoid `index.html` clobbering.

## Scene composition + GSAP timing model

How HyperFrames' clip/timing model reproduces the Remotion composition.

**HyperFrames' model:** the `index.html` is a set of `class="clip"` elements with `data-start` (seconds), `data-duration`, `data-track-index` attrs. Audio in `<audio>` elements. Animations must be **seek-safe** — the timeline is paused and HyperFrames seeks to each frame's timestamp, so animations must render correctly at *any* arbitrary `t`. GSAP timelines support this natively via `tl.seek(t)`.

**The 4 scenes as clips on one master timeline:**

```
track 0 (bg):     ┌──────────────────────────────────────────────────┐
                  │  background clip(s) — full reel duration           │
                  └──────────────────────────────────────────────────┘
track 1 (hook):   ┌────────────┐
                  │ Hook clip   │  data-start=0  data-duration=hookDur
                  └────────────┘
track 2 (bridge):            ┌────────────┐  (only if bridge set)
                            │ Bridge     │  data-start=hookDur
                            └────────────┘
track 3 (quote):                       ┌────────────┐
                                       │ Quote      │  data-start=hookDur+bridgeDur+silenceDrop
                                       └────────────┘
track 4 (cta):                                 ┌────────────┐
                                               │ CTA        │  data-start=…+quoteDur
                                               └────────────┘
track 5 (audio):  <audio> VO per scene + Jamendo music bed (ducked)
```

**Timing math comes from the ported `sceneFrames.ts`:** the *same* function Remotion uses (`sceneFrames(duration, fps, voiceDurations, hasBridge, hasHook)`) returns `{hook, bridge, quote, cta, total}` frame counts. Ported to `hyperframes/js/lib/sceneFrames.ts`, returns seconds instead of frames (HyperFrames is seconds-based), and the Jinja template bakes those `data-start`/`data-duration` values into each clip at render time. One timing function, two renderers — parity by construction.

**Word-by-word VO timing → seek-safe keyframes:**

- `wordAt.ts` (ported) maps each word to `[start, end]` from the VO SRT
- Each scene's GSAP timeline (`js/scenes/hook.ts` etc.) builds a paused master timeline:
  ```ts
  const tl = gsap.timeline({ paused: true });
  words.forEach((w, i) => {
    tl.fromTo(`#hook-word-${i}`, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: w.end - w.start }, w.start);
  });
  // HyperFrames seeks: tl.seek(t) per frame
  ```
- HyperFrames calls a global `seek(t)` function per frame (the HyperFrames contract); `js/index.ts` routes `t` to each scene's `tl.seek(t)`.

**Tier 2 effects as layered GSAP timelines** (each in `js/effects/`, seek-safe):

- `gradientBg.ts` — breathing radial-gradient on `--bg` vars, phase driven by `t`
- `particleField.ts` — 3-tint particles drifting upward, deterministic positions from `animSeed`
- `filmGrade.ts` / `colorGrade.ts` — CSS filter chains on an overlay layer, mood-driven via `getGrade.ts`
- `glitchText.ts` — pattern-interrupt flash on the hook's stressed word, `beats`-driven
- `cameraZoom.ts` — slow zoom on bg clip, curve from ported `cameraZoom.ts`

**`silence_drop` (0.8s before quote):** baked into `data-start` of the quote clip by `sceneFrames.ts` (ported to add the drop when a quote VO exists). No special GSAP logic.

**`animSeed` (row_number):** passed to `particleField.ts` and `cameraZoom.ts` as a seeded PRNG so the same row produces the same variation — determinism across reels and across renderers.

**HyperFrames lint gate:** HyperFrames' CLI runs `lint` before `render` (part of its 7-step). The composition must pass `data-*` validity checks (every `class="clip"` has `data-start`/`data-duration`, audio tracks declared, no seek-unsafe animations like wall-clock `requestAnimationFrame`). This is a built-in regression gate the React path doesn't have — a net win.

## Mood system (CSS vars from `theme.ts`)

The 7-mood palette port. `remotion/src/styles/theme.ts` defines a `Palette` per mood with `{bg[3], text, stroke, accent, glow, particles[3], dark}`. These become CSS custom properties on `[data-mood="…"]` selectors.

**`hyperframes/css/moods.css`** (one block per mood, mirrors `MOOD_PALETTES` exactly):

```css
[data-mood="dark_philosophical"] {
  --bg-outer: #0a0805; --bg-core: #2a1f12; --bg-outer2: #0a0805;
  --text: #f5f0e8; --stroke: #000000; --accent: #c9a96e;
  --glow: <mood glow>; --particle-1: …; --particle-2: …; --particle-3: …;
  --is-dark: 1;
}
[data-mood="dramatic_ancient"] { … }
/* …7 moods total */
```

**Rules:**

- **One file, seven blocks.** `moods.css` is the *only* place colors live. Scenes/effects reference `var(--text)`, `var(--accent)`, etc. — never hardcoded hex. A mood switch (`<html data-mood="…">`) re-skins every scene and every effect atomically.
- **Generated, not hand-typed.** To eliminate transcription drift between `theme.ts` and `moods.css`, a one-shot generator (`scripts/sync_moods.py`) reads `theme.ts`'s `MOOD_PALETTES` and emits `moods.css`. Run once at port time, re-run if `theme.ts` ever changes (rare). Checked in. This is the parity guarantee for color.
- **`--is-dark` as a number (1/0)** drives text-shadow direction and particle opacity — replaces the React `dark: boolean` field. Effects branch on `var(--is-dark)`.
- **`getGrade.ts` (ported)** maps mood → `filmGrade`/`colorGrade` parameters; the grade effects read CSS vars *and* the mood's grade params, so a mood change re-grades correctly without JS logic.
- **No runtime JS to pick a mood.** The mood is set by `data-mood` on `<html>`, written by Jinja at render time. Pure CSS cascade. Matches HyperFrames' "static HTML, seek-safe animations" model — no `if (mood === …)` branches in GSAP.

**Parity check:** during shadow tests, the mood palette comparison is automated — a script extracts dominant colors from both renderers' first frame per mood and diffs them. Any drift > tolerance flags a `moods.css` re-sync.

## The 9 lib tests (TDD port, first build step)

The build's step 1: port the lib tests *before* any DOM.

**Current tests in `remotion/src/lib/` (and `remotion/src/styles/`):**

| Test file | Tests | What it covers | Ports to |
|---|---|---|---|
| `sceneFrames.test.ts` (in `lib/`) | scene timing math: hook/bridge/quote/cta/total frame counts given duration, fps, voiceDurations, hasBridge, hasHook | The clip `data-start`/`data-duration` values | `hyperframes/tests/sceneFrames.test.ts` — return seconds instead of frames |
| `wordAt.test.ts` (in `lib/`) | word → `[start,end]` lookup from VO SRT | Word-by-word GSAP keyframe placement | `hyperframes/tests/wordAt.test.ts` — verbatim port |
| `cameraZoom.test.ts` (in `lib/`) | zoom curve over scene duration | `cameraZoom.ts` bg zoom | `hyperframes/tests/cameraZoom.test.ts` — verbatim, but replace `remotion`'s `interpolate` with an inline `lerp`/`clamp` helper (no `remotion` package in `hyperframes/`) |
| `emphasis.test.ts` (in `lib/`) | word emphasis classification (plain/stress/etc.) | `glitchText` target word | `hyperframes/tests/emphasis.test.ts` — verbatim |
| `duckVolume.test.ts` (in `lib/`) | music-ducking curve under VO | `<audio>` music bed volume timeline | `hyperframes/tests/duckVolume.test.ts` — verbatim |
| `getGrade.test.ts` (in `styles/`, imports from `../styles/theme`) | mood → grade params lookup | `filmGrade`/`colorGrade` | `hyperframes/tests/getGrade.test.ts` — verbatim, but **extract** `getGrade` from `remotion/src/styles/theme.ts` (line 141) into its own `hyperframes/js/lib/getGrade.ts` module; the test import changes from `../styles/theme` to `../lib/getGrade` |

(6 test files covering 6 lib modules — the "9" counts multiple describe blocks within `cameraZoom.test.ts` and `emphasis.test.ts` in the current suite. Every assertion preserved.)

**TDD ordering:**

1. **Port `sceneFrames.ts` + its test first.** The timing spine — every clip's `data-start`/`data-duration` depends on it. Test runs red (no module) → implement → green. *Only* conversion change: return seconds (HyperFrames is seconds-based) not frames (Remotion is frames-based). Keep a `toFrames(sec, fps)` helper so the test can compare against the Remotion expected values during port, then drop it.
2. **Port `wordAt.ts` + test.** Verbatim — no unit change.
3. **Port `cameraZoom.ts`, `emphasis.ts`, `duckVolume.ts` + tests.** Verbatim ports — pure functions, no renderer dependency — except `cameraZoom.ts` which imports `interpolate` from `remotion`; replace with an inline `lerp`/`clamp` helper (no `remotion` package in `hyperframes/`).
4. **Extract `getGrade` from `remotion/src/styles/theme.ts` into `hyperframes/js/lib/getGrade.ts` + port its test.** The test currently imports `getGrade` from `../styles/theme`; the port imports from `../lib/getGrade`. Verbatim otherwise.
5. **Then** Tier 1 skeleton, **then** Tier 2 polish.

**Why this ordering matters:** `sceneFrames` and `wordAt` are the timing contract. If they're wrong, every clip and every word animation is wrong — discovered only at render time (slow feedback). Porting tests first gives a sub-second red/green loop on the math before any GSAP exists.

**Test runner:** vitest (already a devDep in `remotion/package.json`; reuse in `hyperframes/package.json`). `npm test` in `hyperframes/` runs all 6 test files. Runs in CI on every PR — a gate the React path didn't have at build time.

**Shadow-test parity assertion:** the *same* `sceneFrames` test expected values (converted to seconds) are asserted against both the ported module AND the Remotion module's output (via a small Node script that imports `remotion/src/lib/sceneFrames.ts` and compares). If the port drifts, the test fails. Mathematical parity guarantee — not just visual.

## CLI flag, fallback chain, shadow tests

### CLI flag (C2 wiring)

`pipeline.py` gains one new flag, parallel to `--remotion`:

```
--renderer {remotion,hyperframes,ffmpeg}   # default: remotion (C2)
```

- `--renderer remotion` → current behavior (default through C2/C3)
- `--renderer hyperframes` → calls `generate_hyperframes_reel()`, falls back to Remotion → ffmpeg POV on `None`
- `--renderer ffmpeg` → skips both, goes straight to ffmpeg POV (useful for offline tests)
- `--remotion` (existing flag) stays as an alias for `--renderer remotion` for back-compat

Inside `_run_pov_reel`, the renderer branch becomes a small dispatch:

```python
renderer = cfg.renderer  # "remotion" | "hyperframes" | "ffmpeg"
if renderer == "hyperframes":
    from src.video.hyperframes_reel import generate_hyperframes_reel
    reel_path = generate_hyperframes_reel(...)
    if reel_path is None:
        log.warning("[hyperframes] failed → falling back to Remotion")
        # fall through to remotion path below
if reel_path is None and renderer != "ffmpeg":
    # existing Remotion path (unchanged)
    reel_path = generate_remotion_reel(...)
if reel_path is None:
    # existing ffmpeg POV fallback (unchanged)
```

No other `pipeline.py` changes — VO/music/bg generation upstream is identical.

### Fallback chain (deterministic path only)

```
--renderer hyperframes:
   generate_hyperframes_reel() ──ok──→ post
        │ fail (None)
        └──→ generate_remotion_reel() ──ok──→ post
                  │ fail (None)
                  └──→ ffmpeg POV generator ──ok──→ post
                            │ fail
                            └──→ skip slot, log, alert (existing behavior)

--renderer remotion (default C2): Remotion → ffmpeg POV (unchanged today)
--renderer ffmpeg: straight to ffmpeg POV
```

Studio path (`scripts/studio_render.py`) has **no fallback** — exit non-zero, save transcript.

### Shadow tests (C2 phase)

"Shadow test" = render the *same* reel through both HyperFrames and Remotion, compare, don't post the HyperFrames one. Mechanism:

**New script: `scripts/shadow_test.py`** — runs on a single reel:

1. Generate reel data once (hook/quote/cta/bridge, VO, music, bg) — the shared upstream work.
2. Render via Remotion → `output/shadow/remotion_NNN.mp4`
3. Render via HyperFrames → `output/shadow/hyperframes_NNN.mp4`
4. Compare:
   - **Duration parity:** `ffprobe` both, assert `<50ms` diff
   - **First/middle/last frame parity:** `ffmpeg -ss` extracts 3 frames each, `pixelmatch` diffs them, log per-frame diff %; tolerance: ≤ 5% pixel diff per sampled frame (after exact-duration match)
   - **Color parity per mood:** extract dominant colors, diff vs `moods.css` expected (catches `theme.ts`↔`moods.css` drift); tolerance: dominant-color channel diff ≤ 8/255 per channel
   - **Audio parity:** `ffprobe` audio streams match (VO + music bed levels)
5. Write `output/shadow/report_NNN.json` with metrics + side-by-side frame PNGs.
6. Post nothing — shadow output is local-only.

**Cron cadence during C2:** the daily cron runs `--renderer remotion` (default, posts to Instagram as today) **plus** a second non-posting shadow run via `scripts/shadow_test.py` on the same reel data. Review `output/shadow/report_NNN.json` each day for a few days. This is the "few days of parallel compare" specified.

**Phase gate to C3:** HyperFrames shadow report shows (a) zero render failures, (b) frame diff within tolerance (≤ 5% per sampled frame), (c) duration parity (< 50ms), (d) color parity per mood (≤ 8/255 per channel) — for N consecutive days (default 5). Then flip the default in `pipeline.py` to `--renderer hyperframes`.

## Studio mode (`scripts/studio_render.py`, H2)

The agent-driven hero-reel path. Human-triggered, never cron. Shells out to `claude --print` with the `/hyperframes` skill installed.

### Invocation

```bash
.venv/bin/python scripts/studio_render.py \
  --content '{"hook":"...","quote":"...","cta":"...","mood":"dark_philosophical"}' \
  --vibe "dark cinematic, Netflix-investigation opening" \
  --workflow faceless-explainer \
  --out output/studio_001.mp4
```

- `--content` accepts the same JSON shape `pipeline.py --content` uses (reuses the existing loader) — no new contract.
- `--vibe` is free text appended to the agent prompt (the tutorial's "vibe" lever).
- `--workflow` picks a `/hyperframes` sub-skill (`faceless-explainer`, `motion-graphics`, `music-to-video`, etc.). Default: `faceless-explainer`.
- `--out` output path. Default: `output/studio_<timestamp>.mp4`.

### What the script does

1. **Load + validate** `--content` JSON (same validator `pipeline.py` uses) → `quote_data`.
2. **Build the prompt:**
   ```
   Using hyperframes and /<workflow>, create a <duration>-second <vibe> reel
   from this philosophy content:
     hook: "..."
     quote: "..."
     attribution: "— Socrates"
     cta: "..."
     mood: dark_philosophical (use this palette: bg #0a0805/#2a1f12, text #f5f0e8, accent #c9a96e)
   Render to <out>.
   ```
   The mood palette is injected from `theme.ts` (read at script runtime) so the agent's HTML matches the brand palette — no off-brand free-styling.
3. **Shell out:**
   ```python
   result = subprocess.run(
       ["claude", "--print", "--allowedTools", "Bash,Read,Write,Edit",
        prompt],
       cwd=str(REPO_ROOT / "hyperframes_studio"),  # isolated workdir
       capture_output=True, text=True, timeout=1800,  # 30min cap
   )
   ```
   - **Isolated workdir** (`hyperframes_studio/`, gitignored): the agent writes HTML/GSAP here, never touches `hyperframes/` (deterministic templates) or `remotion/`. Clean slate per run.
   - **30-min timeout** — agent runs are slow; cap prevents runaway.
4. **Locate output:** the agent writes the MP4 to the path in the prompt. Script verifies the file exists, `ffprobe`s it's a valid MP4, moves to `--out`.
5. **On failure:** exit non-zero, dump `result.stdout` + `result.stderr` to `output/studio_<timestamp>_transcript.txt` for debugging. No fallback.

### Dependencies

- **`claude` CLI on PATH** with the `/hyperframes` skill installed (`npx skills add heygen-com/hyperframes`). The script's `--help` checks for `claude` and the skill; exits with install instructions if missing.
- **One-time skill install** documented in the runbook. Not auto-installed — installing a skill is a user decision, not a script's job.

### What it deliberately does NOT do

- **No cron wiring.** Studio mode is never invoked by `pipeline.py` or GitHub Actions. Manual only.
- **No fallback to deterministic.** A failed agent run doesn't silently produce a Remotion reel — that would hide bugs and defeat the creative intent.
- **No posting.** Output stays in `output/studio_*` for manual review and posting.
- **No `pipeline.py` changes.** Studio mode is a sibling script; the cron pipeline is untouched.

## Migration ladder, error handling, testing, runbook

### Migration ladder + phase gates

| Phase | Default renderer | `remotion/` status | Shadow testing | Exit gate to next phase |
|---|---|---|---|---|
| **C2 — Additive** | `remotion` | Frozen, unchanged | `scripts/shadow_test.py` runs daily on same reel; review `output/shadow/report_NNN.json` | N consecutive days (default 5) with: zero HyperFrames render failures, frame diff within tolerance, duration parity, color parity per mood |
| **C3 — Flip default** | `hyperframes` | Kept as fallback | Shadow tests continue but now Remotion is the *shadow* (renders for compare, not post) | "Few weeks" (default 3) of stable HyperFrames production with **zero** fallback triggers to Remotion (logged in `logs/notifications.jsonl`) |
| **C1 — Deprecate** | `hyperframes` | `remotion/` deleted; `--renderer remotion` flag removed; `src/video/remotion_reel.py` deleted; fallback chain becomes `hyperframes → ffmpeg POV` | Shadow tests retired (no baseline to compare) | One-time deletion commit; CI passes without `remotion/` |

Each phase gate is **logged** (`logs/migration_phase.log`): when the gate fires, the script writes a timestamped entry with the metrics that justified the transition. Reviewed before manually flipping the default — no automatic phase promotion.

### Error handling (cross-cutting)

**Deterministic path (`hyperframes_reel.py`):**

- `npx hyperframes render` non-zero exit → log stderr, return `None` → Remotion fallback
- Render timeout (cap: 10 min per reel) → kill process, return `None` → fallback
- Missing `index.html` / missing output MP4 → return `None` → fallback
- Jinja render error → log, return `None` → fallback (rare; means template bug)
- All failures log to `logs/notifications.jsonl` (existing channel) with `[hyperframes]` tag — same place Remotion failures already log

**Studio path (`studio_render.py`):**

- `claude` not on PATH → exit non-zero with install instructions
- `/hyperframes` skill not installed → exit non-zero with install command
- Agent timeout (30 min) → kill, save transcript, exit non-zero
- Output MP4 invalid/missing → save transcript, exit non-zero
- No fallback, no retry — surface the failure for human review

**Studio workdir cleanup:** `hyperframes_studio/` is gitignored; the script writes a fresh `index.html` per run but leaves prior runs for debugging. A `--clean` flag clears it; otherwise it grows (one-time manual cleanup, same as `output/`).

**Shared reel-data builder:** to enforce the "one source of truth" contract, `hyperframes_reel.py` and `remotion_reel.py` both call a shared builder (`src/video/reel_data.py::build_reel_data(...)`) that returns the canonical dict. Adding a field in one place flows to both renderers. (This is a small refactor of the existing `remotion_reel.py` builder into a shared module — done as part of the C2 wiring, not a separate effort.)

### Testing strategy

| Layer | What | Runner | When |
|---|---|---|---|
| **Unit (lib)** | 6 ported lib test files, 9 describe blocks | `vitest` in `hyperframes/` | Every PR (CI) — `npm test` |
| **Unit (Python bridge)** | `tests/test_hyperframes_reel.py` — Jinja render produces valid HTML, correct `data-mood`, inlined JSON parseable, bg URIs resolved, `sceneFrames` seconds match expected | `pytest` (existing venv) | Every PR |
| **Integration** | `tests/test_renderer_dispatch.py` — `--renderer hyperframes` routes correctly, fallback chain fires on mock failure | `pytest` | Every PR |
| **Shadow compare** | `scripts/shadow_test.py` produces `report_NNN.json` | Manual / daily cron during C2 | During C2 phase only |
| **CI smoke** | GitHub Actions job renders one fixture reel via HyperFrames, asserts valid MP4 produced | GH Actions | Every PR (cap: 10 min) |

The CI smoke job reuses the existing `pipeline-db-*` cache pattern — no new infra. It uses `--renderer hyperframes` on a fixture `--content` JSON, asserts `output/reel_001.mp4` exists and `ffprobe` says it's valid. No posting.

### Runbook (`docs/superpowers/hyperframes-runbook.md`)

One doc, four sections:

1. **One-time setup** — `npx skills add heygen-com/hyperframes --full-depth` (for studio mode); `npm install` in `hyperframes/`; Node 22+/ffmpeg already satisfied.
2. **Daily cron (C2)** — no manual action; shadow reports land in `output/shadow/`.
3. **Studio mode** — how to run `scripts/studio_render.py`, when to use which `--workflow`, where output lands.
4. **Phase promotion** — how to review the gate log, flip the default in `pipeline.py`, the deletion steps for C1.

## Build order (TDD, as specified)

1. Port `sceneFrames.ts` + test (seconds, not frames)
2. Port `wordAt.ts` + test
3. Port `cameraZoom.ts` (inline `lerp`/`clamp`, no `remotion` dep), `emphasis.ts`, `duckVolume.ts` + tests
4. Extract `getGrade` from `remotion/src/styles/theme.ts` into `hyperframes/js/lib/getGrade.ts` + port its test (import changes `../styles/theme` → `../lib/getGrade`)
5. Generate `moods.css` from `theme.ts` via `scripts/sync_moods.py`
6. Tier 1 skeleton: `index.html.j2` + 4 scene partials + `moods.css` + `scenes.css` + basic GSAP timing (no Tier 2)
7. Extract shared reel-data builder `src/video/reel_data.py::build_reel_data(...)` from `remotion_reel.py` (no behavior change to Remotion path)
8. `src/video/hyperframes_reel.py` bridge (calls shared builder) + `--renderer hyperframes` flag in `pipeline.py`
9. `tests/test_hyperframes_reel.py` + `tests/test_renderer_dispatch.py` + CI smoke job
10. `scripts/shadow_test.py` + begin C2 shadow runs
11. Tier 2 polish: port `particleField`, `gradientBg`, `filmGrade`, `colorGrade`, `glitchText`, `cameraZoom` as seek-safe GSAP timelines
12. `scripts/studio_render.py` (studio mode — can land any time after step 8, independent of shadow phase)

## Out of scope (YAGNI)

- Porting the Sentry ErrorBoundary (currently intentionally disabled in Remotion — no equivalent needed)
- HyperFrames cloud rendering / AWS Lambda (local render is fine for one reel/day)
- The `/remotion-to-hyperframes` *agent workflow* (porting by hand with tests is more deterministic for a bespoke 7-mood reel)
- HyperFrames registry blocks (Approach C, rejected)
- Per-reel parallelization (cron slots are serial)

## Reference

- HyperFrames repo: `https://github.com/heygen-com/hyperframes`
- Install (studio mode skill): `npx skills add heygen-com/hyperframes --full-depth`
- Tutorial walked through during brainstorm: Sabrina Ramonov, "AI Agent Makes Unlimited Free Videos (Hyperframes Tutorial)", Jul 04 2026
- Current Remotion path: `remotion/src/PovReel.tsx`, `src/video/remotion_reel.py`, `remotion/public/reel-data.json`
- Theme: `remotion/src/styles/theme.ts` → ports to `hyperframes/css/moods.css`
- Lib tests: `remotion/src/lib/*.test.ts` → port to `hyperframes/tests/`