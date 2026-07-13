# Self-Improving Loop (Phase 1: Prompts) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-improving loop that autonomously proposes rewrites of the app's agent prompts, validates them, and surfaces winners to Telegram for one-tap approval — working from day one (0 engagement data) via an LLM critic.

**Architecture:** A unified *Optimizable registry* (SQLite) versions every tunable prompt with a champion + history. A `prompt_store.get(key, default)` loader lets studio agents read the champion (falling back to the hardcoded default = seed v1). A nightly `loop.py` runs a `prompt_critic` agent per prompt asset, guardrails the candidate, records it as a challenger + a Telegram proposal. Approval flips the champion. Real IG A/B (`opt_experiments`) is built now and auto-activates once `post_metrics` accrue.

**Tech Stack:** Python 3.11, SQLite (`data/pipeline.db`), existing `studio.client.StudioClient` (Anthropic), `src/core/notifier.py` + `approval.py` (Telegram), pytest.

## Global Constraints

- Python 3.11 venv: run everything via `.venv/bin/python`.
- **Never crash a post:** the optimizer is best-effort — every entry point wraps work in try/except and logs; a failure must never block or delay the posting pipeline.
- **No new heavy deps:** pure Python + stdlib + existing deps only (no numpy/sklearn/DSPy).
- All DB schema changes are **additive migrations** (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE … ADD COLUMN` guarded by a column check), matching `src/core/data_store.py` conventions.
- `data/pipeline.db` is git-tracked and must contain **no Meta token** (test `test_committed_db_has_no_token`); run `git checkout -- data/pipeline.db` before committing after any run that touches it.
- Store repo-relative paths only; no absolute local paths in DB/logs.
- New code lives under `src/optimizer/`; CLI entry is `optimize.py` at repo root.

---

### Task 1: Registry — schema + version CRUD

**Files:**
- Create: `src/optimizer/__init__.py` (empty)
- Create: `src/optimizer/registry.py`
- Test: `tests/test_optimizer_registry.py`

**Interfaces:**
- Produces:
  - `init_optimizer_db(db_path=DB_PATH) -> None`
  - `register_asset(key: str, kind: str, seed_value: str, db_path=DB_PATH) -> int` (idempotent; returns champion version id; seeds v1 as champion on first call)
  - `add_version(key: str, value: str, source: str, rationale: str, predicted_delta: float, status: str = "challenger", db_path=DB_PATH) -> int`
  - `get_champion(key: str, db_path=DB_PATH) -> dict | None` (keys: `id, key, version_num, value, source, rationale, status`)
  - `promote(version_id: int, db_path=DB_PATH) -> None` (sets that version `champion`, prior champion `retired`, updates `opt_assets.champion_version_id`)
  - `list_assets(db_path=DB_PATH) -> list[dict]`
  - `DB_PATH` (Path) — `data/pipeline.db`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_registry.py
import sqlite3
from pathlib import Path
import pytest
from src.optimizer import registry


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    return p


def test_register_seeds_champion_v1(db):
    vid = registry.register_asset("prompt.strategist.role", "prompt", "SEED TEXT", db)
    champ = registry.get_champion("prompt.strategist.role", db)
    assert champ["value"] == "SEED TEXT"
    assert champ["version_num"] == 1
    assert champ["status"] == "champion"
    assert champ["id"] == vid


def test_register_is_idempotent(db):
    v1 = registry.register_asset("k", "prompt", "A", db)
    v2 = registry.register_asset("k", "prompt", "DIFFERENT", db)
    assert v1 == v2
    assert registry.get_champion("k", db)["value"] == "A"  # seed not overwritten


def test_add_version_and_promote(db):
    registry.register_asset("k", "prompt", "A", db)
    cid = registry.add_version("k", "B", source="critic", rationale="tighter", predicted_delta=0.1, db_path=db)
    assert registry.get_champion("k", db)["value"] == "A"  # challenger not yet champion
    registry.promote(cid, db)
    champ = registry.get_champion("k", db)
    assert champ["value"] == "B"
    assert champ["version_num"] == 2
    # old champion retired
    con = sqlite3.connect(db)
    statuses = {r[0] for r in con.execute("select status from opt_versions where key='k'")}
    assert "retired" in statuses and "champion" in statuses


def test_get_champion_missing_returns_none(db):
    assert registry.get_champion("nope", db) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_registry.py -q`
Expected: FAIL (`ModuleNotFoundError: src.optimizer`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/optimizer/registry.py
"""Optimizable asset registry — versioned prompts/policies/weights in SQLite.

Each asset has a champion version (active) + history. Additive migrations only,
matching src/core/data_store.py conventions. Never raises on read paths."""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"


def _connect(db_path):
    return sqlite3.connect(str(db_path))


def init_optimizer_db(db_path=DB_PATH):
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS opt_assets (
                key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                champion_version_id INTEGER,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS opt_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                version_num INTEGER NOT NULL,
                value_json TEXT NOT NULL,
                source TEXT,
                rationale TEXT,
                predicted_delta REAL DEFAULT 0.0,
                status TEXT DEFAULT 'candidate',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS opt_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                champion_version_id INTEGER,
                challenger_version_id INTEGER,
                metric TEXT,
                status TEXT DEFAULT 'open',
                opened_at TEXT,
                closed_at TEXT,
                result_json TEXT
            );
            """
        )
        con.commit()
    finally:
        con.close()


def _row_to_version(r):
    if r is None:
        return None
    return {
        "id": r[0], "key": r[1], "version_num": r[2], "value": r[3],
        "source": r[4], "rationale": r[5], "predicted_delta": r[6], "status": r[7],
    }


def register_asset(key, kind, seed_value, db_path=DB_PATH):
    init_optimizer_db(db_path)
    con = _connect(db_path)
    try:
        existing = con.execute(
            "SELECT champion_version_id FROM opt_assets WHERE key=?", (key,)
        ).fetchone()
        if existing and existing[0] is not None:
            return existing[0]
        now = datetime.utcnow().isoformat()
        cur = con.execute(
            "INSERT INTO opt_versions (key, version_num, value_json, source, rationale, "
            "predicted_delta, status, created_at) VALUES (?,1,?,?,?,0.0,'champion',?)",
            (key, seed_value, "seed", "seed v1", now),
        )
        vid = cur.lastrowid
        con.execute(
            "INSERT OR REPLACE INTO opt_assets (key, kind, champion_version_id, created_at) "
            "VALUES (?,?,?,?)",
            (key, kind, vid, now),
        )
        con.commit()
        return vid
    finally:
        con.close()


def add_version(key, value, source, rationale, predicted_delta, status="challenger", db_path=DB_PATH):
    con = _connect(db_path)
    try:
        n = con.execute(
            "SELECT COALESCE(MAX(version_num),0)+1 FROM opt_versions WHERE key=?", (key,)
        ).fetchone()[0]
        cur = con.execute(
            "INSERT INTO opt_versions (key, version_num, value_json, source, rationale, "
            "predicted_delta, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (key, n, value, source, rationale, predicted_delta, status,
             datetime.utcnow().isoformat()),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def get_champion(key, db_path=DB_PATH):
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT id,key,version_num,value_json,source,rationale,predicted_delta,status "
            "FROM opt_versions WHERE key=? AND status='champion' "
            "ORDER BY version_num DESC LIMIT 1", (key,)
        ).fetchone()
        return _row_to_version(r)
    finally:
        con.close()


def promote(version_id, db_path=DB_PATH):
    con = _connect(db_path)
    try:
        row = con.execute("SELECT key FROM opt_versions WHERE id=?", (version_id,)).fetchone()
        if not row:
            return
        key = row[0]
        con.execute(
            "UPDATE opt_versions SET status='retired' WHERE key=? AND status='champion'", (key,)
        )
        con.execute("UPDATE opt_versions SET status='champion' WHERE id=?", (version_id,))
        con.execute(
            "UPDATE opt_assets SET champion_version_id=? WHERE key=?", (version_id, key)
        )
        con.commit()
    finally:
        con.close()


def list_assets(db_path=DB_PATH):
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT key, kind, champion_version_id FROM opt_assets").fetchall()
        return [{"key": r[0], "kind": r[1], "champion_version_id": r[2]} for r in rows]
    finally:
        con.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_registry.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/optimizer/__init__.py src/optimizer/registry.py tests/test_optimizer_registry.py
git commit -m "feat(optimizer): Optimizable registry — versioned assets in SQLite"
```

---

### Task 2: Prompt store — champion loader with lazy seed

**Files:**
- Create: `src/optimizer/prompt_store.py`
- Test: `tests/test_optimizer_prompt_store.py`

**Interfaces:**
- Consumes: `registry.register_asset`, `registry.get_champion`
- Produces: `get(key: str, default: str, db_path=registry.DB_PATH) -> str` — returns champion text; on first call for an unknown key, lazily `register_asset(key, "prompt", default)` and returns `default`. Never raises — on any DB error returns `default`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_prompt_store.py
import pytest
from src.optimizer import registry, prompt_store


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    return p


def test_get_seeds_and_returns_default(db):
    out = prompt_store.get("prompt.x", "DEFAULT", db)
    assert out == "DEFAULT"
    assert registry.get_champion("prompt.x", db)["value"] == "DEFAULT"


def test_get_returns_promoted_champion(db):
    prompt_store.get("prompt.x", "DEFAULT", db)          # seed v1
    cid = registry.add_version("prompt.x", "IMPROVED", "critic", "why", 0.2, db_path=db)
    registry.promote(cid, db)
    assert prompt_store.get("prompt.x", "DEFAULT", db) == "IMPROVED"


def test_get_never_raises_on_bad_db(tmp_path):
    bad = tmp_path / "nonexistent_dir" / "t.db"   # parent missing
    assert prompt_store.get("k", "FALLBACK", bad) == "FALLBACK"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_prompt_store.py -q`
Expected: FAIL (`ModuleNotFoundError` / `AttributeError`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/optimizer/prompt_store.py
"""Champion-prompt loader. Studio agents call get(key, default) instead of
using a static constant; the hardcoded default is the seed v1 + safety net."""
import logging
from src.optimizer import registry

log = logging.getLogger(__name__)


def get(key, default, db_path=registry.DB_PATH):
    try:
        registry.register_asset(key, "prompt", default, db_path)  # idempotent seed
        champ = registry.get_champion(key, db_path)
        return champ["value"] if champ else default
    except Exception as e:  # never break generation
        log.warning(f"[optimizer] prompt_store.get({key!r}) fell back to default ({e})")
        return default
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_prompt_store.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/optimizer/prompt_store.py tests/test_optimizer_prompt_store.py
git commit -m "feat(optimizer): prompt_store.get — champion loader with lazy seed"
```

---

### Task 3: Guardrails — placeholder preservation + safety

**Files:**
- Create: `src/optimizer/guardrails.py`
- Test: `tests/test_optimizer_guardrails.py`

**Interfaces:**
- Consumes: `src.content.trend_sources.is_unsafe`
- Produces: `validate_prompt_candidate(champion: str, candidate: str) -> tuple[bool, str]` — returns `(ok, reason)`. Fails if: candidate empty/whitespace; candidate drops any `{placeholder}` present in champion; `is_unsafe(candidate)` is True; candidate len < 40% or > 300% of champion (sanity bounds).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_guardrails.py
from src.optimizer import guardrails


def test_ok_when_placeholders_preserved_and_safe():
    champ = "You are the Strategist. Slot {slot}. Pool: {pool}."
    cand = "You are the Content Strategist. Today's slot is {slot}. Choose from {pool}."
    ok, reason = guardrails.validate_prompt_candidate(champ, cand)
    assert ok, reason


def test_fails_when_placeholder_dropped():
    champ = "Slot {slot}. Pool {pool}."
    cand = "Slot {slot}. Pick the best quote."   # dropped {pool}
    ok, reason = guardrails.validate_prompt_candidate(champ, cand)
    assert not ok and "pool" in reason.lower()


def test_fails_when_empty():
    ok, reason = guardrails.validate_prompt_candidate("A {x}", "   ")
    assert not ok


def test_fails_when_unsafe(monkeypatch):
    monkeypatch.setattr(guardrails, "is_unsafe", lambda s: True)
    ok, reason = guardrails.validate_prompt_candidate("A {x}", "A {x} improved")
    assert not ok and "unsafe" in reason.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_guardrails.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/optimizer/guardrails.py
"""Pre-experiment validation for prompt challengers. A candidate that fails
here never opens an experiment (and never reaches a real generation call)."""
import re

try:
    from src.content.trend_sources import is_unsafe
except Exception:  # defensive — never import-crash the optimizer
    def is_unsafe(_s):
        return False

_PLACEHOLDER = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")


def _placeholders(s):
    return set(_PLACEHOLDER.findall(s))


def validate_prompt_candidate(champion, candidate):
    if not candidate or not candidate.strip():
        return False, "candidate is empty"
    missing = _placeholders(champion) - _placeholders(candidate)
    if missing:
        return False, f"dropped placeholders: {', '.join(sorted(missing))}"
    lo, hi = 0.4 * len(champion), 3.0 * len(champion)
    if not (lo <= len(candidate) <= hi):
        return False, f"length {len(candidate)} outside sane bounds [{int(lo)},{int(hi)}]"
    if is_unsafe(candidate):
        return False, "candidate flagged unsafe"
    return True, "ok"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_guardrails.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/optimizer/guardrails.py tests/test_optimizer_guardrails.py
git commit -m "feat(optimizer): guardrails — placeholder + safety validation for candidates"
```

---

### Task 4: Reward — scalar reward from post metrics

**Files:**
- Create: `src/optimizer/reward.py`
- Test: `tests/test_optimizer_reward.py`

**Interfaces:**
- Produces:
  - `REWARD_WEIGHTS = {"saved": 3.0, "shares": 2.5, "comments": 2.0, "reach": 1.5, "likes": 1.0, "impressions": 0.0}`
  - `reward(metrics: dict) -> float` — weighted sum, missing keys treated as 0, normalized by `max(reach, 1)` so it is an engagement-rate not a raw-volume signal.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_reward.py
from src.optimizer import reward


def test_reward_weights_saves_highest():
    saves = reward.reward({"saved": 10, "reach": 100})
    likes = reward.reward({"likes": 10, "reach": 100})
    assert saves > likes


def test_reward_is_rate_not_volume():
    small = reward.reward({"saved": 5, "reach": 50})
    big = reward.reward({"saved": 50, "reach": 500})
    assert abs(small - big) < 1e-9   # same rate → same reward


def test_reward_missing_keys_zero():
    assert reward.reward({}) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_reward.py -q`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# src/optimizer/reward.py
"""Scalar reward for a post's engagement. Reuses predictive_scoring's research
weights; normalized by reach so it measures engagement *rate*, not raw volume
(a high-reach post shouldn't win just for being distributed)."""

REWARD_WEIGHTS = {
    "saved": 3.0, "shares": 2.5, "comments": 2.0,
    "reach": 1.5, "likes": 1.0, "impressions": 0.0,
}


def reward(metrics):
    if not metrics:
        return 0.0
    reach = max(float(metrics.get("reach", 0) or 0), 1.0)
    total = 0.0
    for k, w in REWARD_WEIGHTS.items():
        if k == "reach":
            continue
        total += w * float(metrics.get(k, 0) or 0)
    return total / reach
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_reward.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/optimizer/reward.py tests/test_optimizer_reward.py
git commit -m "feat(optimizer): reward — reach-normalized engagement scalar"
```

---

### Task 5: Experiments — open + evaluate champion-challenger

**Files:**
- Create: `src/optimizer/experiments.py`
- Test: `tests/test_optimizer_experiments.py`

**Interfaces:**
- Consumes: `registry` (tables), `reward.reward`
- Produces:
  - `open_experiment(key, champion_version_id, challenger_version_id, metric="reward", db_path=registry.DB_PATH) -> int`
  - `get_open_experiment(key, db_path=registry.DB_PATH) -> dict | None`
  - `evaluate(experiment_id, arm_rewards: dict, min_samples=8, margin=0.05, db_path=registry.DB_PATH) -> dict`
    where `arm_rewards = {"champion": [floats], "challenger": [floats]}`.
    Returns `{"decision": "promote"|"retire"|"insufficient", "champion_mean":…, "challenger_mean":…, "n_champ":…, "n_chal":…}` and, on a terminal decision, sets experiment `status` to `promoted`/`retired` and stamps `closed_at` + `result_json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_experiments.py
import pytest
from src.optimizer import registry, experiments


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    registry.register_asset("k", "prompt", "A", p)
    return p


def _open(db):
    champ = registry.get_champion("k", db)
    chal = registry.add_version("k", "B", "critic", "r", 0.1, db_path=db)
    return experiments.open_experiment("k", champ["id"], chal, db_path=db), champ["id"], chal


def test_open_and_get(db):
    eid, _, _ = _open(db)
    assert experiments.get_open_experiment("k", db)["id"] == eid


def test_insufficient_samples(db):
    eid, _, _ = _open(db)
    res = experiments.evaluate(eid, {"champion": [0.1], "challenger": [0.2]}, min_samples=8, db_path=db)
    assert res["decision"] == "insufficient"


def test_promote_when_challenger_wins(db):
    eid, _, chal = _open(db)
    res = experiments.evaluate(
        eid,
        {"champion": [0.10] * 8, "challenger": [0.30] * 8},
        min_samples=8, margin=0.05, db_path=db,
    )
    assert res["decision"] == "promote"
    assert experiments.get_open_experiment("k", db) is None  # closed


def test_retire_when_challenger_loses(db):
    eid, _, chal = _open(db)
    res = experiments.evaluate(
        eid,
        {"champion": [0.30] * 8, "challenger": [0.10] * 8},
        min_samples=8, margin=0.05, db_path=db,
    )
    assert res["decision"] == "retire"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_experiments.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/optimizer/experiments.py
"""Champion-challenger experiments. evaluate() is pure w.r.t. the reward lists
passed in — the caller collects per-arm rewards from post_metrics (Phase 1
tests pass them directly; the pipeline wires real attribution later)."""
import json
from datetime import datetime
from src.optimizer import registry


def _connect(db_path):
    import sqlite3
    return sqlite3.connect(str(db_path))


def open_experiment(key, champion_version_id, challenger_version_id, metric="reward",
                    db_path=registry.DB_PATH):
    con = _connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO opt_experiments (key, champion_version_id, challenger_version_id, "
            "metric, status, opened_at) VALUES (?,?,?,?, 'open', ?)",
            (key, champion_version_id, challenger_version_id, metric,
             datetime.utcnow().isoformat()),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def get_open_experiment(key, db_path=registry.DB_PATH):
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT id, key, champion_version_id, challenger_version_id, metric "
            "FROM opt_experiments WHERE key=? AND status='open' "
            "ORDER BY id DESC LIMIT 1", (key,)
        ).fetchone()
        if not r:
            return None
        return {"id": r[0], "key": r[1], "champion_version_id": r[2],
                "challenger_version_id": r[3], "metric": r[4]}
    finally:
        con.close()


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def evaluate(experiment_id, arm_rewards, min_samples=8, margin=0.05, db_path=registry.DB_PATH):
    champ = arm_rewards.get("champion", [])
    chal = arm_rewards.get("challenger", [])
    cm, hm = _mean(champ), _mean(chal)
    res = {"champion_mean": cm, "challenger_mean": hm,
           "n_champ": len(champ), "n_chal": len(chal)}
    if len(champ) < min_samples or len(chal) < min_samples:
        res["decision"] = "insufficient"
        return res
    res["decision"] = "promote" if hm >= cm * (1 + margin) else "retire"
    con = _connect(db_path)
    try:
        status = "promoted" if res["decision"] == "promote" else "retired"
        con.execute(
            "UPDATE opt_experiments SET status=?, closed_at=?, result_json=? WHERE id=?",
            (status, datetime.utcnow().isoformat(), json.dumps(res), experiment_id),
        )
        con.commit()
    finally:
        con.close()
    return res
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_experiments.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/optimizer/experiments.py tests/test_optimizer_experiments.py
git commit -m "feat(optimizer): champion-challenger experiments (open/evaluate)"
```

---

### Task 6: Prompt critic agent

**Files:**
- Create: `src/optimizer/proposers/__init__.py` (empty)
- Create: `src/optimizer/proposers/prompt_critic.py`
- Test: `tests/test_optimizer_prompt_critic.py`

**Interfaces:**
- Consumes: a `client` with `.call(role, prefix, role_system, user, schema) -> dict` (the `StudioClient` seam — mocked in tests).
- Produces:
  - `CRITIC_SCHEMA` (dict) — JSON schema requiring `candidate` (str), `rationale` (str), `predicted_delta` (number).
  - `propose(client, key: str, champion_text: str, perf_context: str) -> dict | None` — returns `{"candidate","rationale","predicted_delta"}` or `None` on failure/over-ceiling. Never raises.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_prompt_critic.py
from src.optimizer.proposers import prompt_critic


class FakeClient:
    def __init__(self, resp, over=False):
        self._resp, self._over = resp, over
        self.calls = []
    def over_daily_ceiling(self):
        return self._over
    def call(self, role, prefix, role_system, user, schema):
        self.calls.append(user)
        return self._resp


def test_propose_returns_candidate():
    c = FakeClient({"candidate": "BETTER {slot}", "rationale": "tighter", "predicted_delta": 0.12})
    out = prompt_critic.propose(c, "prompt.strategist.role", "OLD {slot}", "perf: none yet")
    assert out["candidate"] == "BETTER {slot}"
    assert out["predicted_delta"] == 0.12
    assert "OLD {slot}" in c.calls[0]          # champion text is in the prompt
    assert "perf: none yet" in c.calls[0]      # perf context is in the prompt


def test_propose_none_when_over_ceiling():
    c = FakeClient({}, over=True)
    assert prompt_critic.propose(c, "k", "OLD", "ctx") is None


def test_propose_none_on_client_error():
    class Boom:
        def over_daily_ceiling(self): return False
        def call(self, *a, **k): raise RuntimeError("api down")
    assert prompt_critic.propose(Boom(), "k", "OLD", "ctx") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_prompt_critic.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/optimizer/proposers/prompt_critic.py
"""Critic agent: rewrite an agent's system prompt to be more viral, given the
champion text + performance context. Returns a challenger candidate + rationale
+ predicted improvement. Best-effort — never raises."""
import logging

log = logging.getLogger(__name__)

_PREFIX = (
    "You are a Prompt Optimization Critic for a viral Stoic-philosophy Instagram "
    "account. You improve the SYSTEM PROMPTS that instruct the account's content "
    "agents, to drive saves/comments/shares."
)
_ROLE = (
    "Here is the CURRENT champion prompt for the agent '{key}':\n"
    "<<<\n{champion}\n>>>\n\n"
    "Performance context (what is winning/dying):\n{perf}\n\n"
    "Rewrite the prompt to more reliably produce scroll-stopping, save-worthy "
    "output. HARD RULES: keep every {{placeholder}} exactly as-is; keep it a "
    "system prompt (instructions, not content); do not add unsafe directives; "
    "stay concise. Output JSON with: candidate (the full rewritten prompt), "
    "rationale (one sentence on what you changed and why), predicted_delta "
    "(your estimate of fractional engagement-rate improvement, e.g. 0.1 = +10%)."
)

CRITIC_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate": {"type": "string"},
        "rationale": {"type": "string"},
        "predicted_delta": {"type": "number"},
    },
    "required": ["candidate", "rationale", "predicted_delta"],
}


def propose(client, key, champion_text, perf_context):
    try:
        if client.over_daily_ceiling():
            log.info("[optimizer] critic skipped — over daily ceiling")
            return None
        role = _ROLE.format(key=key, champion=champion_text, perf=perf_context)
        d = client.call("prompt_critic", _PREFIX, role,
                        "Rewrite the prompt now.", CRITIC_SCHEMA)
        if not d or "candidate" not in d:
            return None
        return {
            "candidate": d["candidate"],
            "rationale": d.get("rationale", ""),
            "predicted_delta": float(d.get("predicted_delta", 0.0) or 0.0),
        }
    except Exception as e:
        log.warning(f"[optimizer] critic.propose failed ({e})")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_prompt_critic.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/optimizer/proposers/__init__.py src/optimizer/proposers/prompt_critic.py tests/test_optimizer_prompt_critic.py
git commit -m "feat(optimizer): prompt_critic agent — proposes prompt rewrites"
```

---

### Task 7: Register studio prompts as assets + wire strategist to prompt_store

**Files:**
- Create: `src/optimizer/assets.py` (declares the managed prompt assets)
- Modify: `studio/strategist.py` (load `_ROLE` via `prompt_store.get`)
- Test: `tests/test_optimizer_assets.py`

**Interfaces:**
- Consumes: `prompt_store.get`, the existing `studio.strategist._ROLE` / `._PREFIX` constants (renamed to `_ROLE_DEFAULT` / `_PREFIX_DEFAULT`).
- Produces:
  - `MANAGED_PROMPTS: list[dict]` — each `{"key","default_ref"}` describing a managed prompt (Phase 1: strategist role+prefix, copywriter draft+revise, trend_scout role).
  - `iter_managed(db_path=…) -> list[dict]` — returns `[{"key","champion_text"}]`, seeding defaults on first call.

**Note:** This task wires **strategist** as the proof-of-path; copywriter/trend_scout keys are declared in `MANAGED_PROMPTS` and picked up by the loop (Task 8) without further wiring, because the loop reads champion text from the registry, not from the agent module. Full runtime wiring of the other two agents is a fast-follow within Phase 1 and mirrors the strategist edit exactly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_assets.py
from src.optimizer import assets, registry, prompt_store
import studio.strategist as strat


def test_managed_prompts_include_strategist():
    keys = {m["key"] for m in assets.MANAGED_PROMPTS}
    assert "prompt.strategist.role" in keys


def test_iter_managed_seeds_and_returns_text(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    got = assets.iter_managed(db)
    keys = {g["key"] for g in got}
    assert "prompt.strategist.role" in keys
    for g in got:
        assert isinstance(g["champion_text"], str) and g["champion_text"]


def test_strategist_role_uses_prompt_store(tmp_path, monkeypatch):
    # When a champion is promoted, the strategist's built role reflects it.
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    monkeypatch.setattr(strat.prompt_store, "DB_PATH", db, raising=False)
    monkeypatch.setattr(registry, "DB_PATH", db, raising=False)
    prompt_store.get("prompt.strategist.role", strat._ROLE_DEFAULT, db)  # seed
    cid = registry.add_version("prompt.strategist.role",
                               "NEW ROLE slot={slot} recent={recent} pool={pool}",
                               "critic", "r", 0.1, db_path=db)
    registry.promote(cid, db)
    role = strat.build_role(slot=1, recent="x", pool="y", db_path=db)
    assert "NEW ROLE" in role
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_assets.py -q`
Expected: FAIL (`ModuleNotFoundError` / `AttributeError: build_role`).

- [ ] **Step 3: Write minimal implementation**

First, `src/optimizer/assets.py`:

```python
# src/optimizer/assets.py
"""Declares which prompts the optimizer manages, and exposes their current
champion text (seeding the hardcoded default as v1 on first access)."""
from src.optimizer import prompt_store, registry
import studio.strategist as strategist
import studio.copywriter as copywriter
import studio.trend_scout as trend_scout

MANAGED_PROMPTS = [
    {"key": "prompt.strategist.role", "default": strategist._ROLE_DEFAULT},
    {"key": "prompt.strategist.prefix", "default": strategist._PREFIX_DEFAULT},
    {"key": "prompt.copywriter.draft", "default": copywriter._DRAFT_ROLE},
    {"key": "prompt.copywriter.revise", "default": copywriter._REVISE_ROLE},
    {"key": "prompt.trend_scout.role", "default": trend_scout._ROLE},
]


def iter_managed(db_path=registry.DB_PATH):
    out = []
    for m in MANAGED_PROMPTS:
        text = prompt_store.get(m["key"], m["default"], db_path)
        out.append({"key": m["key"], "champion_text": text})
    return out
```

Then edit `studio/strategist.py` — rename the constants and add a `build_role` that loads from the store. Current code:

```python
_PREFIX = ( ... )
_ROLE = ( ... )

def shared_prefix(perf):
    return _PREFIX.format(perf=json.dumps(perf.to_dict(), indent=2))
```

becomes:

```python
from src.optimizer import prompt_store

_PREFIX_DEFAULT = ( ... )   # unchanged text, renamed
_ROLE_DEFAULT = ( ... )     # unchanged text, renamed

def shared_prefix(perf, db_path=prompt_store.registry.DB_PATH):
    prefix = prompt_store.get("prompt.strategist.prefix", _PREFIX_DEFAULT, db_path)
    return prefix.format(perf=json.dumps(perf.to_dict(), indent=2))

def build_role(slot, recent, pool, db_path=prompt_store.registry.DB_PATH):
    role = prompt_store.get("prompt.strategist.role", _ROLE_DEFAULT, db_path)
    return role.format(slot=slot, recent=recent, pool=pool)
```

Update the existing caller in `studio/strategist.py` that formats `_ROLE` (the `pick(...)` function) to call `build_role(...)` instead. Keep the module-level names `_PREFIX`/`_ROLE` as aliases if other modules import them: add `_PREFIX = _PREFIX_DEFAULT` and `_ROLE = _ROLE_DEFAULT` at the bottom for backward-compat.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_assets.py tests/test_studio_strategist.py -q`
Expected: PASS (new tests pass; any existing strategist tests still pass).

- [ ] **Step 5: Commit**

```bash
git add src/optimizer/assets.py studio/strategist.py tests/test_optimizer_assets.py
git commit -m "feat(optimizer): register managed prompts; strategist loads via prompt_store"
```

---

### Task 8: The loop — propose challengers + record proposals

**Files:**
- Create: `src/optimizer/loop.py`
- Test: `tests/test_optimizer_loop.py`

**Interfaces:**
- Consumes: `assets.iter_managed`, `experiments.get_open_experiment`, `prompt_critic.propose`, `guardrails.validate_prompt_candidate`, `registry.add_version`, `experiments.open_experiment`.
- Produces:
  - `run_once(client, perf_context: str, db_path=registry.DB_PATH, propose_fn=prompt_critic.propose) -> list[dict]`
    For each managed prompt with **no** open experiment: call `propose_fn`; if a candidate passes guardrails and `predicted_delta > 0`, `add_version(status="challenger")` + `open_experiment(...)`, and append a proposal dict `{"key","challenger_version_id","rationale","predicted_delta","candidate"}`. Skips assets that already have an open experiment. Never raises (per-asset try/except).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_loop.py
import pytest
from src.optimizer import loop, registry, experiments, assets


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    return p


def _good_propose(client, key, champ, perf):
    # returns a valid rewrite preserving placeholders
    return {"candidate": champ + " (sharper)", "rationale": "tighter", "predicted_delta": 0.2}


def test_run_once_creates_proposals(db):
    props = loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=_good_propose)
    assert len(props) == len(assets.MANAGED_PROMPTS)
    keys = {p["key"] for p in props}
    assert "prompt.strategist.role" in keys
    # each created an open experiment
    assert experiments.get_open_experiment("prompt.strategist.role", db) is not None


def test_run_once_skips_open_experiments(db):
    loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=_good_propose)
    props2 = loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=_good_propose)
    assert props2 == []   # all have open experiments now


def test_run_once_drops_guardrail_failures(db):
    def bad(client, key, champ, perf):
        return {"candidate": "no placeholders here", "rationale": "x", "predicted_delta": 0.5}
    props = loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=bad)
    # strategist prompts have placeholders → candidate dropping them fails guardrails
    assert all(p["key"] not in ("prompt.strategist.role", "prompt.strategist.prefix") for p in props)


def test_run_once_never_raises_on_propose_error(db):
    def boom(*a, **k): raise RuntimeError("x")
    assert loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=boom) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_loop.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/optimizer/loop.py
"""Nightly self-improvement loop (Phase 1: prompts).

For each managed prompt with no open experiment, ask the critic for a rewrite,
guardrail it, and (if it passes) record a challenger version + open an experiment
+ emit a proposal. Surfacing proposals to Telegram + applying approvals lives in
optimize.py (the CLI). Every asset is handled in isolation; one failure never
aborts the rest."""
import logging
from src.optimizer import registry, experiments, guardrails, assets
from src.optimizer.proposers import prompt_critic

log = logging.getLogger(__name__)


def run_once(client, perf_context, db_path=registry.DB_PATH, propose_fn=prompt_critic.propose):
    proposals = []
    for m in assets.iter_managed(db_path):
        key, champ = m["key"], m["champion_text"]
        try:
            if experiments.get_open_experiment(key, db_path):
                continue
            cand = propose_fn(client, key, champ, perf_context)
            if not cand:
                continue
            if float(cand.get("predicted_delta", 0) or 0) <= 0:
                continue
            ok, reason = guardrails.validate_prompt_candidate(champ, cand["candidate"])
            if not ok:
                log.info(f"[optimizer] {key}: candidate rejected ({reason})")
                continue
            champ_v = registry.get_champion(key, db_path)
            cid = registry.add_version(
                key, cand["candidate"], source="critic",
                rationale=cand.get("rationale", ""),
                predicted_delta=cand["predicted_delta"], status="challenger", db_path=db_path,
            )
            experiments.open_experiment(key, champ_v["id"], cid, db_path=db_path)
            proposals.append({
                "key": key, "challenger_version_id": cid,
                "rationale": cand.get("rationale", ""),
                "predicted_delta": cand["predicted_delta"],
                "candidate": cand["candidate"],
            })
        except Exception as e:
            log.warning(f"[optimizer] loop failed for {key} ({e})")
            continue
    return proposals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_loop.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/optimizer/loop.py tests/test_optimizer_loop.py
git commit -m "feat(optimizer): nightly loop — propose+guardrail+record challengers"
```

---

### Task 9: CLI + Telegram surfacing

**Files:**
- Create: `optimize.py` (repo root)
- Modify: `src/optimizer/loop.py` (add `format_proposal_message`)
- Test: `tests/test_optimize_cli.py`

**Interfaces:**
- Consumes: `loop.run_once`, `config.Config`, `studio.client.StudioClient`, `src.core.notifier.Notifier` (or its `send_message` seam), `src.core.data_store.save_proposal`.
- Produces:
  - `loop.format_proposal_message(proposal: dict) -> str` — a Telegram-ready summary (key, rationale, predicted delta, truncated candidate).
  - `optimize.main(argv=None, *, client=None, notify=None, db_path=…)` supporting `--run` (run loop, surface proposals), `--status` (print open experiments + champions), `--dry-run` (run loop, print proposals, send nothing).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimize_cli.py
from src.optimizer import loop, registry
import optimize


def test_format_proposal_message_has_key_and_delta():
    msg = loop.format_proposal_message({
        "key": "prompt.strategist.role", "rationale": "tighter hooks",
        "predicted_delta": 0.15, "candidate": "X" * 500,
    })
    assert "prompt.strategist.role" in msg
    assert "15" in msg              # 0.15 → +15%
    assert "tighter hooks" in msg
    assert len(msg) < 1200          # candidate truncated


def test_dry_run_sends_nothing(tmp_path, capsys):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    sent = []
    def _good(client, key, champ, perf):
        return {"candidate": champ + " x", "rationale": "r", "predicted_delta": 0.2}
    rc = optimize.main(
        ["--dry-run"], client=None, notify=lambda m: sent.append(m),
        db_path=db, propose_fn=_good,
    )
    assert rc == 0
    assert sent == []               # dry-run never notifies
    assert "prompt." in capsys.readouterr().out


def test_run_notifies_each_proposal(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    sent = []
    def _good(client, key, champ, perf):
        return {"candidate": champ + " x", "rationale": "r", "predicted_delta": 0.2}
    rc = optimize.main(
        ["--run"], client=None, notify=lambda m: sent.append(m),
        db_path=db, propose_fn=_good,
    )
    assert rc == 0
    assert len(sent) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimize_cli.py -q`
Expected: FAIL (`ModuleNotFoundError: optimize`).

- [ ] **Step 3: Write minimal implementation**

Add to `src/optimizer/loop.py`:

```python
def format_proposal_message(proposal):
    pct = round(float(proposal.get("predicted_delta", 0)) * 100)
    cand = proposal.get("candidate", "")
    if len(cand) > 800:
        cand = cand[:800] + "…"
    return (
        f"🧠 Prompt improvement proposed\n"
        f"Asset: {proposal['key']}\n"
        f"Predicted: +{pct}% engagement\n"
        f"Why: {proposal.get('rationale','')}\n\n"
        f"New prompt:\n{cand}\n\n"
        f"Challenger v#{proposal.get('challenger_version_id')} — approve to make champion."
    )
```

Create `optimize.py`:

```python
#!/usr/bin/env python
"""Self-improvement loop CLI.

  optimize.py --run       run the loop; surface proposals to Telegram
  optimize.py --dry-run   run the loop; print proposals; notify nothing
  optimize.py --status    print champions + open experiments
"""
import argparse
import sys
from src.optimizer import loop, registry, experiments, assets
from src.optimizer.proposers import prompt_critic


def _default_notify(msg):
    from config import Config
    from src.core.notifier import Notifier
    Notifier(Config()).send_message(msg)


def _default_client():
    from config import Config
    from studio.client import StudioClient
    return StudioClient(Config().ANTHROPIC_API_KEY)


def _perf_context(db_path):
    """Best-effort performance context for the critic (empty string at cold start)."""
    try:
        from pathlib import Path
        import json
        p = Path(__file__).parent / "data" / "perf_brief.json"
        return json.dumps(json.loads(p.read_text())) if p.exists() else "No performance data yet."
    except Exception:
        return "No performance data yet."


def main(argv=None, *, client=None, notify=None, db_path=registry.DB_PATH,
         propose_fn=prompt_critic.propose):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    if args.status:
        for a in assets.iter_managed(db_path):
            exp = experiments.get_open_experiment(a["key"], db_path)
            print(f"{a['key']}: champion set; open_experiment={'yes' if exp else 'no'}")
        return 0

    if args.run or args.dry_run:
        if client is None and args.run:
            client = _default_client()
        proposals = loop.run_once(client, _perf_context(db_path), db_path=db_path,
                                  propose_fn=propose_fn)
        for p in proposals:
            msg = loop.format_proposal_message(p)
            print(msg)
            if args.run:
                (notify or _default_notify)(msg)
        print(f"\n{len(proposals)} proposal(s).")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Note:** if `src/core/notifier.Notifier` has no `send_message` method, add a thin one that posts a Telegram text message via the existing bot token (mirror `notifier.py`'s existing send path). Confirm the method name during implementation and adjust `_default_notify`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimize_cli.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add optimize.py src/optimizer/loop.py tests/test_optimize_cli.py
git commit -m "feat(optimizer): optimize.py CLI + Telegram proposal surfacing"
```

---

### Task 10: Apply approvals + full-suite + cold-start smoke

**Files:**
- Modify: `optimize.py` (add `--apply-decisions`)
- Modify: `src/optimizer/loop.py` (add `apply_decision(key_or_version, approved, db_path)`)
- Test: `tests/test_optimizer_apply.py`

**Interfaces:**
- Consumes: `registry.promote`, `experiments` tables, `src.core.approval.poll_once` (Telegram approve/reject callbacks).
- Produces:
  - `loop.apply_decision(challenger_version_id: int, approved: bool, db_path=…) -> str` — on approve: `registry.promote(challenger_version_id)` + mark its experiment `promoted`; on reject: set version `rejected` + experiment `retired`. Returns `"promoted"|"rejected"|"noop"`.
  - `optimize.py --apply-decisions` polls Telegram once and applies each decision.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_optimizer_apply.py
from src.optimizer import registry, experiments, loop


def _setup(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    registry.register_asset("k", "prompt", "A {x}", db)
    champ = registry.get_champion("k", db)
    cid = registry.add_version("k", "B {x}", "critic", "r", 0.2, db_path=db)
    experiments.open_experiment("k", champ["id"], cid, db_path=db)
    return db, cid


def test_apply_approve_promotes(tmp_path):
    db, cid = _setup(tmp_path)
    assert loop.apply_decision(cid, True, db) == "promoted"
    assert registry.get_champion("k", db)["value"] == "B {x}"
    assert experiments.get_open_experiment("k", db) is None


def test_apply_reject_retires(tmp_path):
    db, cid = _setup(tmp_path)
    assert loop.apply_decision(cid, False, db) == "rejected"
    assert registry.get_champion("k", db)["value"] == "A {x}"   # unchanged
    assert experiments.get_open_experiment("k", db) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_optimizer_apply.py -q`
Expected: FAIL (`AttributeError: apply_decision`).

- [ ] **Step 3: Write minimal implementation**

Add to `src/optimizer/loop.py`:

```python
def apply_decision(challenger_version_id, approved, db_path=registry.DB_PATH):
    import sqlite3
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute("SELECT key FROM opt_versions WHERE id=?",
                          (challenger_version_id,)).fetchone()
        if not row:
            return "noop"
        key = row[0]
        exp = con.execute(
            "SELECT id FROM opt_experiments WHERE challenger_version_id=? AND status='open'",
            (challenger_version_id,)).fetchone()
    finally:
        con.close()
    if approved:
        registry.promote(challenger_version_id, db_path)
        if exp:
            con = sqlite3.connect(str(db_path))
            try:
                con.execute("UPDATE opt_experiments SET status='promoted' WHERE id=?", (exp[0],))
                con.commit()
            finally:
                con.close()
        return "promoted"
    else:
        con = sqlite3.connect(str(db_path))
        try:
            con.execute("UPDATE opt_versions SET status='rejected' WHERE id=?",
                       (challenger_version_id,))
            if exp:
                con.execute("UPDATE opt_experiments SET status='retired' WHERE id=?", (exp[0],))
            con.commit()
        finally:
            con.close()
        return "rejected"
```

Add `--apply-decisions` to `optimize.py`'s parser: poll Telegram via `approval.poll_once(Config())`, map each `{"post_row_id": challenger_version_id, "status"}` to `apply_decision(...)`, print the result. (The approval callback ids are challenger version ids for optimizer proposals — send them as `approve_<vid>`/`reject_<vid>` when surfacing in Task 9's notify path; adjust the surfacing to include the inline keyboard using `approval.approve_reject_buttons(vid)`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_optimizer_apply.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run full suite + cold-start smoke**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (existing 482 + new optimizer tests).

Cold-start smoke (mocked critic, temp DB — proves success criterion #1):

```bash
.venv/bin/python -c "
from pathlib import Path
from src.optimizer import loop, registry
db = Path('/tmp/opt_smoke.db')
if db.exists(): db.unlink()
registry.init_optimizer_db(db)
def fake(c,k,champ,perf): return {'candidate':champ+' (sharper)','rationale':'tighter','predicted_delta':0.15}
props = loop.run_once(None, 'no data yet', db_path=db, propose_fn=fake)
print(f'{len(props)} proposals; keys=', [p[\"key\"] for p in props])
assert props, 'expected cold-start proposals'
print('COLD-START OK:', loop.format_proposal_message(props[0])[:80])
"
```
Expected: prints ≥1 proposal and `COLD-START OK: …`.

- [ ] **Step 6: Commit**

```bash
git checkout -- data/pipeline.db 2>/dev/null || true
git add optimize.py src/optimizer/loop.py tests/test_optimizer_apply.py
git commit -m "feat(optimizer): apply Telegram approve/reject decisions; full-suite green"
```

---

## Future phases (not this plan)

- **Phase 2 — Selection policy:** `src/optimizer/proposers/policy_bandit.py` (Thompson sampling over mood/slot/hook/format on `ab_results`); register `policy.*` assets.
- **Phase 3 — Scoring weights:** `weight_fit.py` refit of `predictive_scoring` weights from `post_metrics` (shadow mode → propose).
- **Phase 4 — Music/visual direction:** register `prompt.music_director.*` and `prompt.architect.*` as prompt assets — no new mechanic.
- **Pipeline attribution wiring:** when experiments have real IG traffic, `data_store.log_post` records `opt_versions_json`; the pipeline picks champion vs challenger 50/50 per open experiment; a nightly job collects per-arm rewards and calls `experiments.evaluate`.
