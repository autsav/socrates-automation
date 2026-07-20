# Viral-Formula Scripts — Design Spec

**Date:** 2026-07-20
**Status:** Approved (Approach A + exemplars; script-doctor agent deferred)
**Goal:** Rebuild the 60s story script around an explicit, code-enforced viral formula — viewer-first open loops, cliffhanger structure, withheld payoff — and kill material repetition.

## User diagnosis (all four)

Current scripts: read as history lessons; no open loops (nothing makes you need the ending); about the dead Roman instead of the viewer; same capsules repeat (Cato/Seneca again and again).

## Locked decisions

| Decision | Choice |
|---|---|
| Formula enforcement | Deterministic code checks (`validate_formula`), NOT a critic agent |
| Taste | Two complete exemplar scripts embedded in the prompt (one weird-history, one debate) |
| Repetition fix | 60-capsule pool + per-post `material_key` tracking with last-20 exclusion, LRU fallback |
| Scope | Prompt + validation + material only — schema, VO, visuals, punch mode untouched |

## 1. The 6-phase formula (prompt rewrite in `studio/story_writer.py`)

Applies to story/weird/debate-fed modes (punch keeps its own contract). Beat mapping is unchanged (hook / reframe / quote / cta); the formula structures WHAT goes in them:

| Time | Phase | Lives in | Rule |
|---|---|---|---|
| 0–3s | Viewer-hook + open loop | `beat_hook` | Addresses "you/your"; plants a mystery it does NOT answer; statement ≤15 words. Never opens with the historical figure. |
| 3–10s | Stakes | reframe start | Second person; agitate the viewer's tonight-problem |
| 10–25s | Story entry → cliffhanger | reframe | Ancient story begins, STOPS mid-tension (loop #2) |
| 25–40s | Escalation | reframe | Intensifies; no resolution vocabulary |
| 40–50s | Payoff | reframe end + quote | Both loops close; the quote IS the answer |
| 50–60s | Send-CTA | `beat_cta` | Names the friend type |

Anti-rules in the prompt: never open with the figure; never resolve a loop before the payoff phase; the word "lesson" is banned; the viewer's life is the story — the ancient is the twist.

Two exemplar scripts embedded verbatim in `_ROLE_DEFAULT` (written fresh for this spec — one weird-history using a capsule, one debate-mode) demonstrating the full formula. Exemplars must themselves pass `validate_formula` (tested).

## 2. `validate_formula` (deterministic, `studio/story_writer.py`)

Runs for story/weird/debate modes after `validate_story` passes (punch skips). All checks case-insensitive:

- **Hook**: must contain "you" or "your"; must NOT contain resolution phrases ("that's why", "the answer", "here's how", "the lesson"); existing statement + ≤15-word rules unchanged.
- **Reframe stakes**: "you" or "your" appears within the first 25 words.
- **No early resolution**: resolution vocabulary ("the lesson", "that's why", "the answer is", "this means", "the secret is") absent from the first two-thirds of the reframe (by word count).
- **Cliffhanger marker**: middle third of the reframe contains ≥1 sentence starting with "Then", "Until", "But", "And nobody", "And no one" (unresolved-turn signal).
- Word budgets unchanged (total 140–215; reframe ≤185).
- Failure reasons are specific strings fed to the existing corrective retry; both persona drafts must pass `validate_story` AND `validate_formula` before rubric scoring.

## 3. Material expansion + repetition kill

- **`src/content/weird_stories.py`**: `WEIRD_CAPSULES` 26 → ≥60. New capsules must be historically attested with `source_note` (candidates: Diogenes' pirate capture & slave auction, Epictetus' lame leg, Zeno's shipwreck-to-porch, Cleanthes the night water-carrier, Hipparchia's marriage terms, Crates the door-knocker, Chrysippus' laughing death, Socrates' battlefield trance at Potidaea, Cato refusing loot, Musonius in exile on Gyaros...). Every capsule keeps the schema {hook_fact, escalation, source_note, lesson_theme, send_cta}; every capsule gains a stable `key` (slug). Hypotheticals pool unchanged.
- **`material_key` tracking**: `posts` table gains a `material_key TEXT` column (migration in `data_store.init_db`, additive). `save_post`/`record_arc`-style helper `record_material(row_id, key)` called by the pipeline when a story used a capsule/debate topic/trend (key = capsule slug, debate topic slug, or `trend:<hash8>`).
- **Exclusion**: `pick_weird(row, exclude=set())` / `pick_debate(row, exclude=set())` skip excluded keys deterministically (next index in rotation order); when ALL keys excluded → least-recently-used wins (fallback, never empty). `_build_story_beats` builds `exclude` from the last 20 posts' material_keys (local DB query, best-effort → empty set on error).

## 4. Back-compat

- Punch mode: `validate_formula` not applied.
- Optimizer champion store: the default-hash re-seed migration (already live) promotes the new prompt automatically.
- Old posts without material_key: NULL, excluded from the exclusion query naturally.

## 5. Error handling

Never-crash intact: formula rejection → corrective retry (reason-specific) → fallback arc. DB migration additive; tracking failures → empty exclude set. Capsule pool never returns None.

## 6. Testing

- `validate_formula`: each check's failure case + a passing script; both exemplars pass it (import them in the test).
- Pool: ≥60 capsules, all safe (`is_unsafe` + `mentions_named_person` on joined fields), all keyed uniquely, all send_cta contain "Send this".
- Exclusion: excluded keys skipped; full-exclusion → LRU fallback; determinism per row.
- `record_material` + migration: fixture DB round-trip; `_build_story_beats` passes exclude (mocked write_story captures material).
- Gate: dry-run render, read the generated script — verify formula by inspection; live acceptance post.

## Not in scope

Script-doctor agent, new arcs, VO/visual changes, caption changes, punch-mode changes.
