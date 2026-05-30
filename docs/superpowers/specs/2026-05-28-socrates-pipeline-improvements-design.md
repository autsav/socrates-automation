# Socrates Pipeline Improvements — Design Spec

**Date:** 2026-05-28
**Scope:** Hybrid Foundation Fix (Option A) + Data-Driven Feedback Loop (Option C)
**Out of Scope:** Multi-platform expansion (Twitter/Pinterest — Phase 2)

---

## 1. Problem Statement

The Socrates Instagram Automation Pipeline is functional and cost-efficient (~£0.17/month), but has four categories of gaps:

| Category | Issue | Impact |
|----------|-------|--------|
| **Engagement** | No data on what captions, moods, or posting times perform best | Missed compounding growth from optimisation |
| **Reliability** | Excel file used as read-write state store; risk of corruption on concurrent runs | Hard failure or duplicate posts |
| **Maintenance** | Meta access token expires every 60 days; manual refresh required | Pipeline silently fails after 2 months |
| **Cost/Quality** | Reels generate as silent videos because audio assets are missing | Lower engagement on Reel format |

This spec addresses all four categories within the existing single-platform scope.

---

## 2. Goals

1. Replace Excel write-back with SQLite state tracking.
2. Automate Meta token refresh before expiry.
3. Add A/B testing framework for captions, image moods, and posting slots.
4. Ingest Meta Insights data to close the feedback loop.
5. Add mood-matched audio assets so Reels have ambient sound.
6. Keep monthly cost under £0.50.
7. Preserve all existing module interfaces (backwards compatible).

---

## 3. Architecture

### 3.1 High-Level Flow

```
GitHub Actions (7:30 UTC)
    │
    ▼
┌─────────────────────────────────────┐
│ A/B Test Engine                   │ ← SQLite: post_metrics + ab_results
│ (ab_test.py)                      │
└─────────────────────────────────────┘
    │
    ▼
Existing pipeline.py Steps 1–5
(excel_reader.py → image_generator.py → image_composer.py → instagram_poster.py)
    │
    ▼
┌─────────────────────────────────────┐
│ State Store                       │ ← SQLite: posts
│ (data_store.py)                     │
└─────────────────────────────────────┘
    │
    ▼
Telegram notification (unchanged)

GitHub Actions (24h later, cron)
    │
    ▼
┌─────────────────────────────────────┐
│ Analytics Ingestion               │ ← Meta Insights API
│ (analytics.py)                      │
└─────────────────────────────────────┘
    │
    ▼
SQLite: post_metrics updated
```

### 3.2 New Modules

| Module | File | Responsibility |
|--------|------|--------------|
| State Store | `data_store.py` | SQLite CRUD for posts, metrics, A/B results |
| Analytics | `analytics.py` | Fetch Meta Insights; populate `post_metrics` |
| A/B Test | `ab_test.py` | Select caption variant, mood, slot based on rolling 30-day data |
| Token Manager | `token_manager.py` | Refresh Meta token before expiry; store in `.env` |

### 3.3 Database Schema

**File:** `data/pipeline.db` (SQLite, committed to repo is fine — no secrets)

```sql
-- Tracks every post attempt
CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_text TEXT NOT NULL,
    audience TEXT NOT NULL,
    mood TEXT NOT NULL,
    caption_variant INTEGER DEFAULT 0,   -- 0 = hook-first, 1 = story-first
    posting_slot INTEGER DEFAULT 0,      -- 0 = morning, 1 = afternoon, 2 = evening
    posted_at TIMESTAMP,
    post_id TEXT UNIQUE,
    image_path TEXT,
    reel_path TEXT,
    dry_run BOOLEAN DEFAULT FALSE
);

-- Fetched ~24h after posting via Meta Insights API
CREATE TABLE post_metrics (
    post_id TEXT PRIMARY KEY,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    saved INTEGER DEFAULT 0,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(post_id)
);

-- Tracks A/B test results for compounding optimisation
CREATE TABLE ab_results (
    dimension TEXT NOT NULL,          -- 'caption', 'mood', 'slot'
    variant_a TEXT NOT NULL,
    variant_b TEXT NOT NULL,
    wins_a INTEGER DEFAULT 0,
    wins_b INTEGER DEFAULT 0,
    trials INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (dimension, variant_a, variant_b)
);

-- Token expiry tracking
CREATE TABLE token_state (
    service TEXT PRIMARY KEY,
    token TEXT NOT NULL,
    expires_at TIMESTAMP,
    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. Component Design

### 4.1 `data_store.py`

**Interface:**

```python
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "pipeline.db"

def init_db() -> None:
    """Create tables if they don't exist. Called once at pipeline start."""

def save_post(
    quote_text: str,
    audience: str,
    mood: str,
    caption_variant: int,
    posting_slot: int,
    dry_run: bool = False,
) -> int:
    """Insert a new post record. Returns post row id."""

def mark_posted(row_id: int, post_id: str, image_path: str, reel_path: Optional[str] = None) -> None:
    """Update post with actual post_id and paths after successful publish."""

def get_ab_results(dimension: str, variant_a: str, variant_b: str) -> dict:
    """Return wins_a, wins_b, trials for a dimension pair."""

def record_ab_win(dimension: str, variant_a: str, variant_b: str, winner: str) -> None:
    """Increment wins for the winning variant."""

def get_last_posted_for_audience(audience: str, days: int = 30) -> list[dict]:
    """Return recent posts for an audience with metrics joined."""
```

**Concurrency strategy:** SQLite WAL mode (`PRAGMA journal_mode=WAL`) allows readers during writes. Writes are short (< 10 ms). On `OperationalError: database is locked`, retry 3 times with exponential backoff + jitter.

### 4.2 `analytics.py`

**Interface:**

```python
def fetch_post_metrics(
    post_id: str,
    access_token: str,
    ig_account_id: str,
) -> dict:
    """
    Fetch insights for a single post from Meta Insights API.
    Returns: {likes, comments, shares, reach, impressions, saved}
    """

def ingest_all_pending(access_token: str, ig_account_id: str) -> int:
    """
    Find all posts older than 24h with no metrics, fetch and store.
    Returns count of posts updated.
    """
```

**Meta Insights endpoint:**
```
GET https://graph.instagram.com/{media-id}/insights
    ?metric=likes,comments,shares,reach,impressions,saved
    &access_token={token}
```

**Schedule:** Separate GitHub Actions workflow `analytics.yml` runs daily at 09:30 UTC (2 hours after posting job).

### 4.3 `ab_test.py`

**Algorithm:** Thompson Sampling (Beta-Bernoulli bandit).

For each dimension (caption, mood, slot):
1. Query `ab_results` for wins_a, wins_b, trials.
2. Sample from Beta(wins_a + 1, trials - wins_a + 1) for variant A.
3. Sample from Beta(wins_b + 1, trials - wins_b + 1) for variant B.
4. Pick the variant with higher sample.
5. If trials < 5 (cold start), fall back to random selection + log "exploration mode".

**Interface:**

```python
from typing import Literal

def pick_caption_variant(audience: str) -> Literal[0, 1]:
    """
    Return 0 (hook-first) or 1 (story-first) based on 30-day rolling data.
    """

def pick_mood(audience: str, quote: str) -> str:
    """
    Return mood from VALID_MOODS, weighted by past reach for this audience.
    """

def pick_optimal_slot(audience: str) -> Literal[0, 1, 2]:
    """
    Return 0 (morning), 1 (afternoon), or 2 (evening) based on engagement by slot.
    """
```

**Caption variant generation:** `generate_quotes_excel.py` will produce two caption columns (`caption_a`, `caption_b`) where `caption_a` = hook-first and `caption_b` = story-first. The pipeline picks one at runtime.

### 4.4 `token_manager.py`

**Interface:**

```python
def refresh_if_needed(
    current_token: str,
    app_id: str,
    app_secret: str,
    db_path: Optional[Path] = None,
) -> str:
    """
    Check token expiry in token_state. If < 7 days remaining, refresh using
    Meta's fb_exchange_token endpoint. Return valid token.
    """

def get_valid_token(env_fallback: str = "") -> str:
    """
    Return token from token_state if fresh, else env_fallback.
    """
```

**Token refresh flow:**
```
POST https://graph.facebook.com/oauth/access_token
    ?grant_type=fb_exchange_token
    &client_id={APP_ID}
    &client_secret={APP_SECRET}
    &fb_exchange_token={SHORT_OR_CURRENT_TOKEN}
```

**Required new env vars:**
- `META_APP_ID` — Meta App ID
- `META_APP_SECRET` — Meta App Secret

### 4.5 `reel_composer.py` — Audio Assets Fix

**Current gap:** `audio/` directory does not exist in repo. `reel_composer.py` falls back to silent video.

**Fix:**
1. Add `audio/` directory with 7 ambient `.mp3` files (5 seconds each, royalty-free or generated).
2. `generate_audio.py` already exists — verify it generates the 7 mood tracks.
3. Update `.gitignore` to ignore large audio binaries if needed; alternatively generate them in CI via `python generate_audio.py` (requires ffmpeg + numpy/scipy/soundfile already in requirements).

**Decision:** Generate audio assets in CI via `python generate_audio.py` before Reel creation. No need to commit large MP3s.

---

## 5. Integration Points

### 5.1 `pipeline.py` Changes

**Before:**
```python
quote_data = read_todays_quote(EXCEL_PATH)
```

**After:**
```python
# Initialise SQLite
data_store.init_db()

# A/B selection
slot = ab_test.pick_optimal_slot(quote_data["audience"])
quote_data = read_todays_quote(EXCEL_PATH, slot=slot)
caption_variant = ab_test.pick_caption_variant(quote_data["audience"])
quote_data["caption"] = quote_data[f"caption_{caption_variant}"]
mood = ab_test.pick_mood(quote_data["audience"], quote_data["quote"])

# Save record early
post_row_id = data_store.save_post(...)

# ... existing steps ...

# After successful post
data_store.mark_posted(post_row_id, post_id, final_image_path, reel_path)
```

**Backwards compatibility:** `read_todays_quote()` signature accepts optional `slot` parameter. Default behaviour unchanged.

### 5.2 GitHub Actions

**New workflow:** `.github/workflows/analytics.yml`

```yaml
name: Ingest Analytics
on:
  schedule:
    - cron: '30 9 * * *'  # 09:30 UTC, 2h after post
  workflow_dispatch:

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python analytics.py
        env:
          META_ACCESS_TOKEN: ${{ secrets.META_ACCESS_TOKEN }}
          IG_ACCOUNT_ID: ${{ secrets.IG_ACCOUNT_ID }}
```

**Updated `daily_post.yml`:**
- Add `python -c "from data_store import init_db; init_db()"` before pipeline run.
- Add `python generate_audio.py` before Reel generation (if `--reel` flag).
- Add `META_APP_ID` and `META_APP_SECRET` to secrets.

---

## 6. Error Handling

| Scenario | Strategy |
|----------|----------|
| SQLite locked | Retry 3x with exponential backoff + random jitter (0–200 ms) |
| Meta Insights API rate limited (4xx) | Skip ingestion, log warning, retry next day |
| Token refresh fails (invalid App Secret) | Pipeline still runs with current token; Telegram alert with error |
| A/B cold start (< 5 trials) | Random selection, log "exploration mode", no metrics dependency |
| `ffmpeg` missing | Skip Reel generation, still post image, log info |
| Analytics fetch returns empty metrics | Store zeros, log warning, do not crash |
| `caption_a` / `caption_b` missing in old Excel | Fall back to single `caption` column for backwards compatibility |

---

## 7. Testing

### 7.1 Unit Tests

| Module | Test | Mock Target |
|--------|------|-------------|
| `data_store.py` | CRUD roundtrip | `sqlite3` in-memory DB |
| `data_store.py` | Concurrent write retry | Threading + temporary lock simulation |
| `analytics.py` | Fetch and parse Insights JSON | `requests.get` |
| `analytics.py` | Graceful empty response | `requests.get` returning `{}` |
| `ab_test.py` | Cold start randomises | `random.random` |
| `ab_test.py` | Thompson sampling picks winner with high probability | Pre-seeded `ab_results` |
| `token_manager.py` | Refresh only when needed | `requests.post` + `token_state` query |
| `token_manager.py` | No refresh when token fresh | `token_state` with future expiry |

### 7.2 Integration Tests

- `python pipeline.py --dry-run` completes end-to-end with SQLite state.
- `python analytics.py --dry-run` parses mock data without network.
- Backfill script `scripts/backtest_ab.py` replays past posts to validate no bias toward early winners.

---

## 8. Cost Impact

| Service | Before | After | Change |
|---------|--------|-------|--------|
| Claude Haiku (mood) | ~£0.10/mo | ~£0.10/mo | — |
| Fal.ai FLUX | ~£0.07/mo | ~£0.07/mo | — |
| Meta Insights API | £0 | £0 | Free |
| GitHub Actions | £0 | £0 | Free |
| SQLite | £0 | £0 | Local file |
| **Total** | **~£0.17/mo** | **~£0.17/mo** | **No change** |

Target met: monthly cost stays under £0.50.

---

## 9. Rollout Plan

| Step | Action | Risk |
|------|--------|------|
| 1 | Add SQLite schema + `data_store.py` | Low — parallel to existing Excel write-back |
| 2 | Migrate `mark_as_posted()` from Excel to SQLite | Low — keep Excel backup column temporarily |
| 3 | Add `token_manager.py` + env vars | Low — falls back to env token if DB empty |
| 4 | Add `ab_test.py` with cold-start fallback | Low — random selection until data exists |
| 5 | Generate audio assets + fix Reel audio | Low — already have `generate_audio.py` |
| 6 | Add `analytics.py` + GitHub Actions cron | Low — separate workflow, never blocks posting |
| 7 | Remove Excel write-back after 1 week validation | Low — confirm SQLite state matches Excel |
| 8 | Add caption variant columns to `quotes.xlsx` generation | Medium — requires regenerating the Excel file |

---

## 10. Out of Scope (Phase 2)

- Twitter/X cross-posting
- Pinterest pinning
- Web dashboard for analytics review
- Follower growth prediction model
- Comment auto-reply via Claude

---

## 11. Success Criteria

- [ ] Pipeline runs for 30 days without manual token refresh.
- [ ] SQLite state contains every post with accurate post IDs.
- [ ] `analytics.py` successfully ingests metrics for > 90% of posts within 48h.
- [ ] A/B test data shows non-random preferences emerging after 20+ trials per dimension.
- [ ] Reels include ambient audio when `--reel` flag is used.
- [ ] Monthly operational cost remains < £0.50.
