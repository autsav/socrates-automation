### Task 7: Insights re-poll window

**Files:**
- Modify: `src/analytics/metrics.py` (add `ingest_window`), `.github/workflows/analytics.yml` (call it)
- Test: `tests/test_metrics_window.py`

**Interfaces:**
- Consumes: existing `fetch_post_metrics(post_id, access_token, ig_account_id) -> dict` and the existing `post_metrics` table (post_id, likes, comments, shares, reach, impressions, saved).
- Produces: `ingest_window(access_token, ig_account_id, db_path, days=7, dry_run=False) -> int` — for every live post 1–7 days old, fetch and UPSERT metrics (`INSERT OR REPLACE`), returning the number updated. Existing `ingest_pending` untouched.

- [ ] **Step 1: Failing test**

```python
# tests/test_metrics_window.py
"""Phase-2 poller: posts 1-7 days old get RE-polled (metrics keep moving)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics import metrics


def _seed(db, post_id, days_ago, with_metrics=False):
    db.execute("INSERT INTO posts (post_id, posted_at, dry_run) "
               "VALUES (?, datetime('now', ?), 0)", (post_id, f"-{days_ago} days"))
    if with_metrics:
        db.execute("INSERT INTO post_metrics (post_id, shares, reach) "
                   "VALUES (?, 1, 100)", (post_id,))


def test_window_repolls_and_upserts(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE posts (post_id TEXT, posted_at TEXT, dry_run INT)")
    db.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, likes INT "
               "DEFAULT 0, comments INT DEFAULT 0, shares INT DEFAULT 0, "
               "reach INT DEFAULT 0, impressions INT DEFAULT 0, saved INT DEFAULT 0)")
    _seed(db, "fresh", 2, with_metrics=True)   # has stale metrics -> re-polled
    _seed(db, "old", 12)                        # outside window -> skipped
    db.commit(); db.close()

    monkeypatch.setattr(metrics, "fetch_post_metrics",
                        lambda pid, tok, ig: {"likes": 9, "comments": 1,
                                              "shares": 5, "reach": 200,
                                              "impressions": 250, "saved": 3})
    n = metrics.ingest_window("tok", "ig", db_path=db_path)
    assert n == 1
    row = sqlite3.connect(db_path).execute(
        "SELECT shares, reach FROM post_metrics WHERE post_id='fresh'").fetchone()
    assert row == (5, 200)
```

- [ ] **Step 2: Run** — FAIL `AttributeError: ingest_window`.

- [ ] **Step 3: Implement** in `src/analytics/metrics.py` (match the module's existing sqlite style):

```python
def ingest_window(access_token, ig_account_id, db_path, days=7, dry_run=False):
    """Re-poll every live post 1-{days} days old and upsert its metrics —
    engagement keeps moving for a week, one snapshot at 24h under-counts
    sends (spec 2.1). Returns the number of posts updated."""
    import sqlite3
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT post_id FROM posts WHERE post_id IS NOT NULL AND dry_run=0 "
            "AND posted_at <= datetime('now', '-1 day') "
            "AND posted_at >= datetime('now', ?)", (f"-{days} days",)).fetchall()
        updated = 0
        for (post_id,) in rows:
            if dry_run:
                print(f"    [dry-run] would re-poll {post_id}")
                continue
            try:
                m = fetch_post_metrics(post_id, access_token, ig_account_id)
            except Exception as e:  # noqa: BLE001 - one dead post never stops the sweep
                print(f"    [analytics] {post_id} failed ({e}) — skipping")
                continue
            con.execute(
                "INSERT OR REPLACE INTO post_metrics "
                "(post_id, likes, comments, shares, reach, impressions, saved) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (post_id, m.get("likes", 0), m.get("comments", 0),
                 m.get("shares", 0), m.get("reach", 0),
                 m.get("impressions", 0), m.get("saved", 0)))
            updated += 1
        con.commit()
        return updated
    finally:
        con.close()
```

In `.github/workflows/analytics.yml`, after the existing ingest step, add a step running (mirror the existing step's env exactly):

```yaml
      - name: Re-poll 7-day window
        run: python -c "from src.analytics.metrics import ingest_window; import os; print(ingest_window(os.environ['META_ACCESS_TOKEN'], os.environ['IG_ACCOUNT_ID'], 'data/pipeline.db'))"
```

- [ ] **Step 4: Run** — test passes; full suite green.
- [ ] **Step 5: Commit** — `git add src/analytics/metrics.py .github/workflows/analytics.yml tests/test_metrics_window.py && git commit -m "feat(loop): 7-day insights re-poll window (spec 2.1)"`

