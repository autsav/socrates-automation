# FLUX-Backed Remotion Reel — Design Spec

**Date:** 2026-07-14
**Status:** Approved design → implementation
**Goal:** Reels = **Remotion animated text over a smart fal.ai (FLUX) photo background**, driven by **trending news bridged to a Socrates quote**, narrated in the **edge-tts sage voice**. Make this the *one* reel renderer and retire the path that produced OpenAI-TTS + ffmpeg reels.

---

## 1. Problem (root cause, from debugging)

Two reel renderers exist; the wrong one is the default:

| Path | Text | Background | Voice | Trend |
|---|---|---|---|---|
| `_run_pov_reel` (Remotion) | ✅ animated | ❌ particles/gradient (no photo) | ✅ edge-tts `en-US-AndrewNeural` | ✅ |
| FLUX path (`generate_reel`) | ❌ ffmpeg | ✅ fal.ai photo | ❌ OpenAI TTS (onyx/…) | ✅ |
| **Target** | ✅ | ✅ fal.ai photo | ✅ edge-tts | ✅ |

The Remotion path is gated behind `if pov:` (`pipeline.py:905`); only `--remotion`/`--pov` set `pov=True`. Any reel invoked without those (scheduled `--studio --manual` slots, `workflow_dispatch`) falls to the FLUX path → **OpenAI voice + ffmpeg (no Remotion)** — the reported bug. The Remotion path was intentionally built "zero-cost" and **skips FLUX background generation**, so neither path produces the target.

## 2. Locked decisions (brainstorm)

| Decision | Choice |
|---|---|
| **Visual style** | **AI-per-mood** — `PromptArchitect` picks style from mood; subject also reflects the trend topic. |
| **Renderer** | **Remotion+FLUX is the only reel renderer.** Retire the ffmpeg `generate_reel` + `generate_enhanced_voiceover` (OpenAI TTS) reel path. |
| **Trend** | **Trend-first, evergreen fallback** — try a trending hook every reel; use it only when it bridges safely, else evergreen. |
| **Particles** | Keep the gold particle layer **over** the photo (brand continuity), subtle. |
| **Motion** | Slow Ken-Burns scale on the photo. |
| **fal.ai failure** | `background=None` → particle/gradient bg; reel still renders. |
| **Cost** | ~£0.003/reel (one fal.ai image). Accepted. |

## 3. Architecture — one new branch in an existing flow

```
content stage
  → _apply_trend_scout            trend-first hook+bridge (evergreen fallback) [EXISTS]
  → PromptArchitect.build(quote, mood, trend_topic)   smart FLUX prompt        [EXISTS, extend]
  → generate_background(prompt)   fal.ai FLUX image                            [EXISTS]
  → write_bridge_file(..., background=img)   copies img, adds to reel-data.json [EXTEND]
  → Remotion PovReel renders, bottom → top:
        <BackgroundPhoto> (Img + Ken-Burns) → dark scrim → particle field
        → beat-synced animated text                                           [EXTEND PovReel.tsx]
  → edge-tts sage VO + Jamendo music + sfx                                     [EXISTS]
```

## 4. Components & changes

### 4.1 `remotion/src/PovReel.tsx` + new `remotion/src/components/BackgroundPhoto.tsx`
- New `background?: string` prop (a `staticFile` image name). When present, render a base layer:
  - `<Img src={staticFile(background)}>` full-bleed, `objectFit: cover`, with a slow scale transform (`interpolate(frame, [0, durationInFrames], [1.06, 1.14])`) for Ken-Burns.
  - A dark bottom-weighted gradient scrim (`linear-gradient(180deg, rgba(0,0,0,.25) 0%, rgba(0,0,0,.55) 55%, rgba(0,0,0,.8) 100%)`) for text legibility.
- When `background` is falsy → render today's `GradientBg`/`PulsingBg` (byte-for-byte current behavior — no regression for bridge files without a background).
- The existing particle field + text layers render **on top** of either base, unchanged.
- `povReelDefaultProps` gets `background: undefined`.

### 4.2 `src/video/remotion_reel.py` — `write_bridge_file` / `generate_remotion_reel`
- Add `background: Path | None = None` param. If given and exists, `_copy_audio`-style copy next to the bridge as `bg<ext>` and add `payload["background"] = name`. Absent → no `background` key (payload shape unchanged for existing callers).
- `generate_remotion_reel` threads `background` through to `write_bridge_file`.

### 4.3 `pipeline.py` `_run_pov_reel`
- After `quote_data`/mood are known and before the Remotion call, best-effort generate the FLUX bg:
  - `prompt = PromptArchitect().build(quote=quote_data["quote"], mood=mood, trend_topic=quote_data.get("trend_topic"))`
  - `bg_path, _seed = generate_background(prompt, ...)` (existing fal.ai fn)
  - Wrap in try/except → `bg_path=None` on any failure (log, continue).
- Pass `background=bg_path` to `generate_remotion_reel`.
- `_apply_trend_scout` already sets `quote_data["hook"]`/`["bridge"]`; also stash the chosen `trend_topic` on `quote_data` so PromptArchitect can use it for the photo subject.

### 4.4 `src/prompts/architect.py` `PromptArchitect.build`
- Accept optional `trend_topic: str = ""`. When present, weave it into the subject ("a cinematic scene evoking {trend_topic}") while mood still drives style. No behavior change when empty.

### 4.5 Routing (retire the bad path) — `pipeline.py` + `daily_post.yml`
- **All reels route to `_run_pov_reel`.** In `run_pipeline`, when the output is a reel (studio picks reel, or a reel slot), take the Remotion path regardless of the `--remotion` flag. The `generate_reel` (ffmpeg) + `generate_enhanced_voiceover` (OpenAI TTS) reel branch is removed from the reel flow.
- **Fallback preserved:** if Node/Remotion is unavailable, `generate_remotion_reel` returns `None` and `_run_pov_reel` falls back to the **ffmpeg POV generator with edge-tts** (`generate_pov_reel`) — correct voice, no OpenAI.
- `daily_post.yml`: the `--studio --manual` reel commands become `--studio --manual --remotion` (or the routing change makes the flag moot — belt and suspenders: set it anyway for clarity).
- `generate_enhanced_voiceover` / `VoiceoverEngine` (OpenAI TTS) is left in the tree but no longer called on the reel path (removing the module is out of scope; a follow-up may delete it).

### 4.6 Safety (sports must pass)
- Verify `src/content/trend_sources.is_unsafe` does **not** reject sports/World-Cup (denylist targets tragedy/death/war/politics/violence/crime — sports is fine). Add a test asserting a football topic is allowed and a war topic rejected. If a sports term is inadvertently caught, adjust the denylist.

## 5. Testing (TDD)

- **`write_bridge_file`**: includes `background` key when given a real image; omits it when `None` (payload shape unchanged) — existing bridge tests still pass.
- **`generate_remotion_reel`**: threads `background` to the bridge (mock the Node render).
- **PovReel**: importer/prop test — with `background` set, the normalized reel-data / composition includes the Img layer; without it, the gradient path is used. (Assert via the JSON payload + a lightweight check; full visual is the live render.)
- **`_run_pov_reel`**: passes a bg path when `generate_background` succeeds (mocked) and `None` when it raises — reel still requested either way.
- **`PromptArchitect.build`**: `trend_topic` appears in the prompt when provided; unchanged when empty.
- **Routing**: a `run_pipeline(studio=True, manual=True)` reel invocation calls `_run_pov_reel`, never `generate_reel`/`generate_enhanced_voiceover` (spy/mocks).
- **Safety**: `is_unsafe("World Cup final")` is False; `is_unsafe("war casualties")` is True.
- **Live**: one end-to-end `--remotion --dry-run` render, eyeball the FLUX-backed reel + confirm edge-tts voice + a trend hook.

## 6. Non-goals

- Deleting the OpenAI-TTS `voiceover_engine` module (leave dormant; possible follow-up).
- Changing the image/carousel (non-reel) paths.
- Video-clip backgrounds (still photo + Ken-Burns only).

## 7. Success criteria

1. `pipeline.py --remotion --dry-run` produces a reel whose background is a fal.ai photo (not particles), with animated text over it and the edge-tts sage voice.
2. A `--studio --manual` reel invocation renders via Remotion (not ffmpeg/OpenAI).
3. When fal.ai is unavailable, the reel still renders (particle bg) with the sage voice.
4. A trending topic (e.g. World Cup) is used as the hook and reflected in the photo subject when it bridges safely; evergreen otherwise.
5. Full suite green.
