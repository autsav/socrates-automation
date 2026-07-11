# Reliability Core (A1–A4) — Design

**Date:** 2026-07-11
**Status:** Approved (design)
**Source:** CRITIQUE.md §A1–A4 (verified against live source 2026-07-11)
**Sub-project 1 of 3** in the quality program (2: image+typography; 3: reel motion+hook).

## 1. Goal

Make the persistence + guard layer work so the A/B bandit, dedup guard, and
analytics stop silently resetting or failing every CI run. Four surgical fixes;
no behavior change to content generation.

## 2. Non-goals (YAGNI)

- No changes to content/image/reel generation.
- Not fixing A5 (manual-mode publish) or A6 (reconcile marker) — queued separately.
- No migration to an external datastore; git remains the store (decision A2).

## 3. Decisions (locked)

| # | Decision |
|---|---|
| A2 store | **Commit the DB to git.** Force-add an initial `data/pipeline.db`; both workflows get `permissions: contents: write`; "Restore" fails loudly if the DB is absent. |
| A3 dedup | **First-writer-wins per (day, slot) for real posts.** Atomic via a partial UNIQUE index; `save_post` signals conflict. |

## 4. Architecture (four independent fixes)

### A1 — analytics DB commit
**File:** `.github/workflows/analytics.yml`.
- Change `git add data/pipeline.db` → `git add -f data/pipeline.db` (the path is
  gitignored; `daily_post.yml:187` already uses `-f`).
- Add a top-level `permissions: { contents: write }` to the workflow so the
  commit/push cannot 403.

### A2 — durable DB across runs
**Files:** repo (`data/pipeline.db`), `.github/workflows/daily_post.yml`,
`.github/workflows/analytics.yml`, `.gitignore`.
- Create a fresh schema-only DB via `init_db()` and **force-add** it once
  (`git add -f data/pipeline.db`). Update `.gitignore` so the DB can stay
  tracked: git **cannot** re-include a file whose parent directory is excluded,
  so the current `data/` line (which excludes the whole **directory**) must
  become `data/*` (exclude the directory's *contents*, which a later negation
  CAN re-include). Keep `*.db`/`-shm`/`-wal` ignored globally, and add the
  negation as the **last** matching rule (last-match-wins). Concretely, replace
  the bare `data/` line with `data/*` and append at the end of `.gitignore`:
  ```
  data/*
  *.db
  *.db-shm
  *.db-wal
  !data/pipeline.db
  ```
  The trailing `!data/pipeline.db` wins over both `data/*` and `*.db`, so only
  that one DB is tracked; every other `.db`/wal/shm anywhere stays ignored.
  (Force-add tracks it regardless; this keeps it from showing as ignored and lets
  a plain `git add data/pipeline.db` work in the workflows.)
- Add `permissions: { contents: write }` to `daily_post.yml` (analytics covered
  by A1).
- Harden the "Restore SQLite database from repo" step in `daily_post.yml`: if
  `data/pipeline.db` is missing after checkout, **exit non-zero with a clear
  message** instead of silently continuing on the freshly-init'd empty DB.
  (Order: checkout provides the tracked DB; only run `init_db()` as a no-op
  guard that does not overwrite an existing DB — verify `init_db` uses
  `CREATE TABLE IF NOT EXISTS`, which it does.)

### A3 — atomic dedup guard
**File:** `src/core/data_store.py`; call sites in `pipeline.py`.
- **Schema/migration:** add column `post_date TEXT` defaulting to `date('now')`
  to `posts`, and a partial unique index
  `CREATE UNIQUE INDEX IF NOT EXISTS ux_posts_slot_day ON posts(post_date, posting_slot) WHERE dry_run = 0`.
  Wrap in an idempotent migration inside `init_db` (add column only if absent via
  `PRAGMA table_info`; `CREATE … IF NOT EXISTS` for the index) so existing DBs
  upgrade in place.
- **`save_post`** becomes an atomic claim: `INSERT … ON CONFLICT(post_date, posting_slot) DO NOTHING`
  (the partial index is the conflict target for `dry_run=0`). Change its return
  type to `int | None`: the new row id on insert, or **`None` when the slot was
  already claimed today** (conflict). `dry_run=1` inserts never conflict (outside
  the partial index) so they always return an id.
- **`has_posted_today(slot)`** keyed on the new `post_date` column
  (`WHERE post_date = date('now') AND posting_slot = ? AND dry_run = 0`) so it is
  consistent with the claim (it previously keyed on `posted_at`, which is `NULL`
  until `mark_posted`, so it only ever saw published rows).
- **`pipeline.py`** (both `save_post` call sites): treat a `None` return as
  "slot already claimed today → skip publishing this slot" (same effect as the
  existing `has_posted_today` early-out). The pre-check via `has_posted_today`
  may remain as a fast path, but correctness now rests on the atomic `save_post`.

### A4 — stop the inert token refresh
**Files:** `src/core/token_manager.py`, `src/core/data_store.py`.
- **Skip refresh without creds:** in `refresh_if_needed` (or `get_valid_token_with_fallback`),
  if `app_id`/`app_secret` are falsy, return the current token unchanged and do
  **not** issue the Graph POST.
- **Persist an `expires_at`:** on seed (`data_store.py:106`, currently `NULL`)
  write an estimated `expires_at ≈ now + 60 days` (long-lived token default), and
  on any successful token use persist a best-effort `expires_at` even when the
  token value is unchanged. This makes `_is_token_expiring_soon` stop returning
  `True` forever.

## 5. Error handling

- A2 Restore missing DB → hard fail (loud), never silent empty-DB continuation.
- A3 migration is idempotent and safe to run on every `init_db` call.
- A4 no-creds path is silent success (token returned), zero network calls.
- All fixes preserve the existing graceful behavior of the content pipeline.

## 6. Testing

Run Python tests with the 3.11 `.venv` (`.venv/bin/python -m pytest`).
- **A3:** migration idempotent (run `init_db` twice, one `post_date` column, one
  index); two `save_post(dry_run=False)` for same (today, slot) → first returns
  int, second returns `None`; two `save_post(dry_run=True)` same slot → both
  return ints (exempt); `has_posted_today` reflects a claimed (not-yet-published)
  row.
- **A4:** `refresh_if_needed` with empty creds makes no network call and returns
  the input token (assert via monkeypatched requests that it is never called);
  seed writes a non-`NULL` `expires_at`; `_is_token_expiring_soon` future date → False.
- **A1/A2:** a YAML lint/parse test asserting `analytics.yml` uses
  `git add -f data/pipeline.db` and both workflows declare
  `permissions: contents: write`; assert `data/pipeline.db` is tracked
  (`git ls-files`) and `.gitignore` negates it.
- Full suite stays green apart from the 2 known pre-existing `test_reel_composer.py`
  ffmpeg failures.

## 7. Files touched

| File | Change |
|---|---|
| `.github/workflows/analytics.yml` | `-f` on git add; `permissions: contents: write` |
| `.github/workflows/daily_post.yml` | `permissions: contents: write`; Restore fails loudly on missing DB |
| `.gitignore` | `!data/pipeline.db` negation |
| `data/pipeline.db` | new tracked schema-only DB (force-added) |
| `src/core/data_store.py` | `post_date` column + partial unique index migration; `save_post` atomic claim returning `int \| None`; `has_posted_today` keyed on `post_date`; seed `expires_at` |
| `src/core/token_manager.py` | skip refresh without creds; persist estimated `expires_at` |
| `pipeline.py` | handle `save_post` → `None` as "slot already claimed" at both call sites |
| `tests/…` | new tests per §6 |
