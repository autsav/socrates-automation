# Viral-formula generators + content injection (Sub-project B)

Date: 2026-07-13
Status: Approved

## Goal

Make every reel follow the viral formula (sourced from the user's NotebookLM):
formula-compliant hooks, share/save/DM CTAs, SEO captions with 3–5 hashtags, a
seamless loop, and an optional Bridge scene. Add a content-injection path so a
hand-crafted or externally-sourced reel can be posted directly. This is the
foundation for Sub-project A (one-off reel) and the Trend Scout feature (NEW).

## The formula (reference)

Hook 5–12 words, negative framing (stop/don't/avoid/mistake), 3 types
(Problem-Agitate / Curiosity-Gap / Number-Promise). 3-Act Hook→Value→Action.
Seamless loop (last line flows into hook). CTA drives Saves/Sends/DMs, never
"follow for more". Caption keyword-SEO natural language + exactly 3–5 niche
hashtags (no #fyp/#viral). Arc: Hook→Bridge→Quote→CTA.

## Components

### 1. Content injection — `--content <path.json>` (pipeline.py)
New CLI flag. Reads a JSON object and **bypasses the excel + studio content
stage**, feeding this exact content into the reel path:
```json
{"hook": "...", "bridge": "...", "quote": "...", "attribution": "— Socrates",
 "cta": "...", "caption": "...", "hashtags": ["#a","#b"], "mood": "dark_philosophical",
 "audience": "stuck", "row_number": null}
```
- `bridge`, `caption`, `hashtags` optional. Missing fields fall back to the
  existing generators (so a partial JSON still works).
- Implemented as a new content source `_injected_content(path) -> quote_data`
  parallel to `_legacy_content` / `_studio_stage`, selected first when `--content`
  is passed. Reuses the rest of the reel path unchanged (POV/Remotion/publish).
- Row `posted`-marking is skipped for injected content with `row_number: null`.

### 2. Hook generator — formula-compliant
- `_generate_psychology_hook(audience, row_number)` and the studio copywriter
  prompt (`studio/copywriter.py`) produce hooks that are **5–12 words**, bias to
  negative framing, and match one of the 3 hook types.
- Add `_enforce_hook_len(hook) -> str`: if >12 words, trim to the first
  loss-aversion clause; if <3, leave. Applied wherever the reel hook is finalized.

### 3. CTA generator — Saves/Sends/DMs
- Replace `_pick_cta(row_number)`'s pool with save/send/DM-trigger CTAs; remove
  every "follow for more"/"like if" variant. Include DM-trigger templates
  ("Comment 'WORD' and I'll DM you …").

### 4. Caption + hashtags — SEO
- `_generate_hashtags(audience, mood, max_tags)` → return **exactly 3–5** tags
  (clamp: if fewer than 3 candidates, pad from a niche pool; never exceed 5);
  drop generic tags (`#fyp`, `#viral`, `#reels`, `#explore`).
- Caption path (`_enhance_caption` / studio copywriter) keeps keyword-rich
  natural language; no change beyond ensuring the hashtag block is the 3–5 set.

### 5. Seamless loop
- `_loopify(cta, hook) -> str`: ensure the CTA's final clause is an open lead-in
  (append an em-dash connector if absent) so the reel loops back into the hook.
- Studio copywriter prompt instructs co-generation: the CTA's last words should
  flow into the hook's first words.

### 6. BridgeScene (Remotion) — optional 4th scene
- Add `remotion/src/components/BridgeScene.tsx` and wire it into `PovReel.tsx`
  **only when `bridge` is non-empty** in `reel-data.json` (evergreen reels omit
  it, preserving today's 3-scene arc).
- `remotion_reel.write_bridge_file` gains a `bridge` field + optional
  `bridge_voice`/`bridge_words`; `sceneFrames` allocates a bridge slot between
  hook and quote when present.
- `_run_pov_reel` generates a bridge VO (edge-tts, sage voice) when
  `quote_data["bridge"]` is set, and passes it through.

## Data flow

```
--content json ─▶ _injected_content ─┐
excel ───────────▶ _legacy_content ──┼─▶ quote_data {hook,bridge?,quote,cta,caption,hashtags,mood}
studio ──────────▶ _studio_stage ────┘        │
                       hook: _enforce_hook_len ; cta: _loopify(cta,hook) ; hashtags: 3–5
                                              │
   _run_pov_reel ─▶ (bridge? edge-tts bridge VO) ─▶ remotion bridge file (bridge + scene)
                                              │
                              Remotion Hook→[Bridge]→Quote→CTA ─▶ publish
```

## Error handling / fallback

Injection with missing fields → per-field generator fallback. No `bridge` →
3-scene reel (unchanged). Hook-length/hashtag validators are pure and never
raise. All existing never-crash contracts preserved.

## Out of scope (YAGNI)

- Trend sourcing (that is Sub-project NEW; this only adds the injection *path* +
  bridge *scene* it will use).
- Auto-DM automation (the CTA only prints the trigger text; wiring an actual DM
  bot is separate).

## Testing

- `_enforce_hook_len`: >12 words trimmed, ≤12 unchanged.
- `_pick_cta`: no CTA in the pool contains "follow"/"like if".
- `_generate_hashtags`: result length always in [3,5]; no generic tags.
- `_loopify`: CTA ends with an open connector.
- `_injected_content`: a JSON with all fields overrides the content stage; a
  partial JSON falls back per-field; `row_number: null` skips excel marking.
- Remotion `write_bridge_file`: `bridge` present → bridge in payload + a
  `sceneFrames` slot; absent → payload has no bridge and arc is 3 scenes.
- Integration: `pipeline.py --content sample.json --remotion --dry-run` renders a
  4-scene reel; without `--content` behavior is unchanged.
