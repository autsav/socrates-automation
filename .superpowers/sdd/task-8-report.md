# Task 8 report — Performance digest

## Status: done, all tests green, committed.

## Real `posts` schema (verified in `src/core/data_store.py:60-113`, `init_db`)

Columns: `id, quote_text, audience, mood, caption_variant, posting_slot, posted_at,
post_id, image_path, reel_path, dry_run, hook_id, post_date, seed,
opt_versions_json, trigger_keyword, arc`.

Key finding: **no `hook` or `caption` column exists.**

- `hook_id` (added by migration, `data_store.py:81-82`) is only an opaque
  template-key string (e.g. `"confrontation_2"`), chosen by
  `pick_best_hook()` in `src/analytics/hook_tracker.py`. The actual hook copy
  lives only in the in-code Python dict `HOOK_TEMPLATES`
  (`hook_tracker.py:19-100`) — never written to SQLite. Resolving `hook_id`
  → readable text requires a Python-side dict lookup, not a SQL join, so it
  was not usable inside `_rows`'s single query.
- The only sqlite table with "hook" in its name is `hook_performance`
  (`hook_tracker.py:249-256`) — metrics only (`hook_id, posted_at, saved,
  comments, reach`), no text column.
- Caption text is **never persisted to sqlite at all**. It's built in-memory
  (`quote_data["caption"]` / `_build_caption()` in
  `src/content/generate_quotes_excel.py`) and flows transiently through the
  pipeline to the poster/notifier, then dropped. The one place it does land
  on disk is `data/approvals.json` (a flat JSON file, not a DB table, and not
  joinable by `post_id` in SQL against `posts`/`post_metrics`).

### Adaptation

Per the brief's fallback instruction ("if hook text is genuinely unavailable,
use the caption's first line as the hook surrogate") — since caption isn't in
the schema either, I used the closest available equivalent: **`quote_text`**,
the only `NOT NULL`, always-populated, human-readable column on `posts`. I
take its first line (`_hook_surrogate()`) in case a quote spans multiple
lines, mirroring the "first line" spirit of the brief's fallback.

`_rows` query became:
```sql
SELECT p.arc, p.quote_text, m.shares, m.reach FROM posts p
JOIN post_metrics m ON p.post_id = m.post_id
WHERE p.dry_run=0 AND m.reach >= ?
```
(column `p.hook` → `p.quote_text`; everything else — `arc`, floor filter,
join shape — matched the brief as written since `arc` and `dry_run` do exist
on the real table).

Test fixture (`tests/test_performance_digest.py`) schema was adapted the same
way: `posts(post_id, arc, quote_text, dry_run)` instead of
`posts(post_id, arc, hook, dry_run)`, reusing the brief's same 4 sample rows
(values unchanged — they read fine as quote text, e.g.
`"Barefoot senator."`).

## Files

- `/Users/utsab1/Documents/socrates automation/src/analytics/performance_digest.py` — new
- `/Users/utsab1/Documents/socrates automation/tests/test_performance_digest.py` — new
- `/Users/utsab1/Documents/socrates automation/.gitignore` — added explicit
  `data/perf_digest.json` line (redundant with existing `data/*` blanket
  ignore + allowlist, but added per task instruction for explicitness/intent
  clarity)

## Safety / cold-start

- `build_digest` and `digest_text` wrap their entire body in try/except,
  including the `sqlite3.connect` + query against a DB file with no tables
  at all (e.g. a freshly created empty file) — confirmed via
  `test_build_digest_missing_tables_returns_empty` and
  `test_digest_text_cold_start_missing_db`, both added beyond the brief's
  original 2 tests to explicitly cover the "no tables yet" cold-start case
  the task description called out.
- Cache write to `data/perf_digest.json` wrapped in its own try/except
  (best-effort, never fails the digest).

## Test summary

- `tests/test_performance_digest.py`: 5 passed (2 from brief + 3 added:
  missing-db-file cold start, missing-tables cold start, all-3-views-present
  sanity check).
- Full suite: `685 passed, 1 warning` (pre-existing fastapi/httpx deprecation
  warning, unrelated).

## Git hygiene

- `data/pipeline.db` was dirtied by a concurrent process during the test
  run (per the brief's warning) — ran `git checkout -- data/pipeline.db`
  before staging, never added it.
- Committed exactly: `src/analytics/performance_digest.py`,
  `tests/test_performance_digest.py`, `.gitignore` — commit
  `12065ec`, message `feat(loop): per-agent performance digest (spec 2.2)`,
  no Co-Authored-By trailer.
- Other pre-existing unrelated working-tree modifications
  (`.superpowers/sdd/task-*-report.md`, `logs/notifications.jsonl`,
  `output/product/landing.html`, `quotes.xlsx`, untracked `.hermes/`,
  `remotion/public/bg.mp4`) were left untouched — out of scope for this task.

## Self-review

- Logic (ranking, TOP_N, reach floor, top/bottom dedup, cache write) is
  unchanged from the brief's reference implementation — only the hook-text
  source and query column changed.
- `_hook_surrogate` guards `None`/empty `quote_text` (returns `""`), so a
  post with an empty quote can't crash `.splitlines()`.
- No concerns. Ready for downstream tasks that consume `build_digest`/
  `digest_text`.

## Note

This file previously held a stale report from an unrelated prior task
("Task H — team/video_editor.py + team/engagement_strategist.py"); it has
been overwritten with the actual Task 8 report above.
