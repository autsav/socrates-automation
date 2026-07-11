# Image & Typography Quality — Design

**Date:** 2026-07-11
**Status:** Approved (design)
**Sub-project 2 of 3** in the quality program (1: reliability ✅ merged; 3: reel production polish).

## 1. Goal

Fix the three genuine remaining gaps in image/typography output. The original
`quality_improvement_plan.md` §1–2 (native vertical ratio, 6 steps,
`guidance_scale`, negative prompt, prompt enhancement, adaptive font sizing,
balanced wrap, brightness-adaptive panel, stroke/gradient text) is **already
implemented** and is out of scope — do not re-build it.

## 2. Decisions (locked)

| # | Decision |
|---|---|
| Font | Bundle **Playfair Display** (OFL), loaded first in `_load_font`. |
| FLUX tier | Default **`pro`** (`fal-ai/flux-pro/v1.1`), configurable via `FAL_TIER` env (`schnell`/`dev`/`pro`). |
| Seed | Persist the seed used per post; allow override for reproduction/iteration. |

## 3. Non-goals (YAGNI)

- No changes to aspect ratio, steps, guidance, negative prompt, prompt
  enhancement, or the composer's layout/sizing/wrap logic.
- No per-mood seed *locking* (trivial follow-up on top of persistence).
- No changes to the Remotion reel (that's Sub-project 3).

## 4. Architecture

### 4.1 Bundle Playfair Display — `assets/fonts/` + `src/visual/image_composer.py`
- Commit to `assets/fonts/`: `PlayfairDisplay[wght].ttf` (variable upright),
  `PlayfairDisplay-Italic[wght].ttf` (variable italic), and `OFL.txt` — fetched
  from the google/fonts repo (`ofl/playfairdisplay/`).
- `_load_font(size, bold, italic)`: prepend the bundled font as the **first**
  candidate (before every system path). For the upright variable font, set the
  weight axis via `font.set_variation_by_axes([weight])` — `900` when `bold`,
  else `400`. Use the italic variable file when `italic`. Keep all existing
  system paths + the Pillow default as fallback (so nothing breaks if the asset
  is somehow missing).
- Everything else in the composer is unchanged and simply renders in the better
  face.

### 4.2 Configurable FLUX tier — `src/visual/image_generator.py`
- Replace the hardcoded `FAL_API_URL = ".../flux/schnell"` with a tier map and
  `FAL_TIER = os.getenv("FAL_TIER", "pro")`:

  | tier | endpoint | payload specifics |
  |---|---|---|
  | `schnell` | `fal-ai/flux/schnell` | `num_inference_steps`, `guidance_scale`, `negative_prompt` |
  | `dev` | `fal-ai/flux/dev` | `num_inference_steps`, `guidance_scale`, `negative_prompt` |
  | `pro` | `fal-ai/flux-pro/v1.1` | NO `num_inference_steps`/`guidance_scale`; uses `safety_tolerance`, `output_format` |

- A per-tier **payload builder** emits only the params that tier supports; the
  shared params are `prompt`, `image_size: portrait_16_9`, `num_images: 1`,
  `seed`. The response parsing (`data["images"][0]["url"]`) is identical across
  tiers.
- **External unknown (verify during implementation):** the exact `flux-pro/v1.1`
  param names/allowed values (`safety_tolerance`, `output_format`, whether
  `negative_prompt` is accepted) must be checked against current Fal.ai docs. If
  pro's schema differs from the table above, surface it — do not guess. The tier
  map isolates this so only the `pro` branch is affected.
- Invalid `FAL_TIER` → fall back to `pro` with a logged warning.

### 4.3 Seed reproducibility — `image_generator.py` + `data_store.py` + `pipeline.py`
- `generate_background(..., seed: int | None = None)`: if `seed` is provided use
  it (locked), else `random.randint(0, 999999)`. A module-level default can be
  sourced from `FAL_SEED` env when set. **Return type changes to
  `tuple[Path, int]`** (path, seed_used).
- Update all 5 call sites: the main-image site (`pipeline.py:686`) captures the
  seed and passes it to `save_post`; the other sites (image_generator internal
  self-test, and the three reel background calls) use `path, _ = generate_background(...)`.
- `data_store.py`: add a `seed INTEGER` column to `posts` (idempotent migration,
  mirroring the `post_date`/`hook_id` pattern). `save_post(...)` gains a
  `seed: int | None = None` param persisted in the INSERT. (Return contract from
  Sub-project 1 — `int | None` — is unchanged.)
- Optional CLI `--seed N` on `pipeline.py` forwarded to the main image
  generation for deliberate iteration.

## 5. Data flow
```
FAL_TIER (env, default pro) ─► tier map ─► endpoint + payload builder
generate_background(seed=?) ─► (Path, seed_used)
   main path: pipeline.py:686 ─► save_post(..., seed=seed_used) ─► posts.seed
_load_font ─► assets/fonts/PlayfairDisplay[wght].ttf (weight axis) ─► all text
```

## 6. Error handling
- Missing bundled font (shouldn't happen once committed) → existing system/Pillow
  fallback chain, unchanged.
- Unknown `FAL_TIER` → `pro` + warning.
- Fal pro schema mismatch → surfaced during implementation, not guessed.
- Seed migration idempotent; safe on the DB committed in Sub-project 1.

## 7. Testing
Run under the 3.11 `.venv` (`.venv/bin/python -m pytest`).
- **Font:** bundled files exist + load via `ImageFont.truetype`; `_load_font`
  returns the bundled Playfair as first choice; bold path sets weight 900.
- **FLUX:** the payload builder — pro omits `num_inference_steps`/`guidance_scale`
  and includes `safety_tolerance`; schnell/dev include steps + `guidance_scale`;
  each tier maps to the right endpoint; unknown tier → pro. Seed passed through.
  All unit-level, no network (test the builder function directly).
- **Seed:** `generate_background` returns the seed it used; a provided seed is
  used verbatim; `save_post` persists `seed`; migration idempotent (init_db twice
  → one `seed` column).
- Full suite green apart from the 2 pre-existing `test_reel_composer.py` ffmpeg
  failures.

## 8. Files touched
| File | Change |
|---|---|
| `assets/fonts/PlayfairDisplay[wght].ttf`, `-Italic[wght].ttf`, `OFL.txt` | NEW bundled OFL font |
| `src/visual/image_composer.py` | `_load_font` prepends bundled Playfair + weight axis |
| `src/visual/image_generator.py` | tier map + `FAL_TIER`; per-tier payload builder; `seed` param + `(Path, seed)` return |
| `src/core/data_store.py` | `posts.seed` column migration; `save_post(seed=...)` |
| `pipeline.py` | capture seed at main image site → `save_post(seed=)`; `path,_=` at other sites; optional `--seed` |
| `tests/…` | new font / FLUX-payload / seed tests |
