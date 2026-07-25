### Task 8: Performance digest

**Files:**
- Create: `src/analytics/performance_digest.py`
- Test: `tests/test_performance_digest.py`

**Interfaces:**
- Consumes: `posts` (post_id, arc, hook/caption columns — check actual column names in `data_store.init_db` before coding; the plan assumes `posts.arc` exists and hook/caption live in `posts.versions` JSON or columns) and `post_metrics`.
- Produces: `build_digest(db_path) -> dict` with keys `story_writer`, `copywriter`, `strategist`, each a list of `{"rank": "top"|"bottom", "arc": str, "hook": str, "sends_per_reach": float}`; `digest_text(view: str, db_path=DEFAULT) -> str` — human-readable block, `"No performance data yet."` when empty or on ANY exception (cold-start safe). Reach floor 100.

- [ ] **Step 1: Failing test**

```python
# tests/test_performance_digest.py
"""Per-agent digest: agents SEE their own results (spec 2.2)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.performance_digest import build_digest, digest_text


def _db(tmp_path):
    p = tmp_path / "t.db"
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE posts (post_id TEXT, arc TEXT, hook TEXT, dry_run INT)")
    db.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, shares INT, reach INT)")
    rows = [("p1", "weird", "Barefoot senator.", 9, 300),    # 3.0% -> top
            ("p2", "story", "Airport chaos.", 2, 400),        # 0.5%
            ("p3", "classic", "Plain quote.", 0, 500),        # 0.0% -> bottom
            ("p4", "weird", "Tiny reach.", 50, 50)]           # under floor -> excluded
    for pid, arc, hook, sh, re_ in rows:
        db.execute("INSERT INTO posts VALUES (?, ?, ?, 0)", (pid, arc, hook))
        db.execute("INSERT INTO post_metrics VALUES (?, ?, ?)", (pid, sh, re_))
    db.commit(); db.close()
    return p


def test_ranks_by_sends_per_reach_with_floor(tmp_path):
    d = build_digest(_db(tmp_path))
    sw = d["story_writer"]
    assert sw[0]["hook"] == "Barefoot senator." and sw[0]["rank"] == "top"
    assert all(e["hook"] != "Tiny reach." for e in sw)


def test_digest_text_cold_start(tmp_path):
    p = tmp_path / "empty.db"
    sqlite3.connect(p).close()
    assert digest_text("story_writer", db_path=p) == "No performance data yet."
```

- [ ] **Step 2: Run** — FAIL ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/analytics/performance_digest.py
"""Per-agent performance digests over posts x post_metrics (spec 2.2).
sends-per-reach is the north star; reach floor kills small-sample noise."""
import json
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "pipeline.db"
CACHE = DEFAULT_DB.parent / "perf_digest.json"
REACH_FLOOR = 100
TOP_N = 3


def _rows(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        return con.execute(
            "SELECT p.arc, p.hook, m.shares, m.reach FROM posts p "
            "JOIN post_metrics m ON p.post_id = m.post_id "
            "WHERE p.dry_run=0 AND m.reach >= ?", (REACH_FLOOR,)).fetchall()
    finally:
        con.close()


def build_digest(db_path=DEFAULT_DB) -> dict:
    try:
        scored = sorted(
            ({"arc": arc or "?", "hook": hook or "",
              "sends_per_reach": round(shares / reach, 4)}
             for arc, hook, shares, reach in _rows(db_path) if reach),
            key=lambda e: e["sends_per_reach"], reverse=True)
        if not scored:
            return {}
        top = [dict(e, rank="top") for e in scored[:TOP_N]]
        bottom = [dict(e, rank="bottom") for e in scored[-TOP_N:]
                  if e not in scored[:TOP_N]]
        view = top + bottom
        digest = {"story_writer": view, "copywriter": view, "strategist": view}
        try:
            CACHE.write_text(json.dumps(digest, indent=2))
        except Exception:  # noqa: BLE001 - cache is best-effort
            pass
        return digest
    except Exception:  # noqa: BLE001 - digest must never break generation
        return {}


def digest_text(view: str, db_path=DEFAULT_DB) -> str:
    d = build_digest(db_path).get(view) or []
    if not d:
        return "No performance data yet."
    lines = ["Recent performance (sends-per-reach — copy what wins, avoid what dies):"]
    for e in d:
        lines.append(f"- [{e['rank']}] {e['sends_per_reach']:.1%} | arc={e['arc']} "
                     f"| hook: {e['hook'][:80]}")
    return "\n".join(lines)
```

NOTE: verify `posts` column names (`arc`, and where the hook lives — if hook is inside `posts.versions` JSON, parse it; adjust `_rows` and the test schema to the real schema in `src/core/data_store.py:60-115`).

- [ ] **Step 4: Run** — both tests pass; full suite green.
- [ ] **Step 5: Commit** — `git add src/analytics/performance_digest.py tests/test_performance_digest.py && git commit -m "feat(loop): per-agent performance digest (spec 2.2)"`

