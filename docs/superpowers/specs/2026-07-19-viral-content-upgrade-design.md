# Viral Content Upgrade — Design Spec

**Date:** 2026-07-19
**Status:** Approved design → implementation
**Goal:** Raise the content from "excellent automated" to "engineered for virality": trend-first story reels, debate-bait controversy, and a researched catalog of 100 viral levers with the top 10 shipped now.

---

## 1. Locked decisions (brainstorm)

| Decision | Choice |
|---|---|
| Trend depth | **Both, rotated** — new trend-first `story` arc joins the rotation (~40% when a safe trend exists); existing arcs otherwise. |
| 100 ways | **Catalog + top-10** — `docs/VIRAL_LEVERS.md` (100 scored levers); top ~10 implemented in this wave; rest = optimizer backlog. |
| Edge | **Contrarian, never personal** — strong stances on culture/behavior; hard guard against takes on named individuals; topic denylist stays. |
| Controversy | **Debate-bait** — posts engineered to split comments 50/50 on opinion topics (discipline vs talent, 9-5 vs hustle, phones, soft parenting, AI jobs). No politics/religion/tragedy — denylist unchanged. Debate topics also serve as the story arc's evergreen fallback when no safe trend exists. |

## 2. Components

### 2.1 `story` arc — trend-first storytelling (studio/story_writer.py + pipeline)
- New studio agent `story_writer` (opus, registered in `ROLE_MODELS/ROLE_EFFORT`, prompt managed by the optimizer as `prompt.story_writer.role`).
- Input: chosen trend topic (from trend_scout candidates) **or** a debate topic (from the controversy pool when no safe trend), plus the quote pool.
- Output (schema `STORY_SCHEMA`, `additionalProperties:false`): `{beat_hook, beat_reframe, quote_row|quote_text, beat_cta, stance, topic_query, caption_first_line, trend_tag}` with hard limits: hook ≤15 words; reframe ≤45 words; total VO budget ≤35s; the quote must land as the twist/payoff; contrarian-about-culture framing.
- Beats map 1:1 onto existing scenes: hook→Hook, reframe→Bridge, quote→Quote, cta→CTA. **No Remotion changes.**
- Arc rotation: `_pick_arc` gains `story` — when a safe trend or debate topic is available: 40% story / 60% existing three (deterministic by row). `posts.arc` records it (bandit-ready).
- Never-crash: story generation failure → fall back to the non-story arc for that row.

### 2.2 Debate-bait controversy (src/content/debate_topics.py)
- Curated pool of ~40 opinion-splitting topics (discipline vs talent, the 9-5 debate, phone culture, comfort as the enemy, soft parenting, dating apps, AI and jobs, gym vs therapy, money mindset…), each with a stance seed and a binary CTA ("Agree or disagree — comments.").
- Used by: story arc fallback (evergreen "trend"), and as a `debate` flavor the strategist can pull for non-story arcs (stance-strengthened copy).
- Explicitly excluded: politics, religion, tragedy, protected classes, named individuals — the existing `is_unsafe` denylist applies to every debate topic and generated beat.

### 2.3 Safety — named-person guard (src/content/safety_guards.py)
- `mentions_named_person(text) -> bool`: capitalized-bigram heuristic + honorific patterns, with an allowlist (Stoic philosophers, brand/product names appearing in the trend title itself, sentence-start words).
- Story beats + debate copy must pass: `is_unsafe` ∧ `not mentions_named_person` ∧ no-DM-promise. Any failure → drop to a safe arc; never block the post.

### 2.4 Top-10 levers shipped in this wave
1. **Story arc** (2.1) — the flagship.
2. **Trend-matched footage** — story arcs query stock footage by `topic_query` first, mood as fallback.
3. **First-frame hook** — the hook's key words visible at frame 0 (feed thumbnail = frame 1); Remotion hook text starts at full opacity for frame 0-2 then animates.
4. **Auto first-comment** — after publish, post the engagement/debate question as the post's first comment via existing `post_reply`-style Graph call (`/{media_id}/comments`); caption slims down.
5. **Caption curiosity gap** — first line ≤8 words, gap-shaped, before the fold.
6. **Trend/debate hashtag** — one topical tag added to the 3-5 niche set.
7. **Seamless loop** — CTA scene's final 12 frames crossfade toward the first frame's composition (loop illusion → rewatches).
8. **Dead-air trim** — inter-scene VO gap budget tightened (PAD 0.6→0.35s); story reels target ≤35s total.
9. **Big-type hook** — hook scene shows ≤4 words on screen at a time (chunked reveals) for the retention-critical first 3s.
10. **Trend recency weighting** — trend_scout prefers topics <24h old (recency score in candidate ranking).

### 2.5 `docs/VIRAL_LEVERS.md` — the catalog
100 levers, each: mechanism (why it works), impact H/M/L, effort S/M/L, pipeline component, measurement (how the A/B loop would verify). Categories: hook/retention, visual, audio, caption/SEO, engagement mechanics, algorithm timing, funnel, format variety, psychology, meta/learning. Top-10 marked SHIPPED; the rest ranked as the optimizer/backlog queue.

## 3. Testing
- `story_writer`: schema validation; beat length limits; quote-as-payoff presence; mocked client.
- Safety: named-person guard cases (celebrity name → blocked; "Socrates"/sentence-start → allowed); debate topics all pass `is_unsafe`.
- Arc rotation: distribution with/without available trend; story fallback on generation failure.
- Levers: first-frame text at frame 0 (payload/prop test + frame extract); first-comment call (mocked Graph); caption first-line length; PAD change keeps VO un-clipped (existing sceneFrames tests); loop crossfade renders (tsc + live frame).
- Acceptance: one live story-arc post (real trend or debate topic) rendered via Remotion, published, first-comment attached.

## 4. Non-goals
- Hot-button topics (politics/religion/tragedy) — even human-gated (rejected in brainstorm).
- Multi-agent story chains (single story_writer for v1).
- Auto-implementing beyond the top-10; the rest goes through the optimizer/backlog.

## 5. Success criteria
1. A story-arc reel generates end-to-end from a live trend AND from a debate topic (fallback), passing all safety guards.
2. Top-10 levers live and individually tested; full suite green.
3. `VIRAL_LEVERS.md` contains 100 concrete, scored, measurable levers.
4. One live story post published with first-comment attached (acceptance gate).
