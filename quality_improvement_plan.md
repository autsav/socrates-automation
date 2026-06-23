# Post Quality Improvement Plan

## Executive Summary
The pipeline currently produces functional but visually basic Instagram posts. All four dimensions—**image**, **video**, **sound**, and **text**—have clear, measurable improvement opportunities. Most upgrades are free code changes; a few have marginal API cost impact (~£0.50–1.00/month extra).

---

## 1. Image Generation Quality (`image_generator.py`)

### Current Problems
| Issue | Impact |
|-------|--------|
| `portrait_4_3` (1024×1024 square) requested, then stretched to 1080×1920 | Distortion, lost detail, poor composition |
| Only 4 inference steps | Lower detail, more artifacts |
| No seed control | Cannot reproduce or iterate on good outputs |
| No negative prompt | Unwanted elements (hands, modern objects, text) appear |
| Hardcoded generic prompts | Images don't visually match the specific quote |
| No `guidance_scale` tuning | Weak prompt adherence |

### Improvements
1. **Native vertical aspect ratio** — Switch to `portrait_16_9` (576×1024) or `1024×1536` if Fal.ai supports custom sizes. This eliminates stretching and gives the AI the correct vertical canvas to compose on.
2. **Increase inference steps** — Bump from 4 to 6–8 steps. Cost impact: ~£0.01/image (still negligible). Quality gain: sharper detail, better lighting.
3. **Add seed + negative prompt** — `seed` for reproducibility; negative prompt: `"modern objects, text, watermark, blurry, low quality, people, faces, hands, cartoon, anime"`.
4. **Dynamic prompt enhancement** — Send the quote to Claude Haiku (already have the API call) and ask it to rewrite the mood prompt with 1–2 specific visual elements drawn from the quote's themes. Cost: ~£0.001/call.
5. **Add `guidance_scale: 3.5`** for stronger prompt adherence.

---

## 2. Image Composition & Typography (`image_composer.py`)

### Current Problems
| Issue | Impact |
|-------|--------|
| Fixed 52pt font regardless of quote length | Long quotes get illegible; short quotes look empty |
| Naïve character-width wrapping | Ugly line breaks, poor readability |
| Simple black drop shadow only | Text can still get lost on busy backgrounds |
| Static overlay panel position | Doesn't adapt to background content |
| Single font family | No typographic hierarchy |
| Attribution always "— Socrates" | Incorrect for AI-generated quotes |

### Improvements
1. **Dynamic font sizing** — Calculate font size from quote length:
   - ≤80 chars → 64pt
   - 81–150 chars → 52pt
   - 151–220 chars → 42pt
   - >220 chars → 36pt
2. **Word-aware line balancing** — Use Knuth-Plass-style greedy line breaking that minimizes raggedness, rather than simple `textwrap.wrap()`.
3. **Text glow + stroke** — Replace simple drop shadow with a subtle dark outer glow (`ImageFilter.GaussianBlur` on a text mask) for much better readability on complex backgrounds.
4. **Background brightness analysis** — Sample the center region of the background image. If it's already dark, reduce overlay opacity; if light, increase it. This prevents washed-out or overly-dark compositions.
5. **Typographic hierarchy** — Use a bolder weight for the quote and an italic variant for attribution. Load `LiberationSerif-Bold.ttf` and `LiberationSerif-Italic.ttf` on Linux; fall back gracefully.
6. **Smart attribution** — If the quote is AI-generated (not from the original Excel set), use "— Stoic Start" or "— Ancient Wisdom" instead of always "— Socrates".
7. **Subtle watermark/logo** — Add a small marble-column icon or Greek meander pattern as a bottom watermark for brand consistency.

---

## 3. Reel Video Quality (`reel_composer.py`)

### Current Problems
| Issue | Impact |
|-------|--------|
| Ken Burns zoom barely perceptible (0.0004/frame, max 1.05×) | Looks static; no visual dynamism |
| No burned-in subtitles/captions | 85% of Reels watched without sound |
| CTA scene reuses hook background | Visual monotony |
| Single crossfade transition | Boring; no energy shift |
| `fast` preset + CRF 23 | Blocky motion, compression artifacts |
| 24fps | Slightly juddery on mobile |

### Improvements
1. **Stronger Ken Burns** — Zoom from 1.0 to 1.12 over 15s with subtle pan (e.g., `x=(iw-iw/zoom)/2 + sin(t/15*PI)*50`). This creates real motion.
2. **Burned-in subtitles** — Use ffmpeg `drawtext` filter with a clean sans-serif font (DejavuSans) to overlay the quote text on Scene 2. This is *critical* for silent viewing engagement.
3. **Unique CTA background** — Generate a 3rd background image for the CTA scene instead of reusing the hook background. Cost: one extra Fal.ai call per post (~£0.003).
4. **Vignette effect** — Add `vignette` filter to draw attention to the center text.
5. **Better encoding** — Switch to `preset=slow` or `preset=medium` and `crf=20` for much cleaner output. File size grows ~30% but well within Instagram's limits.
6. **30fps** — Smoother motion perception on mobile screens.
7. **Scene-appropriate motion** — Hook scene could have a subtle zoom-in (energy building); quote scene has slow pan; CTA scene is static or subtle zoom-out.

---

## 4. Audio Quality (`generate_audio.py` + `download_music.py`)

### Current Problems
| Issue | Impact |
|-------|--------|
| `libmp3lame -q:a 9` = worst VBR quality | Noticeable artifacts, tinny sound |
| 10-second synthetic noise/sine loops | Sounds like a phone ringtone, not cinematic audio |
| No real music | Pixabay downloader exists but `audio/music/` dir is empty and no `PIXABAY_API_KEY` in workflow secrets |
| Volume 0.25 | Inaudible on mobile speakers |
| No audio variation across scenes | Monotonous |

### Improvements
1. **Add `PIXABAY_API_KEY` to GitHub secrets + workflow** — Download real royalty-free instrumental tracks once, cache them in `audio/music/`. The existing `download_music.py` already handles this.
2. **Improve MP3 quality** — Change from `-q:a 9` to `-q:a 2` (near-transparent). File size increases but still tiny (~200KB).
3. **Volume normalization** — Target -14 LUFS (YouTube/Instagram standard) using ffmpeg `loudnorm` filter instead of arbitrary `volume=0.25`.
4. **Loop audio to full reel length** — The reel is 20s but audio is only 10s. Use ffmpeg `aloop` or crossfade loop to fill the full duration seamlessly.
5. **Scene-synced audio energy** — Slightly lower volume during the hook scene (let the text shock), full volume during quote scene, fade to silence during CTA.
6. **Beat-aware transitions** (Stretch goal) — If we have real music, analyze BPM and align crossfade transitions to musical bars using ffmpeg `aecho` or `ebur128`.

---

## 5. Text & Caption Quality (`excel_reader.py`, `generate_quotes_excel.py`, `quote_generator.py`)

### Current Problems
| Issue | Impact |
|-------|--------|
| Hook extraction = first sentence truncation | Often boring, not scroll-stopping |
| No hashtags | Reduced discoverability |
| No emoji in captions | Looks flat, less engaging |
| Static CTA | "Save this. Read it again tonight." gets repetitive |
| Template-based captions | After 30 posts, followers may recognize the pattern |

### Improvements
1. **AI-optimized hook extraction** — Send the caption to Claude Haiku and ask it to extract the most emotionally charged 6–8 words as a hook. Cost: already making a Claude call; this is a few extra tokens.
2. **Hashtag generation** — Use Claude Haiku to generate 5–8 relevant hashtags from the quote + audience. E.g., `#Stoicism #SelfDiscipline #PhilosophyQuotes #MindsetShift #AncientWisdom`.
3. **Emoji placement** — Add 2–3 contextual emojis to the caption (e.g., ⚔️ for warrior quotes, 🌊 for calm quotes). Claude can generate these.
4. **Dynamic CTA variants** — Build 6 CTA templates, rotate them, and A/B test:
   - "Save this. Read it again tonight."
   - "Which part hit hardest? Drop it in the comments."
   - "Tag someone who needs to see this."
   - "Double-tap if you felt this."
   - "Screenshot and set it as your wallpaper."
   - "The comments are where the real wisdom lives."
5. **Caption formatting** — Add strategic line breaks:
   ```
   📖 HOOK
   
   [story]
   
   💡 "Quote"
   — Socrates
   
   🎯 CTA
   
   #hashtags
   ```

---

## 6. Implementation Phases

### Phase 1: Image Foundation (Priority: High)
- Fix aspect ratio + seed + negative prompt (`image_generator.py`)
- Dynamic prompt enhancement via Claude
- Dynamic font sizing + text glow (`image_composer.py`)
- **Files**: `image_generator.py`, `image_composer.py`, `excel_reader.py`
- **Cost impact**: ~£0.01/post extra

### Phase 2: Reel Upgrade (Priority: High)
- Stronger Ken Burns + pan
- Burned-in subtitles on Scene 2
- Unique CTA background
- Better encoding settings
- **Files**: `reel_composer.py`, `image_generator.py`, `pipeline.py`
- **Cost impact**: ~£0.003/post extra (one more image)

### Phase 3: Audio Upgrade (Priority: Medium)
- Add `PIXABAY_API_KEY` secret + workflow env
- Improve MP3 quality settings
- Volume normalization + looping
- Scene-synced audio levels
- **Files**: `generate_audio.py`, `reel_composer.py`, `.github/workflows/*.yml`
- **Cost impact**: Free (Pixabay is free)

### Phase 4: Text Polish (Priority: Medium)
- AI hook extraction
- Hashtag + emoji generation
- Dynamic CTA rotation
- Better caption formatting
- **Files**: `generate_quotes_excel.py`, `excel_reader.py`, `quote_generator.py`, `pipeline.py`
- **Cost impact**: Negligible (already calling Claude)

### Phase 5: Analytics-Driven Optimization (Priority: Low)
- Use analytics data to automatically pick the best-performing mood, CTA, and slot
- Feed 30-day rolling metrics back into the A/B test engine
- **Files**: `analytics.py`, `ab_test.py`, `data_store.py`
- **Cost impact**: Free

---

## Estimated Cost Impact

| Phase | Monthly Cost Delta | Notes |
|-------|-------------------|-------|
| Phase 1 | +£0.30 | 2 extra inference steps + prompt enhancement |
| Phase 2 | +£0.09 | One extra Fal.ai image per post |
| Phase 3 | £0 | Pixabay is free |
| Phase 4 | £0 | Reuses existing Claude calls |
| Phase 5 | £0 | Free analytics |
| **Total** | **+£0.39/month** | From ~£2.60 → ~£3.00/month |

---

## Risk Mitigation
- All changes are additive; we keep fallback paths so the pipeline never breaks.
- Fal.ai custom sizes: we test with `portrait_4_3` fallback if the new size isn't supported.
- Font loading: keep existing fallback chain so Linux runners still work.
- Audio: synthetic audio stays as ultimate fallback if Pixabay fails.
- Dry-run mode tests all changes before live posting.

---

## Success Metrics
After implementing, we should see:
- **Reach**: +20–30% (hashtags + better silent viewing with subtitles)
- **Saves**: +15% (better typography + dynamic CTAs)
- **Comments**: +10% (better hooks + engaging CTAs)
- **Video watch-through**: +25% (subtitles + stronger Ken Burns + real music)
