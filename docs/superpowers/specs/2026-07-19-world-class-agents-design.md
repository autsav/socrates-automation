# World-Class Agents — Design Spec

**Date:** 2026-07-19
**Status:** Approved (architecture A + B-lite + C, phased)
**Goal:** Upgrade every live studio agent to world-best-at-its-field quality, then make the fleet self-improving against real Instagram engagement data.

## Locked decisions

| Decision | Choice |
|---|---|
| Scope | Both, phased: prompt mastery (Phase 1) → learning loop (Phase 2) |
| Architecture | A (playbook + coded critique) + B-lite (2-draft rubric pick, story_writer only) + C (winner few-shot, folded into Phase 2 digest) |
| director agent | Retired — removed from daily path; story_writer/copywriter absorb concept-picking |
| Budget | `DAILY_SPEND_CEILING_USD` 2.0 → 5.0 |
| North-star metric | sends-per-reach (shares ÷ reach) |
| Judge | Code (deterministic rubric), never a judge agent |

## Current fleet (context)

7 live agents in `studio/`: strategist, copywriter, director (retiring), trend_scout,
music_director, story_writer, prompt_critic (optimizer-side). All follow the studio
pattern: `_PREFIX`/`_ROLE_DEFAULT`, `client.call(role, prefix, role_system, user, schema)`,
prompts managed via `prompt_store.get` + `optimizer/assets.MANAGED_PROMPTS`, roles in
`settings.ROLE_MODELS/ROLE_EFFORT`. Everything is best-effort/never-crash.

---

## Phase 1 — Prompt Mastery

### 1.1 Playbooks (`studio/playbooks.py`, NEW)

One module-level string constant per agent, ~300–500 words of distilled domain-expert
craft, composed into each agent's `_ROLE_DEFAULT` (so the whole prompt stays a single
optimizer-managed asset):

- `STORY_CRAFT` — curiosity-gap theory, escalation ladders (each beat raises stakes),
  concrete-image rule (no abstraction where an image works), the earned twist (quote
  lands only after the story builds its need), send-psychology (write for ONE person).
- `COPY_CRAFT` — statement hooks beat questions, PAS (problem-agitate-solve) caption
  structure, SEO keyword weaving that reads naturally, first-line curiosity gap ≤8 words,
  one-reader rule.
- `TREND_CRAFT` — <24h recency rule, "philosophy-bridgeable" test (can a Stoic quote
  genuinely reframe this?), emotional charge beats importance, never force a bridge.
- `MUSIC_CRAFT` — energy-arc matching (track build aligns with the quote-twist moment),
  mood→instrument mapping, avoid vocal tracks under narration.
- `STRATEGY_CRAFT` — the 3 content pillars ("Short resets for people rebuilding
  discipline"), audience-fatigue rotation, do-not-repeat window.

Tests: every playbook non-empty, referenced by its agent's default prompt.

### 1.2 story_writer B-lite (2-draft rubric pick)

`write_story` generates TWO drafts with different persona seeds appended to the user
message ("Write as a historian-screenwriter…" / "Write as a growth-storyteller…"),
scores both with a NEW deterministic `score_story(d) -> float` and keeps the winner
(tie → draft 1). `validate_story` still gates both; if only one validates, it wins; if
neither, the existing corrective-retry path runs on draft 1.

`score_story` rubric (pure function, unit-tested):
- hook concreteness: +points for numbers, named ancients, physical objects; −points for
  abstractions ("success", "mindset")
- escalation density: sentence count / total words in band, variance of sentence length
- CTA specificity: "send this to <specific person-type>" beats generic "share this"
- simplicity: mean word length, % words >3 syllables (lower is better)

### 1.3 Inline self-critique

story_writer and copywriter role prompts end with: draft → critique against the rubric
dimensions → output only the revised final. One API call; the critique tokens are
internal reasoning, not a second agent.

### 1.4 Retire director

- Remove `director` from the daily generation path (its `build_prompt`/pick step in the
  studio flow); story_writer's `topic_query` + copywriter cover concept/visual selection.
- Remove `prompt.director.role` from `MANAGED_PROMPTS`; update
  `tests/test_optimizer_wiring.py` expected set; delete director-specific tests or mark
  the module legacy.
- `settings.py`: drop the role rows (or comment-mark legacy).

### 1.5 Budget

`DAILY_SPEND_CEILING_USD = 5.0`. Spend log unchanged.

---

## Phase 2 — Learning Loop

### 2.1 Insights poller (`src/analytics/insights_poller.py`, NEW + cron)

Daily GH Action (extend existing workflow pattern): for every live post 1–7 days old,
fetch plays/reach/likes/comments/shares/saves via the existing `metrics.py` Insights
fetcher (dual-host aware) → upsert into a NEW `post_metrics` table
(post_id, fetched_at, reach, plays, likes, comments, shares, saves). Token-free DB
rules apply (no token stored; CI uses the GH secret).

### 2.2 Performance digest (`src/analytics/performance_digest.py`, NEW)

`build_digest() -> dict` — per-agent views over `post_metrics` joined to `posts`:
- ranked by sends-per-reach (min reach floor 100 to kill noise)
- story_writer view: top-3/bottom-3 {arc, hook, sends_per_reach} + verbatim winning
  hooks (the C few-shot layer)
- copywriter view: top/bottom captions + first lines
- strategist view: per-audience aggregates
Cached to `data/perf_digest.json`; agents receive it via a `{digest}` slot in their
role prompts ("empty digest" string when no data — cold-start safe).

### 2.3 Arc bandit (`src/analytics/arc_bandit.py`, NEW)

Thompson sampling per arc on sends-per-reach (Beta posterior over normalized score).
`pipeline._pick_arc` consults `arc_bandit.pick(row, has_trend, rng_seed=row)` once
≥20 posts have metrics; below that, today's static rotation. Deterministic per row
(seeded) so tests stay reproducible.

### 2.4 Optimizer cadence

Weekly GH Action runs `src/optimizer/loop.py` → prompt_critic proposes challengers →
Telegram approval via existing approval_daemon → champion rotation. The critic's prompt
gains the digest ("prompt A avg 2.1% sends-per-reach vs B 3.4%") so critiques are causal.

---

## Error handling

Existing contract everywhere: every new stage is try/except best-effort.
- Insights API dead → digest goes stale, agents still run (stale beats empty).
- Digest missing → `{digest}` renders as "No performance data yet."
- Bandit below data threshold or erroring → static rotation.
- Rubric scoring exception → draft 1 wins.
- Poller cron failure → next day's run covers the gap (1–7-day window overlaps).

## Testing

- `score_story` determinism + ordering cases (concrete beats abstract, specific CTA
  beats generic).
- 2-draft pick: both valid → higher score; one valid → the valid one; none → retry path.
- Digest builder against a fixture DB (known metrics → known top/bottom).
- Bandit: seeded RNG reproducibility; <20 posts → static rotation passthrough.
- Wiring test updated: director key removed, no new managed keys missed.
- Full suite green; live dry-run after Phase 1; live acceptance post after Phase 2.

## Not in scope

Fine-tuning, judge agents, follower-growth tactics, Trial Reels (still <1k followers),
retiring any agent other than director.
