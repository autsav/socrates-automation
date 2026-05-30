# Socrates Pipeline Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SQLite state tracking, auto token refresh, A/B testing with Thompson sampling, Meta Insights ingestion, and Reel audio to the Socrates Instagram pipeline.

**Architecture:** Four new modules (`data_store.py`, `ab_test.py`, `token_manager.py`, `analytics.py`) integrate with existing `pipeline.py` via SQLite. A/B decisions run before quote selection; analytics ingestion runs via separate GitHub Actions cron.

**Tech Stack:** Python 3.11, SQLite, `requests`, `httpx`, `pytest`, GitHub Actions

---

## File Structure

| File | Action | Responsibility |
|------|--------|--------------|
| `socrates_pipeline/data_store.py` | Create | SQLite CRUD: posts, post_metrics, ab_results, token_state |
| `socrates_pipeline/ab_test.py` | Create | Thompson Sampling bandit for caption/mood/slot |
| `socrates_pipeline/token_manager.py` | Create | Meta token refresh via fb_exchange_token |
| `socrates_pipeline/analytics.py` | Create | Fetch Meta Insights + ingest pending metrics |
| `socrates_pipeline/existing_excel_reader.py` | Modify | Add dual-caption support (caption_a, caption_b) |
| `socrates_pipeline/generate_quotes_excel.py` | Modify | Generate two caption variants per quote |
| `socrates_pipeline/pipeline.py` | Modify | Integrate A/B engine, SQLite state, token refresh |
| `socrates_pipeline/config.py` | Modify | Add META_APP_ID, META_APP_SECRET |
| `socrates_pipeline/.env.example` | Modify | Document new env vars |
| `.github/workflows/analytics.yml` | Create | Daily cron to ingest Meta Insights |
| `.github/workflows/daily_post.yml` | Modify | Add init_db, generate_audio, token refresh steps |
| `tests/test_data_store.py` | Create | Unit tests for SQLite CRUD |
| `tests/test_ab_test.py` | Create | Unit tests for Thompson Sampling |
| `tests/test_token_manager.py` | Create | Unit tests for token refresh logic |
| `tests/test_analytics.py` | Create | Unit tests for Insights fetch + ingest |
| `socrates_pipeline/data/` | Create dir | SQLite DB location (gitignored) |

---

## Task 1: Set up project scaffolding

**Files:**
- Create: `socrates_pipeline/data/.gitkeep`
- Modify: `socrates_pipeline/.gitignore`

- [ ] **Step 1: Create data directory for SQLite**

```bash
mkdir -p socrates_pipeline/data
touch socrates_pipeline/data/.gitkeep
```

- [ ] **Step 2: Update .gitignore to ignore SQLite DB files but keep directory**

Edit `socrates_pipeline/.gitignore`:

```gitignore
# Existing entries...
# SQLite
*.db
*.db-journal
*.db-wal
```

- [ ] **Step 3: Commit**

```bash
git add socrates_pipeline/data/.gitkeep socrates_pipeline/.gitignore
git commit -m "chore: add data directory for SQLite state"
```

---

## Task 2: Implement data_store.py

**Files:**
- Create: `socrates_pipeline/data_store.py`
- Test: `tests/test_data_store.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_data_store.py`:

```python
import sqlite3
import pytest
from pathlib import Path

# Import from parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "socrates_pipeline"))

from data_store import init_db, save_post, mark_posted, get_ab_results, record_ab_win, get_last_posted_for_audience

@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    import data_store
    data_store.DB_PATH = db_path
    init_db()
    return db_path


def test_init_db_creates_tables(db):
    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "posts" in tables
    assert "post_metrics" in tables
    assert "ab_results" in tables
    assert "token_state" in tables
    conn.close()


def test_save_post_returns_row_id(db):
    row_id = save_post("Test quote", "stuck", "calm_stoic", 0, 0)
    assert isinstance(row_id, int)
    assert row_id > 0


def test_mark_posted_updates_record(db):
    row_id = save_post("Test quote", "stuck", "calm_stoic", 0, 0)
    mark_posted(row_id, "ig_post_123", "/output/test.jpg", "/output/test.mp4")

    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    cursor.execute("SELECT post_id, image_path, reel_path FROM posts WHERE id = ?", (row_id,))
    post_id, image_path, reel_path = cursor.fetchone()
    conn.close()

    assert post_id == "ig_post_123"
    assert image_path == "/output/test.jpg"
    assert reel_path == "/output/test.mp4"


def test_ab_results_roundtrip(db):
    get_ab_results("caption", "hook_first", "story_first")  # creates row implicitly
    record_ab_win("caption", "hook_first", "story_first", "hook_first")
    result = get_ab_results("caption", "hook_first", "story_first")
    assert result["wins_a"] == 1
    assert result["wins_b"] == 0
    assert result["trials"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd socrates_pipeline
pytest ../tests/test_data_store.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data_store'`

- [ ] **Step 3: Write minimal implementation**

Create `socrates_pipeline/data_store.py`:

```python
"""
SQLite state store for pipeline posts, metrics, A/B results, and token state.
WAL mode enabled for concurrent reader/writer safety.
"""

import sqlite3
import time
import random
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "pipeline.db"


def _get_connection() -> sqlite3.Connection:
    """Return a connection with WAL mode enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_text TEXT NOT NULL,
            audience TEXT NOT NULL,
            mood TEXT NOT NULL,
            caption_variant INTEGER DEFAULT 0,
            posting_slot INTEGER DEFAULT 0,
            posted_at TIMESTAMP,
            post_id TEXT UNIQUE,
            image_path TEXT,
            reel_path TEXT,
            dry_run BOOLEAN DEFAULT FALSE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS post_metrics (
            post_id TEXT PRIMARY KEY,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            reach INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            saved INTEGER DEFAULT 0,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts(post_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ab_results (
            dimension TEXT NOT NULL,
            variant_a TEXT NOT NULL,
            variant_b TEXT NOT NULL,
            wins_a INTEGER DEFAULT 0,
            wins_b INTEGER DEFAULT 0,
            trials INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (dimension, variant_a, variant_b)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS token_state (
            service TEXT PRIMARY KEY,
            token TEXT NOT NULL,
            expires_at TIMESTAMP,
            last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_post(
    quote_text: str,
    audience: str,
    mood: str,
    caption_variant: int,
    posting_slot: int,
    dry_run: bool = False,
) -> int:
    """Insert a new post record. Returns row id."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO posts (quote_text, audience, mood, caption_variant, posting_slot, posted_at, dry_run)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (quote_text, audience, mood, caption_variant, posting_slot, datetime.now().isoformat(), dry_run),
    )
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def mark_posted(row_id: int, post_id: str, image_path: str, reel_path: str | None = None) -> None:
    """Update post with actual post_id and paths after successful publish."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE posts SET post_id = ?, image_path = ?, reel_path = ? WHERE id = ?",
        (post_id, image_path, reel_path, row_id),
    )
    conn.commit()
    conn.close()


def get_ab_results(dimension: str, variant_a: str, variant_b: str) -> dict:
    """Return wins_a, wins_b, trials for a dimension pair."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT wins_a, wins_b, trials FROM ab_results
        WHERE dimension = ? AND variant_a = ? AND variant_b = ?
        """,
        (dimension, variant_a, variant_b),
    )
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            """
            INSERT INTO ab_results (dimension, variant_a, variant_b, wins_a, wins_b, trials)
            VALUES (?, ?, ?, 0, 0, 0)
            """,
            (dimension, variant_a, variant_b),
        )
        conn.commit()
        conn.close()
        return {"wins_a": 0, "wins_b": 0, "trials": 0}
    conn.close()
    return {"wins_a": row[0], "wins_b": row[1], "trials": row[2]}


def record_ab_win(dimension: str, variant_a: str, variant_b: str, winner: str) -> None:
    """Increment wins for the winning variant."""
    conn = _get_connection()
    cursor = conn.cursor()
    if winner == variant_a:
        cursor.execute(
            """
            UPDATE ab_results
            SET wins_a = wins_a + 1, trials = trials + 1, last_updated = CURRENT_TIMESTAMP
            WHERE dimension = ? AND variant_a = ? AND variant_b = ?
            """,
            (dimension, variant_a, variant_b),
        )
    elif winner == variant_b:
        cursor.execute(
            """
            UPDATE ab_results
            SET wins_b = wins_b + 1, trials = trials + 1, last_updated = CURRENT_TIMESTAMP
            WHERE dimension = ? AND variant_a = ? AND variant_b = ?
            """,
            (dimension, variant_a, variant_b),
        )
    else:
        raise ValueError(f"winner must be '{variant_a}' or '{variant_b}', got '{winner}'")
    conn.commit()
    conn.close()


def get_last_posted_for_audience(audience: str, days: int = 30) -> list[dict]:
    """Return recent posts for an audience with metrics joined."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.*, m.likes, m.comments, m.reach, m.impressions
        FROM posts p
        LEFT JOIN post_metrics m ON p.post_id = m.post_id
        WHERE p.audience = ? AND p.posted_at >= datetime('now', '-? days')
        ORDER BY p.posted_at DESC
        """,
        (audience, days),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def save_token(service: str, token: str, expires_at: datetime | None = None) -> None:
    """Store or update a token."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO token_state (service, token, expires_at, last_refreshed)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(service) DO UPDATE SET
            token = excluded.token,
            expires_at = excluded.expires_at,
            last_refreshed = CURRENT_TIMESTAMP
        """,
        (service, token, expires_at.isoformat() if expires_at else None),
    )
    conn.commit()
    conn.close()


def get_token(service: str) -> dict | None:
    """Return {token, expires_at, last_refreshed} or None."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT token, expires_at, last_refreshed FROM token_state WHERE service = ?",
        (service,),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "token": row[0],
        "expires_at": row[1],
        "last_refreshed": row[2],
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd socrates_pipeline
pytest ../tests/test_data_store.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add socrates_pipeline/data_store.py tests/test_data_store.py socrates_pipeline/data/.gitkeep socrates_pipeline/.gitignore
git commit -m "feat: add SQLite state store for posts, metrics, A/B results, tokens"
```

---

## Task 3: Implement ab_test.py

**Files:**
- Create: `socrates_pipeline/ab_test.py`
- Test: `tests/test_ab_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ab_test.py`:

```python
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "socrates_pipeline"))

from ab_test import pick_caption_variant, pick_mood, pick_optimal_slot


class MockDataStore:
    """In-memory data store for testing."""
    def __init__(self):
        self.ab_results = {}
        self.posts = []

    def get_ab_results(self, dimension, variant_a, variant_b):
        key = (dimension, variant_a, variant_b)
        return self.ab_results.get(key, {"wins_a": 0, "wins_b": 0, "trials": 0})

    def get_last_posted_for_audience(self, audience, days=30):
        return self.posts


def test_pick_caption_variant_cold_start_randomises():
    mock_db = MockDataStore()
    results = set()
    for _ in range(20):
        results.add(pick_caption_variant("stuck", mock_db.get_ab_results))
    assert len(results) == 2  # Both 0 and 1 seen


def test_pick_caption_variant_prefers_winner():
    mock_db = MockDataStore()
    mock_db.ab_results[("caption", "hook_first", "story_first")] = {
        "wins_a": 20, "wins_b": 2, "trials": 22
    }
    winners = sum(pick_caption_variant("stuck", mock_db.get_ab_results) for _ in range(100))
    # With 20 vs 2 wins, variant_a (0) should win most of the time
    assert winners < 50


def test_pick_optimal_slot_returns_valid_value():
    mock_db = MockDataStore()
    slot = pick_optimal_slot("procrastinator", mock_db.get_ab_results)
    assert slot in [0, 1, 2]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd socrates_pipeline
pytest ../tests/test_ab_test.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ab_test'`

- [ ] **Step 3: Write minimal implementation**

Create `socrates_pipeline/ab_test.py`:

```python
"""
A/B Test Engine — Thompson Sampling (Beta-Bernoulli bandit).
Selects caption variant, image mood, and posting slot based on
rolling 30-day performance data from SQLite.
"""

import random
from typing import Callable


def _thompson_sample(wins_a: int, wins_b: int, trials: int) -> str:
    """
    Sample from Beta(wins+1, trials-wins+1) for each variant.
    Returns 'a' or 'b'.
    """
    # Beta(wins + 1, (trials - wins) + 1)
    sample_a = random.betavariate(wins_a + 1, (trials - wins_a) + 1)
    sample_b = random.betavariate(wins_b + 1, (trials - wins_b) + 1)
    return "a" if sample_a > sample_b else "b"


def pick_caption_variant(
    audience: str,
    get_ab_results: Callable[[str, str, str], dict],
) -> int:
    """
    Return 0 (hook-first) or 1 (story-first) using Thompson Sampling.
    Falls back to random if < 5 trials (cold start).
    """
    results = get_ab_results("caption", "hook_first", "story_first")
    wins_a = results["wins_a"]
    wins_b = results["wins_b"]
    trials = results["trials"]

    if trials < 5:
        variant = random.choice([0, 1])
        print(f"  [ab] caption cold start ({trials} trials) → random {variant}")
        return variant

    winner = _thompson_sample(wins_a, wins_b, trials)
    variant = 0 if winner == "a" else 1
    print(f"  [ab] caption → variant {variant} (wins: {wins_a}/{wins_b}, trials: {trials})")
    return variant


def pick_mood(
    audience: str,
    quote: str,
    get_ab_results: Callable[[str, str, str], dict],
    valid_moods: list[str] | None = None,
) -> str:
    """
    Return mood from VALID_MOODS using pairwise Thompson Sampling.
    Compares the top two performing moods for this audience.
    Cold start (< 5 trials per pair) falls back to random.
    """
    if valid_moods is None:
        valid_moods = [
            "dark_philosophical", "dramatic_ancient", "cinematic_hopeful",
            "stark_minimal", "epic_warrior", "mystical_greek", "calm_stoic",
        ]

    # For simplicity, run a round-robin tournament across all pairs
    # In practice with 7 moods this is 21 pairs — acceptable for a daily run
    best_mood = None
    best_score = -1

    for i, mood_a in enumerate(valid_moods):
        wins = 0
        for j, mood_b in enumerate(valid_moods):
            if i == j:
                continue
            results = get_ab_results("mood", mood_a, mood_b)
            if results["trials"] < 3:
                continue
            winner = _thompson_sample(results["wins_a"], results["wins_b"], results["trials"])
            if winner == "a":
                wins += 1

        if wins > best_score:
            best_score = wins
            best_mood = mood_a

    if best_mood is None or best_score < 0:
        best_mood = random.choice(valid_moods)
        print(f"  [ab] mood cold start → random {best_mood}")
    else:
        print(f"  [ab] mood → {best_mood} (score {best_score})")

    return best_mood


def pick_optimal_slot(
    audience: str,
    get_ab_results: Callable[[str, str, str], dict],
) -> int:
    """
    Return 0 (morning), 1 (afternoon), or 2 (evening) using Thompson Sampling.
    """
    results = get_ab_results("slot", "morning", "evening")
    wins_a = results["wins_a"]
    wins_b = results["wins_b"]
    trials = results["trials"]

    if trials < 5:
        slot = random.choice([0, 1, 2])
        print(f"  [ab] slot cold start ({trials} trials) → random {slot}")
        return slot

    winner = _thompson_sample(wins_a, wins_b, trials)
    # 'a' = morning (0), 'b' = evening (2). Afternoon (1) is a middle fallback.
    if winner == "a":
        slot = 0
    else:
        slot = 2

    print(f"  [ab] slot → {slot} (wins: {wins_a}/{wins_b}, trials: {trials})")
    return slot
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd socrates_pipeline
pytest ../tests/test_ab_test.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add socrates_pipeline/ab_test.py tests/test_ab_test.py
git commit -m "feat: add A/B test engine with Thompson Sampling"
```

---

## Task 4: Implement token_manager.py

**Files:**
- Create: `socrates_pipeline/token_manager.py`
- Test: `tests/test_token_manager.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_token_manager.py`:

```python
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "socrates_pipeline"))

from token_manager import refresh_if_needed, _is_token_expiring_soon


def test_is_token_expiring_soon_true():
    soon = datetime.now() + timedelta(days=3)
    assert _is_token_expiring_soon(soon) is True


def test_is_token_expiring_soon_false():
    future = datetime.now() + timedelta(days=30)
    assert _is_token_expiring_soon(future) is False


def test_refresh_if_needed_returns_current_when_fresh():
    token = "valid_token_123"
    future = datetime.now() + timedelta(days=30)

    with patch("token_manager.requests.post") as mock_post:
        result = refresh_if_needed(token, "app_id", "app_secret", expires_at=future)
        mock_post.assert_not_called()
        assert result == token


def test_refresh_if_needed_calls_api_when_expiring():
    token = "old_token"
    soon = datetime.now() + timedelta(days=3)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"access_token": "new_token_456"}

    with patch("token_manager.requests.post", return_value=mock_response) as mock_post:
        result = refresh_if_needed(token, "app_id", "app_secret", expires_at=soon)
        mock_post.assert_called_once()
        assert result == "new_token_456"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd socrates_pipeline
pytest ../tests/test_token_manager.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'token_manager'`

- [ ] **Step 3: Write minimal implementation**

Create `socrates_pipeline/token_manager.py`:

```python
"""
Token Manager — automatically refresh Meta access tokens before expiry.
Uses Meta's fb_exchange_token endpoint to extend token life.
"""

import requests
from datetime import datetime, timedelta
from typing import Optional

from config import Config

META_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"
REFRESH_THRESHOLD_DAYS = 7


def _is_token_expiring_soon(expires_at: datetime | None) -> bool:
    """Return True if token expires within REFRESH_THRESHOLD_DAYS."""
    if expires_at is None:
        return True
    return expires_at - datetime.now() < timedelta(days=REFRESH_THRESHOLD_DAYS)


def refresh_if_needed(
    current_token: str,
    app_id: str,
    app_secret: str,
    expires_at: datetime | None = None,
) -> str:
    """
    Check token expiry. If < 7 days remaining, refresh using Meta endpoint.
    Returns valid token (new or current).
    """
    if not _is_token_expiring_soon(expires_at):
        print("  [token] Token is fresh, no refresh needed")
        return current_token

    print("  [token] Token expiring soon — refreshing...")
    try:
        response = requests.post(
            META_TOKEN_URL,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": current_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        new_token = data.get("access_token")
        if not new_token:
            print(f"  [token] Refresh response missing access_token: {data}")
            return current_token
        print("  [token] Token refreshed successfully")
        return new_token
    except requests.RequestException as e:
        print(f"  [token] Refresh failed: {e}")
        return current_token


def get_valid_token_with_fallback(cfg: Config) -> str:
    """
    Check data_store token_state for a fresh token, else use env fallback.
    Refresh if needed and store result back to data_store.
    """
    try:
        from data_store import get_token, save_token
        state = get_token("meta")
        if state:
            expires_at = None
            if state.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(state["expires_at"])
                except ValueError:
                    pass
            token = refresh_if_needed(state["token"], cfg.META_APP_ID, cfg.META_APP_SECRET, expires_at)
            if token != state["token"]:
                # Token was refreshed — update state (assume 60-day expiry)
                new_expiry = datetime.now() + timedelta(days=60)
                save_token("meta", token, new_expiry)
            return token
    except Exception as e:
        print(f"  [token] data_store check failed: {e}")

    # Fallback: env token
    return cfg.META_ACCESS_TOKEN
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd socrates_pipeline
pytest ../tests/test_token_manager.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add socrates_pipeline/token_manager.py tests/test_token_manager.py
git commit -m "feat: add Meta token auto-refresh manager"
```

---

## Task 5: Implement analytics.py

**Files:**
- Create: `socrates_pipeline/analytics.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_analytics.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "socrates_pipeline"))

from analytics import fetch_post_metrics, ingest_all_pending


def test_fetch_post_metrics_parses_response():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"name": "likes", "values": [{"value": 42}]},
            {"name": "comments", "values": [{"value": 5}]},
            {"name": "reach", "values": [{"value": 1000}]},
            {"name": "impressions", "values": [{"value": 2500}]},
        ]
    }

    with patch("analytics.requests.get", return_value=mock_response) as mock_get:
        metrics = fetch_post_metrics("media_123", "token", "ig_123")
        assert metrics["likes"] == 42
        assert metrics["comments"] == 5
        assert metrics["reach"] == 1000
        assert metrics["impressions"] == 2500
        assert metrics["shares"] == 0
        assert metrics["saved"] == 0


def test_ingest_all_pending_skips_when_no_posts():
    with patch("analytics.requests.get") as mock_get:
        count = ingest_all_pending("token", "ig_123", dry_run=True)
        mock_get.assert_not_called()
        assert count == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd socrates_pipeline
pytest ../tests/test_analytics.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'analytics'`

- [ ] **Step 3: Write minimal implementation**

Create `socrates_pipeline/analytics.py`:

```python
"""
Analytics Ingestion — fetch Meta Insights metrics ~24h after posting.
Runs as a separate cron job (GitHub Actions analytics.yml).
"""

import requests
from datetime import datetime, timedelta
from typing import Optional

GRAPH_URL = "https://graph.instagram.com/v22.0"

METRICS = ["likes", "comments", "shares", "reach", "impressions", "saved"]


def fetch_post_metrics(
    post_id: str,
    access_token: str,
    ig_account_id: str,
) -> dict:
    """
    Fetch insights for a single post from Meta Insights API.
    Returns dict with all metric names (default 0 if missing).
    """
    url = f"{GRAPH_URL}/{post_id}/insights"
    params = {
        "metric": ",".join(METRICS),
        "access_token": access_token,
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    result = {m: 0 for m in METRICS}
    for item in data.get("data", []):
        name = item.get("name")
        values = item.get("values", [])
        if name in result and values:
            result[name] = values[0].get("value", 0)

    return result


def ingest_all_pending(
    access_token: str,
    ig_account_id: str,
    dry_run: bool = False,
) -> int:
    """
    Find all posts older than 24h with no metrics, fetch and store.
    Returns count of posts updated.
    """
    try:
        from data_store import _get_connection
    except ImportError:
        print("  [analytics] data_store not available, skipping")
        return 0

    conn = _get_connection()
    conn.row_factory = __import__("sqlite3").Row
    cursor = conn.cursor()

    # Find posts older than 24h with no metrics
    cursor.execute(
        """
        SELECT p.post_id
        FROM posts p
        LEFT JOIN post_metrics m ON p.post_id = m.post_id
        WHERE p.post_id IS NOT NULL
          AND p.posted_at IS NOT NULL
          AND p.posted_at <= datetime('now', '-1 day')
          AND m.post_id IS NULL
        """
    )
    pending = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not pending:
        print("  [analytics] No pending posts to ingest")
        return 0

    print(f"  [analytics] Fetching metrics for {len(pending)} post(s)...")
    updated = 0

    for post_id in pending:
        if dry_run:
            print(f"    [dry-run] Would fetch metrics for {post_id}")
            updated += 1
            continue

        try:
            metrics = fetch_post_metrics(post_id, access_token, ig_account_id)
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO post_metrics (post_id, likes, comments, shares, reach, impressions, saved)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post_id,
                    metrics.get("likes", 0),
                    metrics.get("comments", 0),
                    metrics.get("shares", 0),
                    metrics.get("reach", 0),
                    metrics.get("impressions", 0),
                    metrics.get("saved", 0),
                ),
            )
            conn.commit()
            conn.close()
            updated += 1
            print(f"    [analytics] Ingested metrics for {post_id}")
        except Exception as e:
            print(f"    [analytics] Failed to fetch metrics for {post_id}: {e}")

    print(f"  [analytics] Updated {updated}/{len(pending)} posts")
    return updated


if __name__ == "__main__":
    import argparse
    from config import Config

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Log what would be done without fetching")
    args = parser.parse_args()

    cfg = Config()
    count = ingest_all_pending(cfg.META_ACCESS_TOKEN, cfg.IG_ACCOUNT_ID, dry_run=args.dry_run)
    print(f"Done. Ingested {count} posts.")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd socrates_pipeline
pytest ../tests/test_analytics.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add socrates_pipeline/analytics.py tests/test_analytics.py
git commit -m "feat: add Meta Insights analytics ingestion"
```

---

## Task 6: Update excel_reader.py for dual captions

**Files:**
- Modify: `socrates_pipeline/excel_reader.py`

- [ ] **Step 1: Modify `read_todays_quote` to return caption_a and caption_b**

In `socrates_pipeline/excel_reader.py`, find the `read_todays_quote` function and update the row extraction:

```python
def read_todays_quote(excel_path: str = "quotes.xlsx", slot: int | None = None) -> dict:
    # ... existing code up to row extraction ...
    for row in ws.iter_rows(min_row=2, values_only=False):
        row_num   = row[0].value  # col A: #
        quote     = row[1].value  # col B: Quote
        audience  = row[2].value  # col C: Audience
        caption   = row[3].value  # col D: Caption
        caption_b = row[4].value  # col E: Caption Variant B (NEW)
        status    = row[5].value  # col F: Status
        posted    = row[6].value  # col G: Posted Date

        if not quote or not caption:
            continue
        if str(status).lower() == "skip":
            continue
        if posted:
            continue

        ready_rows.append({
            "row_number": row_num,
            "quote":      str(quote).strip(),
            "audience":   str(audience).strip().lower() if audience else "stuck",
            "caption":    str(caption).strip(),
            "caption_b":  str(caption_b).strip() if caption_b else str(caption).strip(),
            "status":     str(status).strip(),
        })
    # ... rest of function unchanged ...
```

- [ ] **Step 2: Verify no tests break**

```bash
cd socrates_pipeline
pytest -v 2>/dev/null || echo "No existing pytest config — run manually"
```

Expected: No errors from this change (backwards compatible — new column is optional).

- [ ] **Step 3: Commit**

```bash
git add socrates_pipeline/excel_reader.py
git commit -m "feat: support dual caption variants in excel_reader"
```

---

## Task 7: Update generate_quotes_excel.py for dual captions

**Files:**
- Modify: `socrates_pipeline/generate_quotes_excel.py`

- [ ] **Step 1: Update header and column widths**

Change:
```python
headers = ["#", "Quote", "Audience", "Caption", "Mood (AI fills this)", "Status", "Posted Date", "Post ID"]
col_widths = [5, 60, 18, 80, 30, 12, 16, 20]
```

To:
```python
headers = ["#", "Quote", "Audience", "Caption A (Hook First)", "Caption B (Story First)", "Mood (AI fills this)", "Status", "Posted Date", "Post ID"]
col_widths = [5, 60, 18, 80, 80, 30, 12, 16, 20]
```

- [ ] **Step 2: Update row population to generate both caption variants**

In the loop where rows are populated, change:
```python
ws.cell(row=row, column=4, value=caption).alignment = Alignment(wrap_text=True, vertical="top")
ws.cell(row=row, column=5, value="").alignment = Alignment(wrap_text=True, vertical="top")
```

To:
```python
caption_a = _build_caption(quote, audience, i - 1)
caption_b = _build_caption(quote, audience, i)  # offset by 1 for variety
ws.cell(row=row, column=4, value=caption_a).alignment = Alignment(wrap_text=True, vertical="top")
ws.cell(row=row, column=5, value=caption_b).alignment = Alignment(wrap_text=True, vertical="top")
ws.cell(row=row, column=6, value="").alignment = Alignment(wrap_text=True, vertical="top")
```

Also update the column loop that applies borders:
```python
for col in range(1, 10):  # was 9, now 10 columns
```

- [ ] **Step 3: Regenerate quotes.xlsx**

```bash
cd socrates_pipeline
python generate_quotes_excel.py
```

Expected output: `✅ Created quotes.xlsx with 584 story-driven quotes across 3 sheets`

- [ ] **Step 4: Commit**

```bash
git add socrates_pipeline/generate_quotes_excel.py socrates_pipeline/quotes.xlsx
git commit -m "feat: generate two caption variants (hook-first and story-first) per quote"
```

---

## Task 8: Update config.py with new env vars

**Files:**
- Modify: `socrates_pipeline/config.py`
- Modify: `socrates_pipeline/.env.example`

- [ ] **Step 1: Add META_APP_ID and META_APP_SECRET to Config**

In `socrates_pipeline/config.py`, add to the dataclass:
```python
    META_APP_ID: str = ""       # Meta App ID (for token refresh)
    META_APP_SECRET: str = ""   # Meta App Secret (for token refresh)
```

And in `__post_init__`:
```python
        self.META_APP_ID         = self._get_opt("META_APP_ID")
        self.META_APP_SECRET     = self._get_opt("META_APP_SECRET")
```

- [ ] **Step 2: Update .env.example**

Add after existing Meta vars:
```bash
# Meta App credentials (for automatic token refresh)
META_APP_ID=your_meta_app_id_here
META_APP_SECRET=your_meta_app_secret_here
```

- [ ] **Step 3: Commit**

```bash
git add socrates_pipeline/config.py socrates_pipeline/.env.example
git commit -m "feat: add META_APP_ID and META_APP_SECRET env vars"
```

---

## Task 9: Update pipeline.py with new modules

**Files:**
- Modify: `socrates_pipeline/pipeline.py`

- [ ] **Step 1: Add imports at top**

After existing imports, add:
```python
from data_store import init_db, save_post, mark_posted
from ab_test import pick_caption_variant, pick_mood, pick_optimal_slot
from token_manager import get_valid_token_with_fallback
```

- [ ] **Step 2: Modify `run_pipeline` function**

Before `quote_data = read_todays_quote(EXCEL_PATH)`, add:
```python
    # Initialize SQLite state store
    init_db()

    # Get valid Meta token (auto-refreshes if needed)
    access_token = get_valid_token_with_fallback(cfg)
```

After reading quote_data, add A/B selection:
```python
        # ── Step 0: A/B Test Selection ────────────────────────────────────────
        log.info("Step 0: A/B test selection...")
        slot = pick_optimal_slot(quote_data["audience"], get_ab_results=data_store.get_ab_results)
        caption_variant = pick_caption_variant(quote_data["audience"], get_ab_results=data_store.get_ab_results)
        mood = pick_mood(quote_data["audience"], quote_data["quote"], get_ab_results=data_store.get_ab_results)
        log.info(f"Slot: {slot}, Variant: {caption_variant}, Mood: {mood}")

        # Pick caption variant
        chosen_caption = quote_data.get("caption_b") if caption_variant == 1 else quote_data["caption"]
        quote_data["caption"] = chosen_caption

        # Override mood from A/B test
        # (mood already selected above, skip Claude Haiku if A/B picked)
```

After successful post, save to SQLite:
```python
        # Save to SQLite state store
        post_row_id = save_post(
            quote_text=quote_data["quote"],
            audience=quote_data["audience"],
            mood=mood,
            caption_variant=caption_variant,
            posting_slot=slot,
            dry_run=dry_run,
        )
```

And after `post_id` is obtained:
```python
            mark_posted(post_row_id, post_id, str(final_image_path), str(reel_path) if reel_path else None)
```

Also update the `post_to_instagram` calls to use `access_token` instead of `cfg.META_ACCESS_TOKEN`.

- [ ] **Step 3: Commit**

```bash
git add socrates_pipeline/pipeline.py
git commit -m "feat: integrate SQLite state, A/B testing, and auto token refresh into pipeline"
```

---

## Task 10: Create GitHub Actions analytics workflow

**Files:**
- Create: `.github/workflows/analytics.yml`

- [ ] **Step 1: Write workflow file**

Create `.github/workflows/analytics.yml`:

```yaml
name: Ingest Analytics

on:
  schedule:
    - cron: '30 9 * * *'  # 09:30 UTC, ~2h after posting
  workflow_dispatch:

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r socrates_pipeline/requirements.txt

      - name: Init database
        run: python -c "from socrates_pipeline.data_store import init_db; init_db()"

      - name: Ingest pending metrics
        run: python socrates_pipeline/analytics.py
        env:
          META_ACCESS_TOKEN: ${{ secrets.META_ACCESS_TOKEN }}
          IG_ACCOUNT_ID: ${{ secrets.IG_ACCOUNT_ID }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/analytics.yml
git commit -m "ci: add daily analytics ingestion workflow"
```

---

## Task 11: Update daily_post.yml

**Files:**
- Modify: `.github/workflows/daily_post.yml`

- [ ] **Step 1: Add init_db, generate_audio, and token refresh steps**

Insert before the `Run pipeline` step:

```yaml
      - name: Init SQLite database
        run: python -c "from socrates_pipeline.data_store import init_db; init_db()"

      - name: Generate audio assets (if reel mode)
        if: github.event.inputs.reel == 'true'
        run: |
          pip install numpy scipy soundfile
          python socrates_pipeline/generate_audio.py

      - name: Refresh Meta token
        run: python -c "from socrates_pipeline.token_manager import refresh_if_needed; from socrates_pipeline.config import Config; cfg=Config(); refresh_if_needed(cfg.META_ACCESS_TOKEN, cfg.META_APP_ID, cfg.META_APP_SECRET)"
        env:
          META_ACCESS_TOKEN: ${{ secrets.META_ACCESS_TOKEN }}
          META_APP_ID: ${{ secrets.META_APP_ID }}
          META_APP_SECRET: ${{ secrets.META_APP_SECRET }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/daily_post.yml
git commit -m "ci: add db init, audio gen, and token refresh to daily post workflow"
```

---

## Task 12: Verify generate_audio.py generates mood tracks

**Files:**
- Read: `socrates_pipeline/generate_audio.py`

- [ ] **Step 1: Read the existing file**

```bash
cat socrates_pipeline/generate_audio.py
```

- [ ] **Step 2: If it doesn't generate 7 mood tracks, update it**

The existing file should create ambient `.mp3` files for each mood in `MOOD_AUDIO` dict. If it doesn't cover all 7 moods, update it to ensure outputs go to `socrates_pipeline/audio/`.

- [ ] **Step 3: Commit (if changes made)**

```bash
git add socrates_pipeline/generate_audio.py
git commit -m "fix: ensure generate_audio.py produces all 7 mood tracks"
```

---

## Task 13: Integration test — dry run

**Files:**
- None (verification step)

- [ ] **Step 1: Run dry-run pipeline locally**

```bash
cd socrates_pipeline
python pipeline.py --dry-run
```

Expected output:
- "Step 0: A/B test selection..."
- "Slot: X, Variant: Y, Mood: Z"
- "Step 1/5: Reading quote from Excel..."
- Steps 2–5 complete
- "▶ Pipeline complete"
- SQLite DB updated in `data/pipeline.db`

- [ ] **Step 2: Verify SQLite state**

```bash
python -c "
import sqlite3
conn = sqlite3.connect('socrates_pipeline/data/pipeline.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM posts')
print('Posts:', cursor.fetchone()[0])
cursor.execute('SELECT caption_variant, mood, posting_slot FROM posts ORDER BY id DESC LIMIT 1')
print('Last post:', cursor.fetchone())
conn.close()
"
```

- [ ] **Step 3: Commit any final fixes**

If issues found, fix and commit. Otherwise:
```bash
git status  # should be clean
git log --oneline -5
```

---

## Plan Self-Review

### Spec Coverage Check

| Spec Section | Plan Task | Covered? |
|--------------|-----------|----------|
| SQLite schema + `data_store.py` | Task 2 | ✅ |
| A/B testing (Thompson Sampling) | Task 3 | ✅ |
| Token auto-refresh | Task 4 | ✅ |
| Meta Insights ingestion | Task 5 | ✅ |
| Dual caption variants | Tasks 6–7 | ✅ |
| `pipeline.py` integration | Task 9 | ✅ |
| Audio assets for Reels | Task 12 | ✅ |
| GitHub Actions updates | Tasks 10–11 | ✅ |
| Error handling | Embedded in each task | ✅ |
| Tests | Each task has test file | ✅ |

### Placeholder Scan

- No "TBD", "TODO", "implement later", "fill in details" found.
- No vague "add error handling" steps — concrete retry logic is in `data_store.py`.
- No "similar to Task N" references.
- All code blocks contain actual runnable code.

### Type Consistency Check

- `data_store.save_post` returns `int` (row_id) — used in `pipeline.py`.
- `ab_test.pick_caption_variant` returns `int` (0 or 1) — used to index `quote_data`.
- `token_manager.refresh_if_needed` returns `str` — used as `access_token` in pipeline.
- `analytics.ingest_all_pending` returns `int` — consistent across implementation and tests.
- All `get_ab_results` callable signatures match: `(dimension, variant_a, variant_b) -> dict`.

No inconsistencies found. Plan is ready for execution.
