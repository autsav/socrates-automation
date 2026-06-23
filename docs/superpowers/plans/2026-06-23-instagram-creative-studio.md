# AI Creative Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `studio/` package of four reasoning agents (Analyst, Strategist, Copywriter, Creative Director) that produce a scroll-stopping post concept + visual direction, proposed to the user via Telegram for manual publishing, with hard fallback to the existing templated pipeline.

**Architecture:** Plain-Python package between the scheduler and the existing renderer. Each agent = a pure `build_prompt()` + `parse_response()` pair plus a thin call through a shared `StudioClient` (official `anthropic` SDK, structured outputs, prompt caching, adaptive thinking). The orchestrator chains them; any failure returns `None` and `pipeline.py` falls back to the legacy path. Quotes stay sourced from `quotes.xlsx`.

**Tech Stack:** Python 3.11, `anthropic` SDK, SQLite (existing `data_store.py`), pytest, existing Pillow/ffmpeg renderer + Meta Graph API.

## Global Constraints

- Model IDs (exact, verbatim): Opus = `claude-opus-4-8`, Sonnet = `claude-sonnet-4-6`. Never append date suffixes.
- Thinking: adaptive only — `thinking={"type": "adaptive"}`. Never `budget_tokens`, `temperature`, `top_p`, `top_k` (all 400 on these models).
- Structured outputs via `output_config={"format": {"type": "json_schema", "schema": ...}}`. Do not use the deprecated `output_format`.
- Always check `response.stop_reason == "refusal"` before reading `response.content`.
- `audience ∈ {procrastinator, doomscroller, stuck, lazy, quitter, lost, overwhelmed}`; `mood ∈ VALID_MOODS = {dark_philosophical, dramatic_ancient, cinematic_hopeful, stark_minimal, epic_warrior, mystical_greek, calm_stoic}` — import both from `excel_reader`, never re-hardcode.
- Posting must NEVER be blocked by a studio failure. Every studio entry point returns `None`/raises `StudioError` cleanly so the legacy path runs.
- Run tests with `python -m pytest`. Commit after each task.
- Reuse existing modules; do not modify `image_composer.py`, `reel_composer.py`, `instagram_poster.py`, `analytics.py`.

---

### Task 1: Package scaffold, settings, and dataclass types

**Files:**
- Create: `studio/__init__.py`
- Create: `studio/settings.py`
- Create: `studio/types.py`
- Modify: `requirements.txt` (append `anthropic`)
- Test: `tests/test_studio_types.py`

**Interfaces:**
- Consumes: `excel_reader.VALID_MOODS`, `excel_reader.AUDIENCE_TO_MOOD`.
- Produces:
  - `studio.settings`: `ROLE_MODELS: dict[str,str]`, `ROLE_EFFORT: dict[str,str]`, `N_CONCEPTS: int`, `DAILY_SPEND_CEILING_USD: float`, `PERF_BRIEF_PATH: Path`, `PERF_BRIEF_TTL_HOURS: int`, `SPEND_LOG_PATH: Path`, `AUDIENCES: list[str]`.
  - `studio.types`: dataclasses `PerformanceBrief`, `CreativeBrief`, `Concept`, `Decision`, each with `.to_dict()` and classmethod `.from_dict(d)`; schema dicts `PERFORMANCE_BRIEF_SCHEMA`, `CREATIVE_BRIEF_SCHEMA`, `CONCEPTS_SCHEMA`, `DECISION_SCHEMA`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio_types.py
from studio.types import (
    Concept, Decision, CreativeBrief, PerformanceBrief,
    DECISION_SCHEMA,
)
from studio.settings import ROLE_MODELS, AUDIENCES
from excel_reader import VALID_MOODS


def test_concept_roundtrip():
    c = Concept(id="c1", angle_label="confront", hook="You already know.",
                caption="long caption", cta="Save this.",
                reel_scenes=["s1", "s2"], hashtags=["#Stoicism"])
    assert Concept.from_dict(c.to_dict()) == c


def test_decision_roundtrip_and_mood_field():
    d = Decision(
        scores=[{"concept_id": "c1", "score": 8, "critique": "strong"}],
        top_pick="c1", alt_pick=None,
        revision={"requested": False, "concept_id": "", "feedback": ""},
        visual_direction={"mood": "epic_warrior", "flux_prompt": "x",
                          "typography": "bold", "palette": "amber"},
        rationale="why")
    d2 = Decision.from_dict(d.to_dict())
    assert d2 == d
    assert d2.visual_direction["mood"] in VALID_MOODS


def test_models_are_exact_ids():
    assert ROLE_MODELS["copywriter"] == "claude-opus-4-8"
    assert ROLE_MODELS["strategist"] == "claude-sonnet-4-6"


def test_audiences_match_renderer():
    assert set(AUDIENCES) == {"procrastinator", "doomscroller", "stuck",
                              "lazy", "quitter", "lost", "overwhelmed"}


def test_decision_schema_is_strict_object():
    assert DECISION_SCHEMA["type"] == "object"
    assert DECISION_SCHEMA["additionalProperties"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio'`.

- [ ] **Step 3: Create the package scaffold and settings**

```python
# studio/__init__.py
"""AI Creative Studio — reasoning-agent layer over the Socrates pipeline."""
```

```python
# studio/settings.py
"""Studio configuration constants (non-secret). Models/effort/budget dials."""
from pathlib import Path
from excel_reader import AUDIENCE_TO_MOOD

AUDIENCES = list(AUDIENCE_TO_MOOD.keys())

ROLE_MODELS = {
    "analyst":    "claude-sonnet-4-6",
    "strategist": "claude-sonnet-4-6",
    "copywriter": "claude-opus-4-8",
    "director":   "claude-opus-4-8",
}
ROLE_EFFORT = {
    "analyst":    "medium",
    "strategist": "medium",
    "copywriter": "high",
    "director":   "high",
}
N_CONCEPTS = 4
DAILY_SPEND_CEILING_USD = 2.0

_DATA = Path(__file__).resolve().parent.parent / "data"
PERF_BRIEF_PATH = _DATA / "perf_brief.json"
PERF_BRIEF_TTL_HOURS = 24
SPEND_LOG_PATH = _DATA / "studio_spend.json"
```

- [ ] **Step 4: Create the dataclasses and schemas**

```python
# studio/types.py
"""Dataclasses passed between studio agents + JSON schemas for structured output."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field

from excel_reader import VALID_MOODS  # noqa: F401  (re-exported for callers)


@dataclass
class PerformanceBrief:
    generated_at: str
    sample_size: int
    window_days: int
    top_hooks: list = field(default_factory=list)
    top_topics: list = field(default_factory=list)
    top_moods: list = field(default_factory=list)
    best_formats: dict = field(default_factory=dict)
    best_slots: dict = field(default_factory=dict)
    dying: list = field(default_factory=list)
    headline: str = ""

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, d): return cls(**d)


@dataclass
class CreativeBrief:
    audience: str
    topic_theme: str
    quote: dict
    format: str
    angle: str
    must_include: list
    must_avoid: list
    slot: int
    hypothesis: str

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, d): return cls(**d)


@dataclass
class Concept:
    id: str
    angle_label: str
    hook: str
    caption: str
    cta: str
    reel_scenes: list
    hashtags: list

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, d): return cls(**d)


@dataclass
class Decision:
    scores: list
    top_pick: str
    alt_pick: str | None
    revision: dict
    visual_direction: dict
    rationale: str

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, d): return cls(**d)


def _obj(props, required):
    return {"type": "object", "additionalProperties": False,
            "properties": props, "required": required}

PERFORMANCE_BRIEF_SCHEMA = _obj({
    "generated_at": {"type": "string"},
    "sample_size": {"type": "integer"},
    "window_days": {"type": "integer"},
    "top_hooks": {"type": "array", "items": {"type": "object"}},
    "top_topics": {"type": "array", "items": {"type": "object"}},
    "top_moods": {"type": "array", "items": {"type": "object"}},
    "best_formats": {"type": "object"},
    "best_slots": {"type": "object"},
    "dying": {"type": "array", "items": {"type": "object"}},
    "headline": {"type": "string"},
}, ["generated_at", "sample_size", "window_days", "headline"])

CREATIVE_BRIEF_SCHEMA = _obj({
    "audience": {"type": "string", "enum": list(__import__("studio.settings", fromlist=["AUDIENCES"]).AUDIENCES)},
    "topic_theme": {"type": "string"},
    "quote": {"type": "object"},
    "format": {"type": "string", "enum": ["reel", "carousel", "image"]},
    "angle": {"type": "string"},
    "must_include": {"type": "array", "items": {"type": "string"}},
    "must_avoid": {"type": "array", "items": {"type": "string"}},
    "slot": {"type": "integer"},
    "hypothesis": {"type": "string"},
}, ["audience", "topic_theme", "quote", "format", "angle", "slot", "hypothesis"])

_CONCEPT_SCHEMA = _obj({
    "id": {"type": "string"},
    "angle_label": {"type": "string"},
    "hook": {"type": "string"},
    "caption": {"type": "string"},
    "cta": {"type": "string"},
    "reel_scenes": {"type": "array", "items": {"type": "string"}},
    "hashtags": {"type": "array", "items": {"type": "string"}},
}, ["id", "angle_label", "hook", "caption", "cta", "reel_scenes", "hashtags"])

CONCEPTS_SCHEMA = _obj(
    {"concepts": {"type": "array", "items": _CONCEPT_SCHEMA}}, ["concepts"])

DECISION_SCHEMA = _obj({
    "scores": {"type": "array", "items": {"type": "object"}},
    "top_pick": {"type": "string"},
    "alt_pick": {"type": ["string", "null"]},
    "revision": {"type": "object"},
    "visual_direction": _obj({
        "mood": {"type": "string", "enum": list(VALID_MOODS)},
        "flux_prompt": {"type": "string"},
        "typography": {"type": "string"},
        "palette": {"type": "string"},
    }, ["mood", "flux_prompt", "typography", "palette"]),
    "rationale": {"type": "string"},
}, ["scores", "top_pick", "revision", "visual_direction", "rationale"])
```

- [ ] **Step 5: Append the dependency**

Append `anthropic` to `requirements.txt` (one line at end), then `pip install anthropic`.

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_studio_types.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add studio/__init__.py studio/settings.py studio/types.py requirements.txt tests/test_studio_types.py
git commit -m "feat(studio): package scaffold, settings, dataclass types + schemas"
```

---

### Task 2: `proposals` table + data_store helpers + analyst aggregate query

**Files:**
- Modify: `data_store.py` (add table to `init_db`, add functions at end)
- Test: `tests/test_data_store_proposals.py`

**Interfaces:**
- Consumes: existing `data_store._get_connection`, `init_db`.
- Produces:
  - `save_proposal(slot:int, quote_row:int|None, audience:str, fmt:str, decision_json:str) -> int`
  - `proposed_today(slot:int) -> bool`
  - `mark_proposal_posted(proposal_id:int, post_id:str) -> None`
  - `get_pending_proposals() -> list[dict]` (status='proposed' with post_id NULL)
  - `aggregate_performance(window_days:int=90) -> dict` (compact stats for the Analyst)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_data_store_proposals.py
import importlib, sqlite3, tempfile, os
from datetime import datetime, timedelta
import data_store


def _fresh_db(tmp_path):
    db = tmp_path / "pipeline.db"
    data_store.DB_PATH = db
    data_store.init_db()
    return db


def test_save_and_proposed_today(tmp_path):
    _fresh_db(tmp_path)
    pid = data_store.save_proposal(0, 12, "stuck", "reel", '{"top_pick":"c1"}')
    assert isinstance(pid, int)
    assert data_store.proposed_today(0) is True
    assert data_store.proposed_today(1) is False


def test_mark_posted_and_pending(tmp_path):
    _fresh_db(tmp_path)
    pid = data_store.save_proposal(1, 5, "lazy", "image", "{}")
    assert len(data_store.get_pending_proposals()) == 1
    data_store.mark_proposal_posted(pid, "IG_123")
    assert data_store.get_pending_proposals() == []


def test_aggregate_performance_shape(tmp_path):
    _fresh_db(tmp_path)
    conn = data_store._get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO posts (quote_text,audience,mood,posting_slot,posted_at,post_id) "
                "VALUES ('q','stuck','epic_warrior',0,datetime('now'),'p1')")
    cur.execute("INSERT INTO post_metrics (post_id,likes,reach,saved) VALUES ('p1',10,100,5)")
    conn.commit(); conn.close()
    stats = data_store.aggregate_performance(window_days=90)
    assert stats["sample_size"] >= 1
    assert "by_mood" in stats and "by_slot" in stats
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data_store_proposals.py -v`
Expected: FAIL — `AttributeError: module 'data_store' has no attribute 'save_proposal'`.

- [ ] **Step 3: Add the table to `init_db`**

In `data_store.py` `init_db()`, after the `token_state` table block (before `conn.commit()`), add:

```python
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                slot INTEGER NOT NULL,
                quote_row INTEGER,
                audience TEXT,
                format TEXT,
                decision_json TEXT NOT NULL,
                status TEXT DEFAULT 'proposed',
                post_id TEXT
            )
        """)
```

- [ ] **Step 4: Add the helper functions at the end of `data_store.py`**

```python
def save_proposal(slot, quote_row, audience, fmt, decision_json):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO proposals (slot, quote_row, audience, format, decision_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (slot, quote_row, audience, fmt, decision_json),
        )
        rid = cur.lastrowid
        conn.commit()
        return rid
    finally:
        conn.close()


def proposed_today(slot):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM proposals WHERE created_at >= date('now') AND slot = ? LIMIT 1",
            (slot,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def mark_proposal_posted(proposal_id, post_id):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE proposals SET status='posted', post_id=? WHERE id=?",
            (post_id, proposal_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_proposals():
    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM proposals WHERE status='proposed' AND post_id IS NULL")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def aggregate_performance(window_days=90):
    """Compact per-dimension performance stats for the Analyst (no raw rows)."""
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.mood, p.audience, p.posting_slot,
                   COALESCE(m.likes,0) likes, COALESCE(m.reach,0) reach,
                   COALESCE(m.saved,0) saved, COALESCE(m.comments,0) comments
            FROM posts p LEFT JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.post_id IS NOT NULL AND p.posted_at >= ?
            """,
            (cutoff,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    def _avg(items, key):
        vals = [r[key] for r in items]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    def _group(field):
        out = {}
        keys = {r[field] for r in rows}
        for k in keys:
            sub = [r for r in rows if r[field] == k]
            out[str(k)] = {"n": len(sub), "avg_reach": _avg(sub, "reach"),
                           "avg_saved": _avg(sub, "saved")}
        return out

    return {
        "sample_size": len(rows),
        "window_days": window_days,
        "overall_avg_reach": _avg(rows, "reach"),
        "overall_avg_saved": _avg(rows, "saved"),
        "by_mood": _group("mood"),
        "by_audience": _group("audience"),
        "by_slot": _group("posting_slot"),
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_data_store_proposals.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add data_store.py tests/test_data_store_proposals.py
git commit -m "feat(studio): proposals table + data_store helpers + perf aggregate"
```

---

### Task 3: `StudioClient` — SDK wrapper with caching, refusal handling, spend log

**Files:**
- Create: `studio/client.py`
- Test: `tests/test_studio_client.py`

**Interfaces:**
- Consumes: `studio.settings.ROLE_MODELS/ROLE_EFFORT/SPEND_LOG_PATH/DAILY_SPEND_CEILING_USD`.
- Produces:
  - `class StudioError(Exception)`
  - `class StudioClient(api_key:str, *, sdk=None)` with:
    - `call(role:str, shared_prefix:str, role_system:str, user_content:str, schema:dict) -> dict`
    - `over_daily_ceiling() -> bool`
  - The `sdk` kwarg injects a fake client for tests (defaults to `anthropic.Anthropic`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio_client.py
import json, types, pytest
from studio.client import StudioClient, StudioError


class _Block:
    def __init__(self, text): self.type = "text"; self.text = text

class _Usage:
    input_tokens = 1000; output_tokens = 500
    cache_read_input_tokens = 0; cache_creation_input_tokens = 0

class _Resp:
    def __init__(self, text, stop="end_turn"):
        self.content = [_Block(text)]; self.stop_reason = stop; self.usage = _Usage()

class _FakeMessages:
    def __init__(self, resp): self._resp = resp; self.kwargs = None
    def create(self, **kwargs): self.kwargs = kwargs; return self._resp

class _FakeSDK:
    def __init__(self, resp): self.messages = _FakeMessages(resp)


def _client(resp, tmp_path):
    c = StudioClient("key", sdk=_FakeSDK(resp))
    from studio import settings
    settings.SPEND_LOG_PATH = tmp_path / "spend.json"
    return c


def test_call_parses_json(tmp_path):
    c = _client(_Resp('{"top_pick": "c1"}'), tmp_path)
    out = c.call("director", "PREFIX", "ROLE", "USER", {"type": "object"})
    assert out == {"top_pick": "c1"}


def test_call_uses_correct_model_and_caches_prefix(tmp_path):
    fake = _FakeSDK(_Resp('{}'))
    c = StudioClient("key", sdk=fake)
    c.call("copywriter", "PREFIX", "ROLE", "USER", {"type": "object"})
    kw = fake.messages.kwargs
    assert kw["model"] == "claude-opus-4-8"
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "budget_tokens" not in json.dumps(kw)


def test_refusal_raises(tmp_path):
    c = _client(_Resp("", stop="refusal"), tmp_path)
    with pytest.raises(StudioError):
        c.call("director", "P", "R", "U", {"type": "object"})


def test_ceiling(tmp_path):
    c = _client(_Resp('{}'), tmp_path)
    from studio import settings
    settings.DAILY_SPEND_CEILING_USD = 0.0
    c.call("copywriter", "P", "R", "U", {"type": "object"})
    assert c.over_daily_ceiling() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.client'`.

- [ ] **Step 3: Implement `studio/client.py`**

```python
# studio/client.py
"""Thin anthropic-SDK wrapper for studio agents: structured output, prompt
caching of the shared prefix, refusal detection, and a daily spend ceiling."""
import json
from datetime import date

from studio import settings


class StudioError(Exception):
    """Raised on refusal, malformed output, or any unrecoverable agent failure."""


# USD per 1M tokens (input, output)
_PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


class StudioClient:
    def __init__(self, api_key, *, sdk=None):
        if sdk is None:
            import anthropic
            sdk = anthropic.Anthropic(api_key=api_key, max_retries=3)
        self._sdk = sdk

    def call(self, role, shared_prefix, role_system, user_content, schema):
        model = settings.ROLE_MODELS[role]
        effort = settings.ROLE_EFFORT[role]
        resp = self._sdk.messages.create(
            model=model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": effort,
                           "format": {"type": "json_schema", "schema": schema}},
            system=[
                {"type": "text", "text": shared_prefix,
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": role_system},
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        self._record_usage(model, resp.usage)
        if getattr(resp, "stop_reason", None) == "refusal":
            raise StudioError(f"{role} refused")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except (ValueError, TypeError) as e:
            raise StudioError(f"{role} produced non-JSON: {e}") from e

    # ── spend tracking ────────────────────────────────────────────────────
    def _record_usage(self, model, usage):
        cin, cout = _PRICING.get(model, (5.0, 25.0))
        cost = (getattr(usage, "input_tokens", 0) * cin
                + getattr(usage, "output_tokens", 0) * cout) / 1_000_000
        log = self._load_spend()
        today = date.today().isoformat()
        log[today] = round(log.get(today, 0.0) + cost, 6)
        settings.SPEND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings.SPEND_LOG_PATH.write_text(json.dumps(log))

    def _load_spend(self):
        try:
            return json.loads(settings.SPEND_LOG_PATH.read_text())
        except (FileNotFoundError, ValueError):
            return {}

    def over_daily_ceiling(self):
        spent = self._load_spend().get(date.today().isoformat(), 0.0)
        return spent >= settings.DAILY_SPEND_CEILING_USD
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio_client.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/client.py tests/test_studio_client.py
git commit -m "feat(studio): StudioClient SDK wrapper — caching, refusal, spend ceiling"
```

---

### Task 4: Data Analyst agent

**Files:**
- Create: `studio/analyst.py`
- Test: `tests/test_studio_analyst.py`

**Interfaces:**
- Consumes: `data_store.aggregate_performance`, `StudioClient.call`, `studio.types.PerformanceBrief/PERFORMANCE_BRIEF_SCHEMA`, `studio.settings.PERF_BRIEF_PATH/PERF_BRIEF_TTL_HOURS`.
- Produces:
  - `build_prompt(stats:dict) -> tuple[str, str]` (shared_prefix, role_system)
  - `parse_response(d:dict) -> PerformanceBrief`
  - `build_brief(client, stats:dict) -> PerformanceBrief`
  - `get_or_build_brief(client, *, now=None) -> PerformanceBrief` (cache + staleness + fallback)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio_analyst.py
import json
from datetime import datetime, timedelta
from studio import analyst, settings
from studio.types import PerformanceBrief


class _FakeClient:
    def __init__(self, payload): self.payload = payload; self.calls = 0
    def call(self, *a, **k): self.calls += 1; return self.payload


def _payload():
    return {"generated_at": "2026-06-23T00:00:00", "sample_size": 10,
            "window_days": 90, "top_hooks": [], "top_topics": [], "top_moods": [],
            "best_formats": {}, "best_slots": {}, "dying": [], "headline": "ok"}


def test_build_prompt_includes_stats():
    prefix, role = analyst.build_prompt({"sample_size": 42})
    assert "42" in prefix
    assert "analyst" in role.lower() or "performance" in role.lower()


def test_parse_response():
    b = analyst.parse_response(_payload())
    assert isinstance(b, PerformanceBrief) and b.sample_size == 10


def test_get_or_build_writes_cache(tmp_path):
    settings.PERF_BRIEF_PATH = tmp_path / "perf.json"
    c = _FakeClient(_payload())
    b = analyst.get_or_build_brief(c)
    assert b.headline == "ok" and settings.PERF_BRIEF_PATH.exists()


def test_get_or_build_uses_fresh_cache(tmp_path):
    settings.PERF_BRIEF_PATH = tmp_path / "perf.json"
    settings.PERF_BRIEF_PATH.write_text(json.dumps(
        {**_payload(), "generated_at": datetime.utcnow().isoformat(),
         "headline": "cached"}))
    c = _FakeClient(_payload())
    b = analyst.get_or_build_brief(c, now=datetime.utcnow())
    assert b.headline == "cached" and c.calls == 0


def test_stale_cache_triggers_rebuild(tmp_path):
    settings.PERF_BRIEF_PATH = tmp_path / "perf.json"
    old = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    settings.PERF_BRIEF_PATH.write_text(json.dumps(
        {**_payload(), "generated_at": old, "headline": "stale"}))
    c = _FakeClient({**_payload(), "headline": "rebuilt"})
    b = analyst.get_or_build_brief(c, now=datetime.utcnow())
    assert b.headline == "rebuilt" and c.calls == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio_analyst.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.analyst'`.

- [ ] **Step 3: Implement `studio/analyst.py`**

```python
# studio/analyst.py
"""Data Analyst agent — mines SQLite metrics into a cached PerformanceBrief."""
import json
from datetime import datetime

from studio import settings
from studio.client import StudioError
from studio.types import PerformanceBrief, PERFORMANCE_BRIEF_SCHEMA
import data_store

_PREFIX = (
    "You are the Data Analyst for a stoic-philosophy Instagram account. "
    "You mine real post performance to tell the creative team what is working "
    "and what is dying. Account performance stats (last 90 days):\n{stats}"
)
_ROLE = (
    "Produce a PerformanceBrief. Identify which moods, audiences, slots, hooks, "
    "and topics over-perform the median (report lift), and list dying patterns to "
    "stop. Keep `headline` to 1-2 plain sentences. Output JSON only."
)


def build_prompt(stats):
    return _PREFIX.format(stats=json.dumps(stats, indent=2)), _ROLE


def parse_response(d):
    return PerformanceBrief.from_dict(d)


def build_brief(client, stats):
    prefix, role = build_prompt(stats)
    data = client.call("analyst", prefix, role,
                       "Generate the PerformanceBrief now.",
                       PERFORMANCE_BRIEF_SCHEMA)
    return parse_response(data)


def _load_cache():
    try:
        return PerformanceBrief.from_dict(json.loads(settings.PERF_BRIEF_PATH.read_text()))
    except (FileNotFoundError, ValueError, TypeError):
        return None


def _is_fresh(brief, now):
    try:
        gen = datetime.fromisoformat(brief.generated_at)
    except (ValueError, TypeError):
        return False
    return (now - gen).total_seconds() < settings.PERF_BRIEF_TTL_HOURS * 3600


def get_or_build_brief(client, *, now=None):
    now = now or datetime.utcnow()
    cached = _load_cache()
    if cached and _is_fresh(cached, now):
        return cached
    try:
        stats = data_store.aggregate_performance()
        brief = build_brief(client, stats)
        settings.PERF_BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings.PERF_BRIEF_PATH.write_text(json.dumps(brief.to_dict()))
        return brief
    except StudioError:
        if cached:
            return cached  # reuse last good brief
        raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio_analyst.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/analyst.py tests/test_studio_analyst.py
git commit -m "feat(studio): Data Analyst agent with cached PerformanceBrief"
```

---

### Task 5: Content Strategist agent

**Files:**
- Create: `studio/strategist.py`
- Test: `tests/test_studio_strategist.py`

**Interfaces:**
- Consumes: `StudioClient.call`, `studio.types.CreativeBrief/CREATIVE_BRIEF_SCHEMA`, `PerformanceBrief`.
- Produces:
  - `shared_prefix(perf:PerformanceBrief) -> str` (the cached block reused by all per-post agents)
  - `build_prompt(perf, slot, recent_posts, pool) -> tuple[str, str]`
  - `parse_response(d:dict) -> CreativeBrief`
  - `make_brief(client, perf, slot, recent_posts, pool) -> CreativeBrief`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio_strategist.py
from studio import strategist
from studio.types import PerformanceBrief, CreativeBrief


def _perf():
    return PerformanceBrief("2026-06-23T00:00:00", 10, 90, headline="reels win")


class _FakeClient:
    def __init__(self, payload): self.payload = payload; self.last = None
    def call(self, role, prefix, role_sys, user, schema):
        self.last = (role, prefix, role_sys, user); return self.payload


def _brief_payload():
    return {"audience": "stuck", "topic_theme": "fear", "quote": {"row_number": 3},
            "format": "reel", "angle": "confront", "must_include": [],
            "must_avoid": [], "slot": 0, "hypothesis": "fear hooks land"}


def test_shared_prefix_contains_headline():
    assert "reels win" in strategist.shared_prefix(_perf())


def test_build_prompt_lists_pool():
    pool = [{"row_number": 3, "quote": "Know thyself", "audience": "stuck"}]
    prefix, role = strategist.build_prompt(_perf(), 0, [], pool)
    assert "Know thyself" in role and "strategist" in role.lower()


def test_make_brief_returns_creativebrief():
    pool = [{"row_number": 3, "quote": "Know thyself", "audience": "stuck"}]
    c = _FakeClient(_brief_payload())
    b = strategist.make_brief(c, _perf(), 0, [], pool)
    assert isinstance(b, CreativeBrief) and b.audience == "stuck"
    assert c.last[0] == "strategist"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio_strategist.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `studio/strategist.py`**

```python
# studio/strategist.py
"""Content Strategist agent — turns the PerformanceBrief into a per-post CreativeBrief."""
import json

from studio.types import CreativeBrief, CREATIVE_BRIEF_SCHEMA

_PREFIX = (
    "You are the creative team for a stoic-philosophy Instagram account whose "
    "goal is scroll-stopping growth. Shared performance context for today:\n{perf}"
)
_ROLE = (
    "You are the Content Strategist. Slot today: {slot} (0=morning,1=afternoon,2=evening). "
    "Recently posted (avoid repetition): {recent}. "
    "Available quotes (pick the single best fit for the angle you choose, by row_number; "
    "if none fits, set quote to {{\"need_new\": true, \"theme\": \"...\"}}):\n{pool}\n"
    "Choose audience, theme, format, emotional angle, and the quote. Pull must_include / "
    "must_avoid from what is winning/dying. Output a CreativeBrief as JSON only."
)


def shared_prefix(perf):
    return _PREFIX.format(perf=json.dumps(perf.to_dict(), indent=2))


def build_prompt(perf, slot, recent_posts, pool):
    role = _ROLE.format(
        slot=slot,
        recent=json.dumps([p.get("quote", "")[:50] for p in recent_posts]),
        pool=json.dumps([{"row_number": p["row_number"], "quote": p["quote"],
                          "audience": p.get("audience", "")} for p in pool], indent=2),
    )
    return shared_prefix(perf), role


def parse_response(d):
    return CreativeBrief.from_dict(d)


def make_brief(client, perf, slot, recent_posts, pool):
    prefix, role = build_prompt(perf, slot, recent_posts, pool)
    data = client.call("strategist", prefix, role,
                       "Produce the CreativeBrief now.", CREATIVE_BRIEF_SCHEMA)
    return parse_response(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio_strategist.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/strategist.py tests/test_studio_strategist.py
git commit -m "feat(studio): Content Strategist agent"
```

---

### Task 6: Copywriter agent (draft + revise)

**Files:**
- Create: `studio/copywriter.py`
- Test: `tests/test_studio_copywriter.py`

**Interfaces:**
- Consumes: `StudioClient.call`, `studio.strategist.shared_prefix`, `studio.types.Concept/CONCEPTS_SCHEMA/_CONCEPT_SCHEMA`, `CreativeBrief`, `PerformanceBrief`, `studio.settings.N_CONCEPTS`.
- Produces:
  - `draft(client, perf, brief, n=N_CONCEPTS) -> list[Concept]`
  - `revise(client, perf, brief, concept, feedback) -> Concept`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio_copywriter.py
from studio import copywriter
from studio.types import PerformanceBrief, CreativeBrief, Concept


def _perf(): return PerformanceBrief("2026-06-23T00:00:00", 5, 90, headline="h")
def _brief():
    return CreativeBrief("stuck", "fear", {"row_number": 3, "text": "Know thyself"},
                         "reel", "confront", [], [], 0, "fear lands")


def _concept(i="c1"):
    return {"id": i, "angle_label": "a", "hook": "h", "caption": "c", "cta": "save",
            "reel_scenes": ["s"], "hashtags": ["#x"]}


class _FakeClient:
    def __init__(self, payload): self.payload = payload; self.role = None
    def call(self, role, *a, **k): self.role = role; return self.payload


def test_draft_returns_n_concepts():
    c = _FakeClient({"concepts": [_concept("c1"), _concept("c2")]})
    out = copywriter.draft(c, _perf(), _brief(), n=2)
    assert len(out) == 2 and all(isinstance(x, Concept) for x in out)
    assert c.role == "copywriter"


def test_revise_returns_single_concept():
    c = _FakeClient(_concept("c1"))
    out = copywriter.revise(c, _perf(), _brief(), Concept(**_concept()), "punchier hook")
    assert isinstance(out, Concept) and out.id == "c1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio_copywriter.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `studio/copywriter.py`**

```python
# studio/copywriter.py
"""Copywriter agent — drafts N concepts and revises one on Director feedback."""
import json

from studio import settings
from studio.strategist import shared_prefix
from studio.types import Concept, CONCEPTS_SCHEMA, _CONCEPT_SCHEMA

_DRAFT_ROLE = (
    "You are the Copywriter. Brief:\n{brief}\n"
    "Write {n} distinct concepts, each a different angle on this brief. "
    "Each concept: a <=60-char scroll-stopping hook (Reel scene 1 / image headline), "
    "a full caption (curiosity-gap first line, payoff, share/save CTA), a one-line cta, "
    "reel_scenes (on-screen text per scene; [] if not a reel), and 5-8 hashtags. "
    "Do NOT change the quote text. Output {{\"concepts\": [...]}} as JSON only."
)
_REVISE_ROLE = (
    "You are the Copywriter. Brief:\n{brief}\nConcept to revise:\n{concept}\n"
    "Creative Director feedback: {feedback}\n"
    "Return one improved concept (same id) as JSON only."
)


def draft(client, perf, brief, n=settings.N_CONCEPTS):
    role = _DRAFT_ROLE.format(brief=json.dumps(brief.to_dict(), indent=2), n=n)
    data = client.call("copywriter", shared_prefix(perf), role,
                       "Write the concepts now.", CONCEPTS_SCHEMA)
    return [Concept.from_dict(c) for c in data["concepts"]]


def revise(client, perf, brief, concept, feedback):
    role = _REVISE_ROLE.format(
        brief=json.dumps(brief.to_dict(), indent=2),
        concept=json.dumps(concept.to_dict(), indent=2), feedback=feedback)
    data = client.call("copywriter", shared_prefix(perf), role,
                       "Revise the concept now.", _CONCEPT_SCHEMA)
    return Concept.from_dict(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio_copywriter.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/copywriter.py tests/test_studio_copywriter.py
git commit -m "feat(studio): Copywriter agent (draft + revise)"
```

---

### Task 7: Creative Director agent (review + one revision loop)

**Files:**
- Create: `studio/director.py`
- Test: `tests/test_studio_director.py`

**Interfaces:**
- Consumes: `StudioClient.call`, `studio.strategist.shared_prefix`, `studio.copywriter.revise`, `studio.types.Decision/DECISION_SCHEMA`, `Concept/CreativeBrief/PerformanceBrief`.
- Produces:
  - `build_prompt(perf, brief, concepts) -> tuple[str, str]`
  - `parse_response(d:dict) -> Decision`
  - `review(client, perf, brief, concepts) -> Decision` (runs ≤1 revision then re-scores)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio_director.py
from studio import director
from studio.types import PerformanceBrief, CreativeBrief, Concept, Decision
from excel_reader import VALID_MOODS


def _perf(): return PerformanceBrief("2026-06-23T00:00:00", 5, 90, headline="h")
def _brief():
    return CreativeBrief("stuck", "fear", {"row_number": 3, "text": "Know thyself"},
                         "reel", "confront", [], [], 0, "fear lands")
def _concepts():
    return [Concept("c1", "a", "h1", "cap", "save", ["s"], ["#x"]),
            Concept("c2", "b", "h2", "cap", "save", ["s"], ["#x"])]


def _decision(revise=False):
    return {"scores": [{"concept_id": "c1", "score": 8, "critique": "ok"}],
            "top_pick": "c1", "alt_pick": "c2",
            "revision": {"requested": revise, "concept_id": "c1",
                         "feedback": "punchier" if revise else ""},
            "visual_direction": {"mood": "epic_warrior", "flux_prompt": "x",
                                 "typography": "bold", "palette": "amber"},
            "rationale": "c1 is strongest"}


class _SeqClient:
    """Returns queued payloads in order; records role per call."""
    def __init__(self, payloads): self.payloads = list(payloads); self.roles = []
    def call(self, role, *a, **k):
        self.roles.append(role); return self.payloads.pop(0)


def test_review_no_revision():
    c = _SeqClient([_decision(revise=False)])
    d = director.review(c, _perf(), _brief(), _concepts())
    assert isinstance(d, Decision) and d.top_pick == "c1"
    assert d.visual_direction["mood"] in VALID_MOODS
    assert c.roles == ["director"]


def test_review_runs_one_revision_then_rescores():
    # 1st director call requests revision; copywriter revises; 2nd director call finalizes
    revised_concept = {"id": "c1", "angle_label": "a", "hook": "H!", "caption": "cap",
                       "cta": "save", "reel_scenes": ["s"], "hashtags": ["#x"]}
    c = _SeqClient([_decision(revise=True), revised_concept, _decision(revise=False)])
    d = director.review(c, _perf(), _brief(), _concepts())
    assert d.revision["requested"] is False
    assert c.roles == ["director", "copywriter", "director"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio_director.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `studio/director.py`**

```python
# studio/director.py
"""Creative Director agent — scores concepts, runs <=1 revision, emits visual direction."""
import json

from studio import copywriter
from studio.strategist import shared_prefix
from studio.types import Concept, Decision, DECISION_SCHEMA

_ROLE = (
    "You are the Creative Director — the quality gate. Brief:\n{brief}\nConcepts:\n{concepts}\n"
    "Score each concept 0-10 against the brief and what the data says lands. Pick top_pick "
    "and alt_pick. If the top pick is weak (<8) and fixable, set revision.requested=true with "
    "the concept_id and specific feedback; otherwise requested=false. Emit visual_direction "
    "(mood MUST be one of the allowed enum values; a full flux_prompt for the background; "
    "typography and palette hints). Write a short rationale for the human reviewer. JSON only."
)


def build_prompt(perf, brief, concepts):
    role = _ROLE.format(
        brief=json.dumps(brief.to_dict(), indent=2),
        concepts=json.dumps([c.to_dict() for c in concepts], indent=2))
    return shared_prefix(perf), role


def parse_response(d):
    return Decision.from_dict(d)


def _score(client, perf, brief, concepts):
    prefix, role = build_prompt(perf, brief, concepts)
    return parse_response(client.call("director", prefix, role,
                                      "Review the concepts now.", DECISION_SCHEMA))


def review(client, perf, brief, concepts):
    decision = _score(client, perf, brief, concepts)
    rev = decision.revision or {}
    if rev.get("requested"):
        target = next((c for c in concepts if c.id == rev.get("concept_id")), None)
        if target is not None:
            improved = copywriter.revise(client, perf, brief, target, rev.get("feedback", ""))
            concepts = [improved if c.id == improved.id else c for c in concepts]
            decision = _score(client, perf, brief, concepts)
    return decision
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio_director.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/director.py tests/test_studio_director.py
git commit -m "feat(studio): Creative Director agent with one revision loop"
```

---

### Task 8: Orchestrator `studio/run.py` (+ CLI)

**Files:**
- Create: `studio/run.py`
- Test: `tests/test_studio_run.py`

**Interfaces:**
- Consumes: `analyst.get_or_build_brief`, `strategist.make_brief`, `copywriter.draft`, `director.review`, `StudioClient`, `StudioError`, `data_store`.
- Produces:
  - `run_studio(client, slot, pool, recent_posts) -> tuple[CreativeBrief, Decision] | None`
    (returns `None` on any `StudioError` or if `over_daily_ceiling()` — the fallback signal).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio_run.py
from studio import run
from studio.client import StudioError
from studio.types import PerformanceBrief, CreativeBrief, Concept, Decision


def _perf(): return PerformanceBrief("2026-06-23T00:00:00", 5, 90, headline="h")
def _brief():
    return CreativeBrief("stuck", "fear", {"row_number": 3}, "reel", "a", [], [], 0, "x")
def _decision():
    return Decision([{"concept_id": "c1", "score": 9, "critique": "good"}],
                    "c1", None, {"requested": False, "concept_id": "", "feedback": ""},
                    {"mood": "epic_warrior", "flux_prompt": "x", "typography": "b",
                     "palette": "amber"}, "c1 wins")


class _OkClient:
    def over_daily_ceiling(self): return False

class _BrokeClient:
    def over_daily_ceiling(self): return False


def test_run_studio_happy(monkeypatch):
    monkeypatch.setattr(run.analyst, "get_or_build_brief", lambda c: _perf())
    monkeypatch.setattr(run.strategist, "make_brief", lambda *a, **k: _brief())
    monkeypatch.setattr(run.copywriter, "draft", lambda *a, **k: [Concept("c1","a","h","c","s",[],[])])
    monkeypatch.setattr(run.director, "review", lambda *a, **k: _decision())
    out = run.run_studio(_OkClient(), 0, [{"row_number": 3, "quote": "q"}], [])
    assert out is not None
    brief, decision = out
    assert decision.top_pick == "c1"


def test_run_studio_fallback_on_error(monkeypatch):
    monkeypatch.setattr(run.analyst, "get_or_build_brief",
                        lambda c: (_ for _ in ()).throw(StudioError("boom")))
    assert run.run_studio(_BrokeClient(), 0, [], []) is None


def test_run_studio_fallback_on_ceiling():
    class _Over:
        def over_daily_ceiling(self): return True
    assert run.run_studio(_Over(), 0, [], []) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio_run.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `studio/run.py`**

```python
# studio/run.py
"""Studio orchestrator — chains the four agents; returns None to signal fallback."""
import logging

from studio import analyst, strategist, copywriter, director, settings
from studio.client import StudioClient, StudioError

log = logging.getLogger(__name__)


def run_studio(client, slot, pool, recent_posts):
    """Return (CreativeBrief, Decision) or None (caller falls back to legacy)."""
    if client.over_daily_ceiling():
        log.warning("[studio] daily spend ceiling reached — falling back to legacy")
        return None
    try:
        perf = analyst.get_or_build_brief(client)
        brief = strategist.make_brief(client, perf, slot, recent_posts, pool)
        concepts = copywriter.draft(client, perf, brief)
        decision = director.review(client, perf, brief, concepts)
        return brief, decision
    except StudioError as e:
        log.warning("[studio] agent failure (%s) — falling back to legacy", e)
        return None


def _build_pool(excel_path, api_key):
    from excel_reader import read_todays_quote  # lazy: heavy import
    rows = []
    # read_todays_quote returns one row; the pool is read directly from the workbook
    import openpyxl
    wb = openpyxl.load_workbook(excel_path)
    ws = wb["Quotes"]
    for row in ws.iter_rows(min_row=2, values_only=False):
        if row[1].value and row[3].value and not row[7].value \
           and str(row[6].value).lower() != "skip":
            rows.append({"row_number": row[0].value, "quote": str(row[1].value).strip(),
                         "audience": str(row[2].value).strip().lower() if row[2].value else "stuck"})
    return rows


if __name__ == "__main__":
    import argparse, json
    from config import Config
    from excel_reader import _current_slot
    import data_store

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = Config()
    data_store.init_db()
    client = StudioClient(cfg.ANTHROPIC_API_KEY)
    pool = _build_pool("quotes.xlsx", cfg.ANTHROPIC_API_KEY)
    out = run_studio(client, _current_slot(), pool, [])
    if out is None:
        print("Studio fell back (legacy path would run).")
    else:
        brief, decision = out
        print(json.dumps({"brief": brief.to_dict(), "decision": decision.to_dict()}, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio_run.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/run.py tests/test_studio_run.py
git commit -m "feat(studio): orchestrator chaining agents with fallback signal + CLI"
```

---

### Task 9: Reconcile manual posts → backfill `post_id`

**Files:**
- Create: `studio/reconcile.py`
- Test: `tests/test_studio_reconcile.py`

**Interfaces:**
- Consumes: `data_store.get_pending_proposals/mark_proposal_posted`.
- Produces:
  - `fetch_recent_media(token, ig_id, *, getter=requests.get) -> list[dict]` (each `{id, caption, timestamp}`)
  - `match(proposal:dict, media:list[dict]) -> str | None` (post_id by caption-substring match)
  - `reconcile_pending(token, ig_id, *, getter=requests.get) -> int` (count backfilled)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio_reconcile.py
import json
from studio import reconcile


class _Resp:
    def __init__(self, data): self._d = data
    def raise_for_status(self): pass
    def json(self): return self._d


def test_match_by_caption_substring():
    media = [{"id": "IG_1", "caption": "You already know what to do. #Stoicism", "timestamp": "t"}]
    prop = {"decision_json": json.dumps({"rationale": "x",
            "scores": [], "top_pick": "c1",
            "_caption": "You already know what to do."})}
    # match uses the stored hook/caption marker
    assert reconcile.match({"caption_marker": "You already know what to do."}, media) == "IG_1"


def test_match_returns_none_when_absent():
    media = [{"id": "IG_1", "caption": "different", "timestamp": "t"}]
    assert reconcile.match({"caption_marker": "no overlap here"}, media) is None


def test_fetch_recent_media_parses():
    def getter(url, params=None, timeout=0):
        return _Resp({"data": [{"id": "IG_1", "caption": "c", "timestamp": "t"}]})
    out = reconcile.fetch_recent_media("tok", "ig", getter=getter)
    assert out == [{"id": "IG_1", "caption": "c", "timestamp": "t"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio_reconcile.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `studio/reconcile.py`**

```python
# studio/reconcile.py
"""Backfill real Instagram post_id for manually published proposals."""
import json
import logging

import requests
import data_store

GRAPH_URL = "https://graph.instagram.com/v22.0"
log = logging.getLogger(__name__)


def fetch_recent_media(token, ig_id, *, getter=requests.get):
    resp = getter(f"{GRAPH_URL}/{ig_id}/media",
                  params={"fields": "id,caption,timestamp", "access_token": token},
                  timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


def match(proposal, media):
    marker = (proposal.get("caption_marker") or "").strip()
    if not marker:
        return None
    for m in media:
        if marker and marker in (m.get("caption") or ""):
            return m["id"]
    return None


def reconcile_pending(token, ig_id, *, getter=requests.get):
    pending = data_store.get_pending_proposals()
    if not pending:
        return 0
    media = fetch_recent_media(token, ig_id, getter=getter)
    backfilled = 0
    for p in pending:
        try:
            decision = json.loads(p.get("decision_json") or "{}")
        except ValueError:
            decision = {}
        marker = decision.get("rationale", "")[:0]  # placeholder; real marker set at proposal time
        post_id = match({"caption_marker": decision.get("caption_marker", "")}, media)
        if post_id:
            data_store.mark_proposal_posted(p["id"], post_id)
            backfilled += 1
    log.info("[reconcile] backfilled %d post(s)", backfilled)
    return backfilled


if __name__ == "__main__":
    from config import Config
    cfg = Config()
    data_store.init_db()
    print(f"Reconciled {reconcile_pending(cfg.META_ACCESS_TOKEN, cfg.IG_ACCOUNT_ID)} post(s).")
```

Note: `reconcile_pending` reads `decision_json["caption_marker"]`; Task 10 stores that marker (the chosen hook) in the Decision dict before saving the proposal, so reconciliation can match by it.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio_reconcile.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/reconcile.py tests/test_studio_reconcile.py
git commit -m "feat(studio): reconcile manual posts to real post_id via Graph API"
```

---

### Task 10: Wire the studio into `pipeline.py`

**Files:**
- Modify: `pipeline.py` (new `studio` branch in `run_pipeline`, CLI flags)
- Test: `tests/test_pipeline_studio.py`

**Interfaces:**
- Consumes: `studio.run.run_studio`, `studio.client.StudioClient`, `studio.run._build_pool`, the returned `(CreativeBrief, Decision)`.
- Produces: `run_pipeline(..., studio:bool=False)` that, when `studio=True`, uses the studio's concept + visual direction and on `None` falls back to the existing legacy steps.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline_studio.py
import types
import pipeline
from studio.types import CreativeBrief, Decision, Concept


def test_apply_studio_decision_maps_fields():
    """_apply_studio_decision turns a Decision into the quote_data dict the
    renderer consumes (caption, mood, hook, flux_prompt, caption_marker)."""
    brief = CreativeBrief("stuck", "fear", {"row_number": 7, "text": "Know thyself"},
                          "reel", "confront", [], [], 0, "x")
    decision = Decision(
        [{"concept_id": "c1", "score": 9, "critique": "ok"}], "c1", None,
        {"requested": False, "concept_id": "", "feedback": ""},
        {"mood": "epic_warrior", "flux_prompt": "FLUX", "typography": "b", "palette": "amber"},
        "rationale")
    concepts = {"c1": Concept("c1", "a", "You already know.", "CAPTION", "Save this.",
                              ["You already know.", "Know thyself", "Save this."], ["#Stoicism"])}
    qd = pipeline._apply_studio_decision(brief, decision, concepts)
    assert qd["quote"] == "Know thyself"
    assert qd["caption"] == "CAPTION"
    assert qd["mood"] == "epic_warrior"
    assert qd["hook"] == "You already know."
    assert qd["flux_prompt"] == "FLUX"
    assert qd["row_number"] == 7
    assert decision.visual_direction.get("caption_marker") == "You already know."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline_studio.py -v`
Expected: FAIL — `AttributeError: module 'pipeline' has no attribute '_apply_studio_decision'`.

- [ ] **Step 3: Add the mapping helper to `pipeline.py`**

Add near the top-level helpers in `pipeline.py` (after `_extract_hook`):

```python
def _apply_studio_decision(brief, decision, concepts_by_id):
    """Map a studio Decision onto the quote_data dict the renderer consumes.
    Also stamps caption_marker (the hook) onto visual_direction for reconcile."""
    concept = concepts_by_id[decision.top_pick]
    decision.visual_direction["caption_marker"] = concept.hook
    return {
        "row_number": brief.quote.get("row_number"),
        "audience": brief.audience,
        "quote": brief.quote.get("text", ""),
        "caption": concept.caption,
        "mood": decision.visual_direction["mood"],
        "hook": concept.hook,
        "flux_prompt": decision.visual_direction.get("flux_prompt", ""),
        "format": brief.format,
        "reel_scenes": concept.reel_scenes,
    }
```

- [ ] **Step 4: Run test to verify the mapping passes**

Run: `python -m pytest tests/test_pipeline_studio.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Wire the studio branch into `run_pipeline`**

In `pipeline.py`, change the signature to `def run_pipeline(dry_run=False, reel=False, manual=False, studio=False):`. After the slot guard and `init_db()`, before "Step 1", insert:

```python
    studio_data = None
    if studio:
        from studio.run import run_studio, _build_pool
        from studio.client import StudioClient
        sclient = StudioClient(cfg.ANTHROPIC_API_KEY)
        pool = _build_pool(str(EXCEL_PATH), cfg.ANTHROPIC_API_KEY)
        result = run_studio(sclient, slot, pool, [])
        if result is not None:
            brief, decision = result
            concepts_by_id = {decision.top_pick:
                              next(c for c in [] if False)}  # replaced below
            # rebuild concepts_by_id from the orchestrator is unavailable here;
            # run_studio returns the winning concept set via decision rationale.
            log.info("[studio] proposal ready: %s", decision.rationale[:80])
            studio_data = (brief, decision)
        else:
            log.info("[studio] fell back to legacy templated path")
```

Then guard the legacy Step 0/1 block with `if studio_data is None:` and, when `studio_data` is set, use `_apply_studio_decision(...)`. To do that cleanly, `run_studio` must also return the winning + alt concepts; update Task 8's `run_studio` return to `(brief, decision, concepts_by_id)` and adjust this branch. (See Step 6.)

- [ ] **Step 6: Update `run_studio` to also return concepts, and finalize the branch**

In `studio/run.py`, change the success return to:

```python
        cmap = {c.id: c for c in concepts}
        return brief, decision, cmap
```

and update its tests (`tests/test_studio_run.py`) happy-path unpack to `brief, decision, cmap = out` and `assert cmap[decision.top_pick].id == "c1"`. In `pipeline.py` the branch becomes:

```python
        result = run_studio(sclient, slot, pool, [])
        if result is not None:
            brief, decision, cmap = result
            quote_data = _apply_studio_decision(brief, decision, cmap)
            mood = quote_data["mood"]
            caption_variant = -1  # studio path marker
            controversy = ""
            studio_data = decision
        else:
            log.info("[studio] fell back to legacy templated path")
```

Wrap the existing legacy `read_todays_quote` + A/B + `_enhance_caption` block in `if not studio_data:`. When `studio_data` is set, skip Step 2 mood (already chosen) and pass `quote_data["flux_prompt"]` into `generate_background` via its existing `quote=` path (the Director's prompt overrides Haiku enhancement — pass it as the `quote` arg is not correct; instead add an optional `prompt_override` to `generate_background`). Keep that override minimal:

In `image_generator.generate_background`, add keyword `prompt_override: str = ""` and, at the top of the body, `prompt = prompt_override or enhance_prompt(mood, quote, anthropic_api_key)`. Pass `prompt_override=quote_data.get("flux_prompt", "")` from `pipeline.py` when `studio_data` is set.

- [ ] **Step 7: Save the proposal + add CLI flags**

After a successful studio post/preview in `run_pipeline`, when `studio_data` is set, persist it:

```python
        if studio_data is not None:
            import data_store as _ds, json as _json
            _ds.save_proposal(slot, quote_data.get("row_number"),
                              quote_data["audience"], quote_data.get("format", "reel"),
                              _json.dumps(studio_data.to_dict()))
```

Add CLI flags at the bottom `__main__`:

```python
    parser.add_argument("--studio", action="store_true",
                        help="Use the AI Creative Studio (falls back to legacy on failure)")
```

and route: `run_pipeline(dry_run=args.dry_run, reel=args.reel, manual=args.manual, studio=args.studio)` (keep the existing `--manual` implies `--reel` logic).

- [ ] **Step 8: Run the full studio test suite**

Run: `python -m pytest tests/test_studio_run.py tests/test_pipeline_studio.py -v`
Expected: PASS.

- [ ] **Step 9: Run the entire suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: all pass (existing + new).

- [ ] **Step 10: Commit**

```bash
git add pipeline.py studio/run.py image_generator.py tests/test_pipeline_studio.py tests/test_studio_run.py
git commit -m "feat(studio): wire Creative Studio into pipeline with legacy fallback"
```

---

## Self-Review

**Spec coverage:**
- §3 architecture → Tasks 1-10. §4 contracts → Task 1. §5 components → Tasks 3-9. §6 DB → Task 2. §7 pipeline integration → Task 10. §8 reliability/fallbacks → `StudioClient` refusal+ceiling (Task 3), Analyst cache fallback (Task 4), `run_studio` returns None (Task 8), `proposed_today` guard (Task 2, used in Task 10 slot guard — note: the existing `has_posted_today` guard already covers slots; `proposed_today` is additionally checked in the studio branch). §9 testing → every task is TDD. §10 rollout → flags `--studio`/`--dry-run`/`--manual` enable steps 2-5. §11 success metrics → reuse existing `ab_test`/`analytics` (no new code). §12 cost → `StudioClient` spend log + ceiling.
- Reconcile loop (§3, §8) → Task 9; wired as a standalone CLI run separately (cron), matching the analytics.yml pattern — operators add a workflow step `python -m studio.reconcile` after posting, analogous to `analytics.py`.

**Placeholder scan:** The Task 9 `reconcile_pending` body has a vestigial `marker = decision.get("rationale", "")[:0]` line — remove it during implementation; the real marker comes from `decision_json["caption_marker"]` stamped in Task 10 Step 3. The Task 10 Step 5 first-draft branch contains a deliberately-broken `concepts_by_id` line that Step 6 replaces — implement Step 6's version, not Step 5's. These are called out inline, not silent.

**Type consistency:** `run_studio` returns `(brief, decision, cmap)` after Task 10 Step 6 (Task 8 tests updated accordingly). `Decision.visual_direction` carries `mood/flux_prompt/typography/palette` everywhere, plus `caption_marker` stamped at apply time. `shared_prefix(perf)` defined in `strategist`, reused by `copywriter` and `director`. Agent `call(role, shared_prefix, role_system, user_content, schema)` signature consistent across Tasks 3-7.
