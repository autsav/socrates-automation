# HyperFrames Runbook

> **Status:** C2 (additive, shadow-testing phase)  
> **Date:** 2026-07-28  
> **Owner:** Socrates IG Pipeline

---

## 1. One-time setup

### 1.1 Install Node dependencies

```bash
cd hyperframes && npm install
```

Verify:
```bash
cd hyperframes && npx hyperframes --version
```

### 1.2 Install studio skill (optional — for hero reels only)

```bash
npx skills add heygen-com/hyperframes --full-depth
```

Restart Claude Code after skill install so `/hyperframes` is available.

### 1.3 Verify FFmpeg

HyperFrames bundles its own FFmpeg, but the Python bridge uses system `ffprobe`:
```bash
ffprobe -version | head -1
```

---

## 2. Daily cron (C2)

No manual action. The GitHub Actions cron runs:

```bash
.venv/bin/python pipeline.py --reel --renderer remotion
```

This is the **default** — HyperFrames is opt-in. To test HyperFrames on a single run:

```bash
.venv/bin/python pipeline.py --reel --renderer hyperframes --manual
```

The `--manual` flag skips Instagram posting so you can review the output locally.

### Fallback chain

```
--renderer hyperframes
   └─ HyperFrames fails ──→ Remotion ──→ ffmpeg POV
--renderer remotion (default)
   └─ Remotion fails ──→ ffmpeg POV
--renderer ffmpeg
   └─ Straight to ffmpeg POV
```

Any failure logs to `logs/notifications.jsonl` with `[hyperframes]` tag.

---

## 3. Shadow testing

During C2, run shadow tests to compare HyperFrames vs Remotion parity:

```bash
.venv/bin/python scripts/shadow_test.py \
  --content '{"hook":"This changed me.","quote":"Know thyself.","cta":"Save this.","mood":"dark_philosophical"}'
```

Output lands in `output/shadow/`:
- `report_NNN.json` — duration diff, frame diff %, color diff
- `remotion_first.png` / `hyperframes_first.png` — side-by-side frames

### Phase-gate tolerances (Task 14)

| Metric | Tolerance | Notes |
|---|---|---|
| Duration | < 50ms | ffprobe both MP4s |
| Frame diff | ≤ 5% | pixelmatch on 3 sampled frames |
| Color diff | ≤ 8/255 per channel | dominant-color extraction |
| Shadow streak | 5 days | Zero failures + all tolerances met |

When the 5-day streak passes, flip the default in `pipeline.py`:
```python
parser.add_argument("--renderer", choices=["remotion", "hyperframes", "ffmpeg"],
                    default="hyperframes", ...)
```

---

## 4. Studio mode (hero reels)

Manual only — never cron. Use for one-off creative explorations.

```bash
.venv/bin/python scripts/studio_render.py \
  --content '{"hook":"...","quote":"...","cta":"...","mood":"dark_philosophical"}' \
  --vibe "dark cinematic, Netflix-investigation opening" \
  --workflow faceless-explainer \
  --out output/studio_001.mp4
```

### Parameters

| Flag | Default | Description |
|---|---|---|
| `--content` | required | Same JSON shape as `pipeline.py --content` |
| `--vibe` | "cinematic philosophy reel" | Free-text appended to agent prompt |
| `--workflow` | `faceless-explainer` | `/hyperframes` sub-skill |
| `--out` | `output/studio_<timestamp>.mp4` | Output path |
| `--clean` | false | Wipe `hyperframes_studio/` before run |

### What it does

1. Builds prompt from content + mood palette + vibe
2. Shells out: `claude --print --allowedTools Bash,Read,Write,Edit <prompt>`
3. Agent writes HTML/GSAP in `hyperframes_studio/` (isolated)
4. Agent renders MP4 to `--out`
5. Script verifies MP4 exists + ffprobe-valid

### On failure

- Exit non-zero
- Transcript saved to `output/studio_<timestamp>_transcript.txt`
- **No fallback** — a failed agent run doesn't silently produce a Remotion reel

---

## 5. Phase promotion

### C2 → C3 (flip default)

Prerequisites:
- [ ] 5 consecutive days of shadow reports within tolerance
- [ ] Zero HyperFrames render failures in `logs/notifications.jsonl`
- [ ] All Python + vitest tests green

Steps:
1. Edit `pipeline.py`: change `--renderer` default from `"remotion"` to `"hyperframes"`
2. Commit with message: `feat(hyperframes): flip default renderer to hyperframes (C3)`
3. Shadow tests continue but now Remotion is the *shadow* (compare, don't post)

### C3 → C1 (deprecate Remotion)

Prerequisites:
- [ ] 3 weeks of stable HyperFrames production with **zero** fallback triggers
- [ ] All team comfortable with HyperFrames-only workflow

Steps:
1. Delete `remotion/` directory
2. Delete `src/video/remotion_reel.py`
3. Remove `--renderer remotion` choice from argparse
4. Fallback chain becomes: `hyperframes → ffmpeg POV`
5. Commit with message: `feat(hyperframes): deprecate Remotion (C1)`

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `missing_timeline_registry` lint warning | Timeline registered after HyperFrames checks | Warnings only — render still succeeds. Use `--strict` to block. |
| 404 on CSS/JS imports | Relative paths in `index.html` | Ensure `index.html` is in `hyperframes/` root, not a subdir. |
| Black frames | Root element has no sized box | Check `#root` has `width:1080px; height:1920px` |
| Particles not visible | CSS vars missing | Verify `data-mood` is set on `<html>` and `moods.css` is loaded |
| MP4 too large | No video compression | HyperFrames auto-compresses; check `--codec h264` in config |

---

## 7. File map

```
hyperframes/
  package.json          # deps + scripts
  tsconfig.json         # TypeScript config
  hyperframes.config.ts # render config (1080x1920, 30fps)
  vitest.config.ts      # test runner config
  js/
    index.ts            # master timeline wiring
    lib/                # pure functions (ported from Remotion)
      sceneFrames.ts, wordAt.ts, cameraZoom.ts, emphasis.ts,
      duckVolume.ts, getGrade.ts, animateWords.ts, prng.ts
    scenes/             # per-scene GSAP timelines
      hook.ts, bridge.ts, quote.ts, cta.ts
    effects/            # Tier 2 visual effects
      particleField.ts, gradientBg.ts, filmGrade.ts,
      colorGrade.ts, pulsingBg.ts, glitchText.ts
  templates/
    index.html.j2       # root Jinja template
    scenes/
      hook.j2, bridge.j2, quote.j2, cta.j2
  css/
    moods.css           # 7 mood palettes (generated by sync_moods.py)
    scenes.css          # per-scene layout/typography
    effects.css         # particle/gradient/vignette base styles
  tests/                # 6 vitest test files
src/video/
  reel_data.py          # shared canonical dict builder
  hyperframes_reel.py   # Python bridge (Jinja → render)
  remotion_reel.py      # existing Remotion bridge (frozen during C2)
scripts/
  shadow_test.py        # parity harness
  studio_render.py      # agent-driven hero reels
  sync_moods.py         # theme.ts → moods.css generator
  render_hyperframes_test.py # quick smoke test
.github/workflows/
  hyperframes-smoke.yml # CI: npm test + smoke render
```
