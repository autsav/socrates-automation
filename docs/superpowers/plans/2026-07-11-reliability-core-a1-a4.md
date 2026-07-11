# Reliability Core (A1–A4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four reliability defects (A1–A4) so the SQLite state persists across CI, the analytics commit succeeds, the dedup guard is atomic, and the token refresh stops firing a failing network call every run.

**Architecture:** Four independent fixes. A4 (token) and A3 (data_store dedup) are pure-Python + tests. A3 also needs a small guard at two `pipeline.py` call sites. A1/A2 are CI-workflow + `.gitignore` + a committed schema-only DB, verified secret-free.

**Tech Stack:** Python 3.11 (repo `.venv`), sqlite3, pytest; GitHub Actions YAML.

## Global Constraints

- **Run Python tests with the 3.11 venv:** `.venv/bin/python -m pytest …` (system python is 3.9 and cannot import the repo).
- **The committed `data/pipeline.db` MUST NOT contain a real token.** `init_db()` seeds `token_state` from `META_ACCESS_TOKEN`; create the committed DB with that env var UNSET and assert `token_state` is empty before force-adding. Leaking the Meta token into git is a security incident.
- **First-writer-wins dedup** applies only to real posts (`dry_run = 0`); dry-run inserts are exempt.
- **Beats/content generation behavior unchanged** — these fixes touch only persistence, guards, CI, and token handling.
- 2 pre-existing `tests/test_reel_composer.py` failures (local ffmpeg/libx264) are unrelated; "green" means no NEW failures.
- **Branch:** `feat/reliability-core-a1-a4` (already checked out).

---

### Task 1: A4 — stop the inert token refresh

Skip the Graph refresh when app creds are absent, and persist a real `expires_at` so `_is_token_expiring_soon` stops returning `True` forever.

**Files:**
- Modify: `src/core/token_manager.py` (`refresh_if_needed`, `get_valid_token_with_fallback`)
- Modify: `src/core/data_store.py` (token seed in `init_db`, ~line 100-108)
- Test: `tests/test_token_refresh_guard.py` (NEW — unique name avoids the `socrates_pipeline/tests` collision)

**Interfaces:**
- `refresh_if_needed(current_token, app_id, app_secret, expires_at=None) -> str` — unchanged signature; new behavior: returns `current_token` immediately (no network) when `app_id` or `app_secret` is falsy.
- `init_db()` seed writes a non-NULL `expires_at`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_token_refresh_guard.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import src.core.token_manager as tm
import src.core.data_store as ds


def test_refresh_skips_network_without_creds(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network must not be called when creds are absent")
    monkeypatch.setattr(tm.requests, "post", boom)
    assert tm.refresh_if_needed("tok123", app_id="", app_secret="", expires_at=None) == "tok123"


def test_init_db_seeds_token_with_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setenv("META_ACCESS_TOKEN", "seedtok")
    ds.init_db()
    state = ds.get_token("meta")
    assert state is not None and state["expires_at"] is not None


def test_get_valid_token_persists_estimate_when_expiry_missing(monkeypatch):
    saved = {}
    monkeypatch.setattr(ds, "get_token", lambda s: {"token": "tok", "expires_at": None})
    monkeypatch.setattr(ds, "save_token", lambda s, t, e=None: saved.update(service=s, token=t, expires=e))

    class Cfg:
        META_APP_ID = ""
        META_APP_SECRET = ""
        META_ACCESS_TOKEN = "env"

    assert tm.get_valid_token_with_fallback(Cfg()) == "tok"
    assert saved.get("expires") is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_token_refresh_guard.py -v`
Expected: FAIL — network guard not present / seed writes NULL / no estimate persisted.

- [ ] **Step 3: Implement the creds skip in `refresh_if_needed`**

In `src/core/token_manager.py`, add at the very top of `refresh_if_needed` (before the `_is_token_expiring_soon` check):

```python
    if not app_id or not app_secret:
        print("  [token] No app_id/secret configured — skipping refresh")
        return current_token
```

- [ ] **Step 4: Persist an estimate in `get_valid_token_with_fallback`**

In `src/core/token_manager.py`, replace this block:

```python
            token = refresh_if_needed(state["token"], cfg.META_APP_ID, cfg.META_APP_SECRET, expires_at)
            if token != state["token"]:
                new_expiry = datetime.now(timezone.utc) + timedelta(days=60)
                save_token("meta", token, new_expiry)
            return token
```

with:

```python
            token = refresh_if_needed(state["token"], cfg.META_APP_ID, cfg.META_APP_SECRET, expires_at)
            if token != state["token"]:
                save_token("meta", token, datetime.now(timezone.utc) + timedelta(days=60))
            elif expires_at is None:
                # Persist an estimate so a NULL-expiry token stops being re-checked every run.
                save_token("meta", token, datetime.now(timezone.utc) + timedelta(days=60))
            return token
```

- [ ] **Step 5: Seed a non-NULL expiry in `init_db`**

In `src/core/data_store.py`, replace the seed insert:

```python
                cursor.execute(
                    "INSERT INTO token_state (service, token, expires_at) VALUES (?, ?, NULL)",
                    ("meta", env_token),
                )
```

with (note: `datetime`/`timedelta` are already imported at the top of `data_store.py`):

```python
                seed_expiry = (datetime.utcnow() + timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO token_state (service, token, expires_at) VALUES (?, ?, ?)",
                    ("meta", env_token, seed_expiry),
                )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_token_refresh_guard.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add src/core/token_manager.py src/core/data_store.py tests/test_token_refresh_guard.py
git commit -m "fix(token): skip refresh without creds; persist estimated expires_at (A4)"
```

---

### Task 2: A3 — atomic dedup in `data_store`

Add a `post_date` column + partial unique index and make `save_post` an atomic claim.

**Files:**
- Modify: `src/core/data_store.py` (`init_db` schema/migration, `save_post`, `has_posted_today`)
- Test: `tests/test_data_store_dedup.py` (NEW — unique name avoids the `socrates_pipeline/tests` collision)

**Interfaces:**
- `save_post(quote_text, audience, mood, caption_variant, posting_slot, dry_run=False, hook_id=None) -> int | None` — returns the new row id, or **`None`** when a `dry_run=0` post for `(today, posting_slot)` was already claimed. `dry_run=1` inserts are exempt and always return an id.
- `has_posted_today(slot) -> bool` — now keyed on `post_date`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_data_store_dedup.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import src.core.data_store as ds


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DB_PATH", tmp_path / "t.db")
    ds.init_db()
    return ds


def test_migration_idempotent(db):
    db.init_db()  # second run must not error
    conn = db._get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(posts)")}
    idx = {r[1] for r in conn.execute("PRAGMA index_list(posts)")}
    conn.close()
    assert "post_date" in cols
    assert "ux_posts_slot_day" in idx


def test_save_post_dedup_real(db):
    a = db.save_post("q", "aud", "calm_stoic", 0, 1, dry_run=False)
    b = db.save_post("q2", "aud", "calm_stoic", 0, 1, dry_run=False)
    assert isinstance(a, int)
    assert b is None


def test_save_post_dry_run_exempt(db):
    a = db.save_post("q", "aud", "calm_stoic", 0, 1, dry_run=True)
    b = db.save_post("q", "aud", "calm_stoic", 0, 1, dry_run=True)
    assert isinstance(a, int) and isinstance(b, int)


def test_has_posted_today_sees_claim(db):
    db.save_post("q", "aud", "calm_stoic", 0, 2, dry_run=False)
    assert db.has_posted_today(2) is True
    assert db.has_posted_today(3) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_data_store_dedup.py -v`
Expected: FAIL — no `post_date` column / no `ux_posts_slot_day` index / `save_post` never returns None.

- [ ] **Step 3: Add `post_date` to the CREATE TABLE**

In `src/core/data_store.py`, in the `CREATE TABLE IF NOT EXISTS posts (...)` block, change the last column line from:

```python
                hook_id TEXT DEFAULT NULL
```

to:

```python
                hook_id TEXT DEFAULT NULL,
                post_date TEXT DEFAULT (date('now'))
```

- [ ] **Step 4: Add migration + partial unique index**

In `src/core/data_store.py`, immediately after the existing `hook_id` migration block (the `if "hook_id" not in post_columns:` line and its `ALTER TABLE`), add:

```python
        # Migration: add post_date + a partial unique index so the dedup guard
        # is atomic (first-writer-wins per day/slot for real posts). SQLite
        # forbids a non-constant DEFAULT on ADD COLUMN, so the column is added
        # nullable and save_post sets post_date=date('now') explicitly.
        if "post_date" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN post_date TEXT")
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_posts_slot_day "
            "ON posts(post_date, posting_slot) WHERE dry_run = 0"
        )
```

- [ ] **Step 5: Make `save_post` an atomic claim**

In `src/core/data_store.py`, replace the whole `save_post` function with:

```python
def save_post(
    quote_text: str,
    audience: str,
    mood: str,
    caption_variant: int,
    posting_slot: int,
    dry_run: bool = False,
    hook_id: str | None = None,
) -> int | None:
    """Atomically claim + insert a post record for (today, posting_slot).

    Returns the new row id, or None when a non-dry-run post for this slot was
    already claimed today (the partial unique index fired). dry_run inserts are
    exempt from the guard and always return an id.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO posts
              (quote_text, audience, mood, caption_variant, posting_slot,
               posted_at, dry_run, hook_id, post_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'))
            ON CONFLICT(post_date, posting_slot) WHERE dry_run = 0 DO NOTHING
            """,
            (quote_text, audience, mood, caption_variant, posting_slot,
             None, dry_run, hook_id),
        )
        inserted = cursor.rowcount == 1
        conn.commit()
        return cursor.lastrowid if inserted else None
    finally:
        conn.close()
```

- [ ] **Step 6: Key `has_posted_today` on `post_date`**

In `src/core/data_store.py`, in `has_posted_today`, replace the SQL:

```python
            SELECT 1 FROM posts
            WHERE posted_at >= date('now')
              AND posting_slot = ?
              AND dry_run = FALSE
            LIMIT 1
```

with:

```python
            SELECT 1 FROM posts
            WHERE post_date = date('now')
              AND posting_slot = ?
              AND dry_run = 0
            LIMIT 1
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_data_store_dedup.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Run the existing data_store-touching suite for regressions**

Run: `.venv/bin/python -m pytest tests/ -q -k "data_store or ab_test or analytics"`
Expected: no NEW failures (pre-existing ffmpeg failures are unrelated and won't appear in this selection).

- [ ] **Step 9: Commit**

```bash
git add src/core/data_store.py tests/test_data_store_dedup.py
git commit -m "fix(data_store): atomic per-day/slot dedup via partial unique index (A3)"
```

---

### Task 3: A3 — handle the atomic claim at the pipeline call sites

Treat a `None` return from `save_post` as "slot already claimed by a concurrent run — skip to avoid double-post."

**Files:**
- Modify: `pipeline.py` (two `save_post` sites: in `_run_pov_reel` ~line 515, and in `run_pipeline` ~line 748)

**Interfaces:**
- Consumes: `save_post(...) -> int | None` (Task 2).
- Both functions already return a dict; `run_pipeline` uses `{"skipped": True, "reason": ...}` for its `has_posted_today` early-out (line 614). Reuse that shape.

- [ ] **Step 1: Read both call sites**

Run: `sed -n '513,524p' pipeline.py` and `sed -n '746,757p' pipeline.py`
Confirm each is `post_row_id = save_post(...)` followed by later use of `post_row_id` (e.g. `mark_posted`). The guard must go immediately after the `save_post(...)` call, before any use of `post_row_id`.

- [ ] **Step 2: Guard the `_run_pov_reel` site**

In `pipeline.py`, immediately after the `post_row_id = save_post(...)` call inside `_run_pov_reel` (the one with `caption_variant=-1`), insert:

```python
    if post_row_id is None:
        log.warning(
            f"  [dedup] slot {slot} already claimed today (concurrent run) — "
            f"skipping to avoid a double-post"
        )
        return {"skipped": True, "reason": f"slot {slot} already claimed today"}
```

- [ ] **Step 3: Guard the `run_pipeline` site**

In `pipeline.py`, immediately after the `post_row_id = save_post(...)` call inside `run_pipeline` (the one with `caption_variant=caption_variant`, in the non-pov path), insert the same guard:

```python
    if post_row_id is None:
        log.warning(
            f"  [dedup] slot {slot} already claimed today (concurrent run) — "
            f"skipping to avoid a double-post"
        )
        return {"skipped": True, "reason": f"slot {slot} already claimed today"}
```

- [ ] **Step 4: Verify pipeline parses and the suite is green**

Run: `.venv/bin/python -c "import ast; ast.parse(open('pipeline.py').read()); print('pipeline ok')"`
Expected: `pipeline ok`

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: only the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures; no new failures.

- [ ] **Step 5: Commit**

```bash
git add pipeline.py
git commit -m "fix(pipeline): skip publish when save_post reports slot already claimed (A3)"
```

---

### Task 4: A1 + A2 — durable, secret-free DB and correct CI commits

Track a schema-only `data/pipeline.db`, fix the analytics force-add, grant write permission, and make the daily workflow fail loudly on a missing DB.

**Files:**
- Modify: `.github/workflows/analytics.yml`
- Modify: `.github/workflows/daily_post.yml`
- Modify: `.gitignore`
- Create (tracked): `data/pipeline.db`
- Test: `tests/test_workflow_reliability.py` (NEW)

**Interfaces:** none (CI + repo state). Depends on Task 2's schema being final so the committed DB carries `post_date` + the index.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workflow_reliability.py`:

```python
import subprocess
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text()


def test_analytics_uses_force_add():
    assert "git add -f data/pipeline.db" in _read(".github/workflows/analytics.yml")


def test_both_workflows_have_write_permission():
    for wf in (".github/workflows/analytics.yml", ".github/workflows/daily_post.yml"):
        t = _read(wf)
        assert "permissions:" in t and "contents: write" in t, f"{wf} missing write permission"


def test_daily_post_fails_loudly_on_missing_db():
    t = _read(".github/workflows/daily_post.yml")
    assert "data/pipeline.db missing" in t and "exit 1" in t


def test_gitignore_negates_pipeline_db():
    assert "!data/pipeline.db" in _read(".gitignore")


def test_pipeline_db_is_tracked():
    out = subprocess.run(
        ["git", "ls-files", "data/pipeline.db"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    assert out == "data/pipeline.db", "data/pipeline.db must be tracked in git"


def test_committed_db_has_no_token():
    conn = sqlite3.connect(str(ROOT / "data" / "pipeline.db"))
    try:
        n = conn.execute("SELECT count(*) FROM token_state").fetchone()[0]
    finally:
        conn.close()
    assert n == 0, "committed pipeline.db must not contain a token (secret leak)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_workflow_reliability.py -v`
Expected: FAIL on every assertion (no `-f`, no permissions, no fail-loud, no negation, DB untracked).

- [ ] **Step 3: Fix `.gitignore`**

In `.gitignore`, under `# Data & logs`, replace the `data/` line with `data/*` and append `!data/pipeline.db` as the LAST rule of that group. The result must read:

```
# Data & logs
data/*
logs/
*.db
*.db-shm
*.db-wal
!data/pipeline.db
```

(The trailing negation wins by last-match; `data/*` — not bare `data/` — is required because git cannot re-include a file under a fully-excluded directory.)

- [ ] **Step 4: Fix `analytics.yml` (A1) — force-add + permissions**

In `.github/workflows/analytics.yml`:
1. Add a top-level permissions block. Immediately after the `on:` block (before `jobs:`), insert:

```yaml
permissions:
  contents: write
```

2. In the "Commit SQLite database back to repo" step, change:

```yaml
          git add data/pipeline.db
```

to:

```yaml
          git add -f data/pipeline.db
```

- [ ] **Step 5: Fix `daily_post.yml` (A2) — permissions + fail-loud restore**

In `.github/workflows/daily_post.yml`:
1. Add the same top-level permissions block immediately after the `on:` block (before `jobs:`):

```yaml
permissions:
  contents: write
```

2. Replace the "Init SQLite database" + "Restore SQLite database from repo" steps:

```yaml
      - name: Init SQLite database
        run: python -c "from src.core.data_store import init_db; init_db()"

      - name: Restore SQLite database from repo
        run: |
          if [ -f "data/pipeline.db" ]; then
            echo "✅ Restored pipeline.db from repo ($(du -h data/pipeline.db | cut -f1))"
          else
            echo "🆕 No existing database — fresh start"
            mkdir -p data
          fi
```

with (verify BEFORE init, so init can't mask a DB missing from checkout):

```yaml
      - name: Verify tracked SQLite database present
        run: |
          if [ ! -f "data/pipeline.db" ]; then
            echo "❌ data/pipeline.db missing after checkout — it must be committed to the repo (spec A2). Refusing to continue on an empty DB."
            exit 1
          fi
          echo "✅ pipeline.db present from repo ($(du -h data/pipeline.db | cut -f1))"

      - name: Init/migrate SQLite database
        run: python -c "from src.core.data_store import init_db; init_db()"
```

- [ ] **Step 6: Create the tracked, secret-free DB**

Run (the `env -u META_ACCESS_TOKEN` guarantees no token is seeded; the assert enforces it):

```bash
cd "$(git rev-parse --show-toplevel)"
# Back up any local DB so we commit a pristine schema-only one (avoid leaking a real token).
[ -f data/pipeline.db ] && mv -f data/pipeline.db data/pipeline.db.local.bak || true
env -u META_ACCESS_TOKEN .venv/bin/python -c "from src.core.data_store import init_db; init_db()"
.venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/pipeline.db'); n=c.execute('SELECT count(*) FROM token_state').fetchone()[0]; c.close(); print('token_state rows:', n); assert n==0, 'committed DB must not contain a token'"
git add -f data/pipeline.db
```

Expected: `token_state rows: 0`, and `git status` shows `data/pipeline.db` staged as a new tracked file. (Do NOT add `data/pipeline.db-wal`/`-shm` — they stay ignored.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_workflow_reliability.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Commit**

```bash
git add .gitignore .github/workflows/analytics.yml .github/workflows/daily_post.yml data/pipeline.db tests/test_workflow_reliability.py
git commit -m "fix(ci): durable secret-free pipeline.db + force-add + write perms + fail-loud restore (A1/A2)"
```

---

## Self-Review

**Spec coverage:**
- A1 (force-add + permissions in analytics.yml) → Task 4 Steps 3-4. ✓
- A2 (commit DB, permissions, fail-loud restore, gitignore negation) → Task 4 Steps 3,5,6. ✓
- A3 (post_date column, partial unique index, atomic save_post, has_posted_today, pipeline guards) → Task 2 + Task 3. ✓
- A4 (skip refresh without creds, persist expires_at, seed non-NULL) → Task 1. ✓
- Testing (§6): A3 dedup/migration, A4 network-skip/seed, A1/A2 YAML+tracking+no-token → Tasks 1,2,4 tests. ✓
- Security constraint (no token in committed DB) → Task 4 Step 6 (`env -u` + assert) + `test_committed_db_has_no_token`. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. Task 3 Step 1 is a read step (legitimate) followed by exact guard code.

**Type consistency:** `save_post(...) -> int | None` defined in Task 2, consumed in Task 3 (guards on `None`). `has_posted_today` keyed on `post_date` in both Task 2 (definition) and the schema (Task 2 Step 3-4). `ux_posts_slot_day` index name identical in Task 2 impl and Task 2 test. `permissions: contents: write` string identical across Task 4 and its test. ✓

**Ordering:** Task 4 (committed DB) runs last so the DB carries Task 2's final schema (`post_date` + index). ✓
