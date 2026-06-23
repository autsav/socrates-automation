# AI Creative Studio — Design Spec

**Date:** 2026-06-23
**Scope:** Sub-project 1 of "AI team to grow the Instagram account" — the **Creative Brain**: a small team of reasoning agents (Data Analyst, Content Strategist, Copywriter, Creative Director) that produce scroll-stopping post concepts, proposed to the user via Telegram for manual publish.
**Out of scope (later sub-projects):** Ad Specialist (paid Meta Ads), Influencer Outreach (DM automation), auto-publish via API, comment auto-reply, multi-platform, new rendering engines.

---

## 1. Problem statement

The existing Socrates pipeline reliably *produces and posts* stoic-quote content (FLUX backgrounds → Pillow composition → Reels with beat-sync/voiceover/trending-music → Meta Graph API, scheduled via GitHub Actions, with SQLite state, A/B bandit, and analytics ingestion). Despite months of posting, content **"doesn't land"** — engagement is weak.

The root cause: content is assembled from a static `quotes.xlsx` pool + fixed hook/caption/controversy/hashtag templates + a `(day×3+slot) % pool` selector. There is **no reasoning per post and no critic rejecting weak drafts**. The machine has no creative brain.

This spec adds that brain as an **additive, fail-safe layer** between the scheduler and the existing renderer. Nothing downstream of concept selection changes.

## 2. Goals

1. Replace the templated brain (quote selection, caption, hook, controversy, mood, FLUX prompt) with four reasoning agents.
2. Keep the curated `quotes.xlsx` pool as the quote source (no fabricated attributions).
3. Human-in-the-loop: propose top concept(s) to Telegram; user approves by **manually publishing** (preserves trending-audio reach the API can't attach).
4. Learn from the account's own metrics (months of data in SQLite) via a Data Analyst agent.
5. Never block posting: any agent failure falls back to the existing templated path.
6. Stay within ~£10–30/mo of AI spend.
7. Preserve all existing module interfaces (backwards compatible).

## 3. Architecture

A new `studio/` package sits between the scheduler and the existing renderer. The studio outputs a **selected concept + visual direction**; the existing `generate_background` → `compose_*` → `reel_composer` → `instagram_poster` chain is untouched.

```
   once/day (cached)        studio/analyst.py    → PerformanceBrief  (data/perf_brief.json)
                                 │ reads SQLite posts + post_metrics
   per post slot                ▼
                            studio/strategist.py → CreativeBrief  (selects quote from pool)
                                 ▼
                            studio/copywriter.py → [Concept × N]
                                 ▼
                            studio/director.py   → Decision
                                 ├─ weak top pick? → ONE revision: copywriter.revise() → re-score
                                 └─ emits visual_direction (FLUX prompt, mood, typography) + rationale
                                 ▼
                            studio/run.py (orchestrator)
                                 ├─ render preview (cover + caption + reel) via visual_direction
                                 ├─ store proposal in SQLite (proposals table)
                                 └─ send top pick + alt + rationale → Telegram
                                 ▼
                         USER reviews, posts manually (adds trending audio)
                                 ▼
                            studio/reconcile.py  → backfill real post_id (Graph API recent media)
                                 ▼
                            analytics.py (existing) → metrics → Analyst's next brief
```

**Roles mapping:** Graphic Designer + Video Editor are the Creative Director's `visual_direction` fields feeding the existing renderers (no new code). Ad Specialist + Influencer Outreach are out of scope.

**SDK decision:** the `studio/` package uses the official **`anthropic` Python SDK** (structured outputs, adaptive thinking, prompt caching, typed retries). Existing one-shot Haiku calls (`excel_reader.get_mood_prompt`, `image_generator.enhance_prompt`) keep their raw `httpx` calls. Add `anthropic` to `requirements.txt`.

## 4. Agent contracts

Dataclasses, serialized to JSON for logging + Telegram. The vocabulary must match the renderer: `audience ∈ {procrastinator, doomscroller, stuck, lazy, quitter, lost, overwhelmed}`, `mood ∈ VALID_MOODS = {dark_philosophical, dramatic_ancient, cinematic_hopeful, stark_minimal, epic_warrior, mystical_greek, calm_stoic}`.

```python
# Analyst → cached daily to data/perf_brief.json
PerformanceBrief:
    generated_at: str
    sample_size: int
    window_days: int
    top_hooks:   list[dict]   # [{pattern, avg_reach, avg_saves, lift_vs_median, examples}]
    top_topics:  list[dict]   # [{theme, lift}]
    top_moods:   list[dict]   # [{mood, lift}]            mood ∈ VALID_MOODS
    best_formats: dict        # {"reel"|"carousel"|"image": score}
    best_slots:  dict         # {0|1|2: score}
    dying:       list[dict]   # [{pattern, why}]
    headline:    str          # 1-2 sentence summary

# strategist.make_brief(perf_brief, slot, recent_posts) → CreativeBrief
CreativeBrief:
    audience:     str          # one of the 7
    topic_theme:  str
    quote:        dict         # {text, row_number} | {need_new: true, theme}
    format:       str          # "reel" | "carousel" | "image"
    angle:        str          # emotional POV / framing
    must_include: list[str]    # from Analyst winners
    must_avoid:   list[str]    # from Analyst losers
    slot:         int          # 0|1|2
    hypothesis:   str          # why this should land

# copywriter.draft(brief, n) → list[Concept]
# copywriter.revise(concept, feedback, brief) → Concept    (the ONE loop)
Concept:
    id:          str
    angle_label: str
    hook:        str           # <= 60 chars; Reel scene 1 / image headline
    caption:     str
    cta:         str
    reel_scenes: list[str]     # on-screen text per scene, only if format == "reel"
    hashtags:    list[str]

# director.review(concepts, brief, perf_brief) → Decision
Decision:
    scores:    list[dict]      # [{concept_id, score(0-10), critique}]
    top_pick:  str             # concept_id
    alt_pick:  str | None
    revision:  dict            # {requested: bool, concept_id, feedback}
    visual_direction: dict     # {mood (∈ VALID_MOODS), flux_prompt, typography, palette}
    rationale: str             # message sent to Telegram with the pick
```

`visual_direction.mood` keeps `generate_background()` working unchanged; `flux_prompt` replaces the current Haiku `enhance_prompt` step (an upgrade). The quote is **selected from the ready pool** by the Strategist (replacing the slot-formula selector); if no good fit, `quote.need_new=true` triggers the existing `quote_generator`.

## 5. Component design

| Module | Responsibility |
|--------|---------------|
| `studio/types.py` | Dataclasses above + JSON (de)serialization + schema definitions for structured outputs |
| `studio/client.py` | Thin wrapper over `anthropic.Anthropic`: model/effort per role, prompt caching of shared prefix, retry, refusal detection, token-usage logging |
| `studio/analyst.py` | Pre-aggregate SQLite posts+metrics in Python → compact stats → `build_prompt`/`parse_response` → `PerformanceBrief`; cache to `data/perf_brief.json` |
| `studio/strategist.py` | `make_brief(perf, slot, recent)` → `CreativeBrief`; selects quote from pool |
| `studio/copywriter.py` | `draft(brief, n)`; `revise(concept, feedback, brief)` |
| `studio/director.py` | `review(concepts, brief, perf)` → `Decision`; triggers ≤1 revision |
| `studio/run.py` | Orchestrator: chain the agents, render preview, store proposal, send to Telegram; CLI `python -m studio.run [--dry-run] [--manual]` |
| `studio/reconcile.py` | Pull account's recent media via Graph API, match manual posts by caption/timestamp, backfill `post_id` |

Each agent module exposes pure `build_prompt(...)` and `parse_response(text) -> dataclass` for testability; the SDK call is isolated in `studio/client.py`.

**Model/effort defaults** (`claude-opus-4-8` / `claude-sonnet-4-6`, adaptive thinking):

| Role | Model | Effort |
|------|-------|--------|
| Analyst | Sonnet 4.6 | medium |
| Strategist | Sonnet 4.6 | medium |
| Copywriter | Opus 4.8 | high |
| Creative Director | Opus 4.8 | high |

All overridable in config. Shared prefix (brand brief + perf brief + recent winners, ~4k tok) is prompt-cached across the per-post calls.

## 6. Database changes

New table (additive; existing schema in `data_store.py` unchanged):

```sql
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    slot INTEGER NOT NULL,
    quote_row INTEGER,
    audience TEXT,
    format TEXT,
    decision_json TEXT NOT NULL,     -- full Decision serialized
    status TEXT DEFAULT 'proposed',  -- proposed | posted | expired
    post_id TEXT                     -- backfilled by reconcile
);
```

New helpers in `data_store.py`: `save_proposal(...)`, `proposed_today(slot) -> bool`, `mark_proposal_posted(id, post_id)`, plus a read-only aggregate query for the Analyst.

## 7. Integration with `pipeline.py`

New mode `--studio` (and `--studio --manual`). When set, the studio replaces Step 1 (Excel slot pick), Step 0 (A/B mood/caption), and the `_enhance_caption` / `_pick_controversy` / `_generate_psychology_hook` / `enhance_prompt` template logic. Downstream rendering + posting + `data_store`/`analytics` are unchanged. Legacy path remains the default and the fallback.

```
run_pipeline(studio=True, manual=True):
    init_db; token; slot guard; if proposed_today(slot): skip
    perf  = analyst.get_or_build_brief()
    brief = strategist.make_brief(perf, slot)
    concepts = copywriter.draft(brief, n=4)
    decision = director.review(concepts, brief, perf)
    if decision.revision.requested:
        revised = copywriter.revise(...); decision = director.review([revised]+keep, brief, perf)
    # render preview using decision.visual_direction (existing generate_background/compose/reel)
    save_proposal(...); notifier.notify_manual_reel_ready(...)  # top pick + alt + rationale
    # user posts manually; reconcile.py backfills post_id later
```

## 8. Reliability & fallbacks

| Scenario | Strategy |
|----------|----------|
| Agent JSON parse/validation fails | Retry once → fall back to legacy templated path for that post |
| `stop_reason == "refusal"` | Treat as failure → legacy fallback |
| Daily spend ceiling exceeded | Studio yields to legacy for rest of day; every run logs token usage + `cache_read_input_tokens` |
| Analyst fails | Reuse last good `perf_brief.json`; if none, Strategist cold-start on best-practice defaults |
| `perf_brief.json` stale (>24h) | Rebuild; on rebuild failure reuse last good |
| Duplicate slot | `proposed_today(slot)` guard |
| Manual post never reconciled | Retried daily for 7 days; logged if still unmatched |

Posting is **never** blocked by a studio failure.

## 9. Testing

| Module | Test | Mock |
|--------|------|------|
| each agent | `build_prompt` shape + `parse_response` against fixture JSON | none / fixtures |
| each agent | schema-validation failure → fallback | malformed fixture |
| `client.py` | retry on transient error; refusal detection | mocked `anthropic.Anthropic` |
| `analyst.py` | aggregation SQL correctness | in-memory SQLite, seeded posts/metrics |
| `data_store.py` | `proposals` CRUD + `proposed_today` | in-memory SQLite |
| `reconcile.py` | caption/timestamp match logic | mocked Graph API response |
| integration | `python -m studio.run --dry-run` full chain | mocked SDK client (no network/spend) |

Matches existing `tests/` + pytest conventions.

## 10. Rollout

1. Add `studio/` package + `types.py` + `client.py` + SDK dep; unit tests. No wiring.
2. Analyst only → generate `perf_brief.json`; eyeball. Read-only.
3. Full chain behind `--studio --dry-run` → review proposals in terminal. No posting.
4. `--studio --manual` → proposals to Telegram; user posts manually. Run alongside legacy for a week.
5. Studio becomes default for manual runs; legacy stays as `--legacy`.

## 11. Measuring success

Use existing `ab_test.py` + `analytics.py`: route some slots via studio, some via legacy; compare median saves/reach per post after 3–4 weeks.

**Success criteria:**
- [ ] Valid proposal for ≥95% of runs; otherwise legacy fallback fires, posting never blocked.
- [ ] Proposals reach Telegram with top pick + alt + rationale.
- [ ] ≥90% of manual posts reconciled to real `post_id` within 48h.
- [ ] AI cost < £30/mo (per-run token logging confirms).
- [ ] Measurable lift in median saves/reach vs legacy baseline after 3–4 weeks.

## 12. Cost

~100 posts/mo (3 reels/day + 2 carousels/week). Opus copy+director, Sonnet strategist+analyst, ~40% one revision, adaptive thinking, shared prefix prompt-cached (reads ~0.1×). ≈ **£11–19/mo**. Dials: model per role, `effort` per role, N variants, revision on/off, posts/day.
