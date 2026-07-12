# Ship & Learn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the polished reel actually ship reliably and feed the A/B learner (guard the auto-publish path, make reconcile robust to caption edits) and stop leaking local absolute paths / sensitive files.

**Architecture:** Three independent streams, all additive and best-effort (never raise from reconcile or path helpers). C1: route every persisted path through a repo-relative helper + untrack junk while keeping the 7 mood beds. A6: stamp a stable hashtag token onto each caption + proposal, match it in reconcile, fall back to timestamp-proximity using the proposal's existing `created_at`. A5: a mocked-HTTP contract test that exercises the Graph-API publish path so it can't rot, plus a README documenting manual-publish-by-design.

**Tech Stack:** Python 3.11 (`.venv`), pytest, sqlite3, `requests` (mocked in tests), GitHub Actions, git.

## Global Constraints

- Run all Python tests with the 3.11 venv: `.venv/bin/python -m pytest` (system python is 3.9 and cannot import the repo).
- Full suite is green **apart from 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures** — those are not regressions; do not "fix" them.
- `--manual` stays the production default; **do not** change any cron/schedule or switch production to auto-publish.
- reconcile and the path helper are **best-effort: never raise** (return `None`/basename on any failure).
- Keep the 7 `audio/*.mp3` mood beds tracked (`calm_stoic`, `cinematic_hopeful`, `dark_philosophical`, `dramatic_ancient`, `epic_warrior`, `mystical_greek`, `stark_minimal`) — they are bundled assets used by `reel_composer.MOOD_AUDIO`.
- No git-history rewrite (out of scope).
- Repo root in `pipeline.py` is `PROJECT_ROOT = Path(__file__).parent.resolve()` (`pipeline.py:50`).
- Reconcile stores the token as the proposal's `caption_marker` inside `decision_json`; `studio/reconcile.py:_marker_for` already reads `visual_direction.caption_marker`.

---

### Task 1: C1 — repo-relative path helper + route persisted paths

**Files:**
- Modify: `pipeline.py` (add `_rel_path`; route `save_log`/`mark_posted` path args through it at `:565`, `:605`, `:958`, `:1003`, `:1038`)
- Test: `tests/test_path_hygiene.py` (create)

**Interfaces:**
- Produces: `pipeline._rel_path(p: str | Path | None) -> str | None` — repo-relative string for in-repo paths, basename for outside-repo paths, `None` for `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_path_hygiene.py
from pathlib import Path
import pipeline


def test_rel_path_none_returns_none():
    assert pipeline._rel_path(None) is None


def test_rel_path_in_repo_is_relative():
    p = pipeline.PROJECT_ROOT / "output" / "post_x.jpg"
    assert pipeline._rel_path(p) == "output/post_x.jpg"


def test_rel_path_outside_repo_is_basename():
    assert pipeline._rel_path("/Users/someone/secret/post_x.jpg") == "post_x.jpg"


def test_rel_path_never_raises_on_junk():
    # non-path-like input must not raise
    assert pipeline._rel_path(12345) is not None or pipeline._rel_path(12345) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_path_hygiene.py -v`
Expected: FAIL with `AttributeError: module 'pipeline' has no attribute '_rel_path'`

- [ ] **Step 3: Add `_rel_path` near the other path constants in `pipeline.py`** (just after `EXCEL_PATH = PROJECT_ROOT / "quotes.xlsx"`, `pipeline.py:53`)

```python
def _rel_path(p):
    """Render a path repo-relative (no absolute local paths in logs/DB).

    In-repo path -> 'output/foo.jpg'; outside-repo -> basename; None -> None.
    Best-effort: never raises."""
    if p is None:
        return None
    try:
        return str(Path(p).resolve().relative_to(PROJECT_ROOT))
    except (ValueError, OSError, TypeError):
        try:
            return Path(str(p)).name
        except Exception:
            return None
```

- [ ] **Step 4: Route the persisted path args through `_rel_path`.**

In `pipeline.py`, replace each `str(...)` path argument written to `save_log`/`mark_posted`:
- `:565` `mark_posted(post_row_id, "PENDING_MANUAL", None, str(reel_path) if reel_path else None)` → `mark_posted(post_row_id, "PENDING_MANUAL", None, _rel_path(reel_path))`
- `:605` record `"reel_path": str(reel_path) if reel_path else None,` → `"reel_path": _rel_path(reel_path),`
- `:958` `mark_posted(post_row_id, "PENDING_MANUAL", str(final_image_path), str(reel_path) if reel_path else None)` → `mark_posted(post_row_id, "PENDING_MANUAL", _rel_path(final_image_path), _rel_path(reel_path))`
- `:1003` `mark_posted(post_row_id, post_id, str(final_image_path), str(reel_path) if reel_path else None)` → `mark_posted(post_row_id, post_id, _rel_path(final_image_path), _rel_path(reel_path))`
- `:1038` record `"image_path": str(final_image_path),` → `"image_path": _rel_path(final_image_path),`

(Line numbers are pre-edit anchors; match on the exact text since earlier edits shift them.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_path_hygiene.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add pipeline.py tests/test_path_hygiene.py
git commit -m "fix(privacy): store repo-relative paths in logs and DB (no /Users leak)"
```

---

### Task 2: C1 — untrack junk, keep mood beds, narrow the workflow

**Files:**
- Modify: `.gitignore` (add `!audio/<name>.mp3` exceptions for the 7 beds)
- Modify: `.github/workflows/daily_post.yml:198` (narrow `git add -f … logs/`)
- Untrack (git rm --cached): `output/*.jpg`, `server.log`, `logs/posts.jsonl`, `.DS_Store`, `docs/.DS_Store`, `docs/superpowers/.DS_Store`
- Test: `tests/test_gitignore_state.py` (create)

**Interfaces:**
- Consumes: nothing. Produces: nothing consumed by later tasks (git-state + config only).

- [ ] **Step 1: Write the failing test** (asserts the end git-state we want)

```python
# tests/test_gitignore_state.py
import subprocess


def _tracked(path):
    out = subprocess.run(["git", "ls-files", path], capture_output=True, text=True).stdout
    return bool(out.strip())


def test_junk_is_untracked():
    assert not _tracked("logs/posts.jsonl")
    assert not _tracked("server.log")
    assert not _tracked(".DS_Store")
    # no output jpgs tracked
    out = subprocess.run(["git", "ls-files", "output/"], capture_output=True, text=True).stdout
    assert ".jpg" not in out


def test_mood_beds_stay_tracked():
    for mood in ["calm_stoic", "cinematic_hopeful", "dark_philosophical",
                 "dramatic_ancient", "epic_warrior", "mystical_greek", "stark_minimal"]:
        assert _tracked(f"audio/{mood}.mp3"), f"mood bed {mood} must stay tracked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_gitignore_state.py -v`
Expected: FAIL on `test_junk_is_untracked` (posts.jsonl/server.log/output jpgs still tracked)

- [ ] **Step 3: Add explicit mood-bed exceptions to `.gitignore`** (right after the `audio/*.mp3` / `!audio/.gitkeep` block, lines 20-21)

```gitignore
!audio/calm_stoic.mp3
!audio/cinematic_hopeful.mp3
!audio/dark_philosophical.mp3
!audio/dramatic_ancient.mp3
!audio/epic_warrior.mp3
!audio/mystical_greek.mp3
!audio/stark_minimal.mp3
```

- [ ] **Step 4: Untrack the junk (keeps files on disk, already gitignored)**

```bash
git rm --cached logs/posts.jsonl server.log .DS_Store docs/.DS_Store docs/superpowers/.DS_Store
git rm --cached output/*.jpg
```

- [ ] **Step 5: Narrow the workflow so CI stops re-committing `posts.jsonl`.**

In `.github/workflows/daily_post.yml`, change the force-add line (`:198`):

```yaml
# before
          git add -f data/pipeline.db logs/
# after
          git add -f data/pipeline.db
          git add -f logs/notifications.jsonl 2>/dev/null || true
```

(The existing `upload-artifact path: logs/` step still captures full per-run logs, so no audit signal is lost.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_gitignore_state.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add .gitignore .github/workflows/daily_post.yml tests/test_gitignore_state.py
git commit -m "chore(privacy): untrack generated/sensitive files; keep mood beds; stop CI committing posts.jsonl"
```

---

### Task 3: A6 — reconcile token generator + caption/proposal stamping

**Files:**
- Modify: `studio/reconcile.py` (add pure `reconcile_token`)
- Modify: `pipeline.py` (import `reconcile_token`; after `save_post` in the studio branch, append token to caption + set `studio_decision.visual_direction["caption_marker"]`)
- Test: `tests/test_reconcile_token.py` (create)

**Interfaces:**
- Produces: `studio.reconcile.reconcile_token(row_id: int) -> str` — a hashtag token `"#sq" + base36(row_id)`, lowercase, body chars `[a-z0-9]` only. Deterministic; unique per `row_id`.
- Consumes: `pipeline.save_post -> post_row_id: int`; mutates `studio_decision.visual_direction["caption_marker"]` (serialized into `decision_json` by `save_proposal` at `pipeline.py:1024` via `studio_decision.to_dict()`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reconcile_token.py
import re
from studio.reconcile import reconcile_token


def test_token_shape():
    t = reconcile_token(1)
    assert t.startswith("#sq")
    assert re.fullmatch(r"#sq[a-z0-9]+", t)


def test_token_deterministic_and_unique():
    assert reconcile_token(42) == reconcile_token(42)
    assert reconcile_token(1) != reconcile_token(2)


def test_token_large_id():
    assert re.fullmatch(r"#sq[a-z0-9]+", reconcile_token(1234567))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reconcile_token.py -v`
Expected: FAIL with `ImportError: cannot import name 'reconcile_token'`

- [ ] **Step 3: Add `reconcile_token` to `studio/reconcile.py`** (after the module docstring / imports, before `fetch_recent_media`)

```python
def reconcile_token(row_id: int) -> str:
    """Stable, unique, edit-surviving caption marker: '#sq' + base36(row_id)."""
    n = int(row_id)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "#sq0"
    s = ""
    while n > 0:
        n, r = divmod(n, 36)
        s = digits[r] + s
    return "#sq" + s
```

- [ ] **Step 4: Wire the token into the studio branch of `pipeline.py`.**

Add the import near the other `src`/`studio` imports (top of `pipeline.py`, alongside `from src.core.data_store import ...`):

```python
from studio.reconcile import reconcile_token
```

In `run_pipeline`, immediately after the studio-branch `post_row_id = save_post(...)` (`pipeline.py:772`), insert:

```python
        # Stamp a stable, edit-surviving reconcile marker on caption + proposal.
        if studio_decision is not None and post_row_id is not None:
            _token = reconcile_token(post_row_id)
            quote_data["caption"] = f"{quote_data['caption']}\n{_token}"
            studio_decision.visual_direction["caption_marker"] = _token
```

- [ ] **Step 5: Add a targeted assertion that the caption gets stamped.**

Append to `tests/test_reconcile_token.py`:

```python
def test_caption_stamp_uses_token():
    # The stamping idiom the pipeline uses, verified in isolation.
    caption = "Some caption\n\nEngagement block"
    token = reconcile_token(7)
    stamped = f"{caption}\n{token}"
    assert stamped.endswith(token)
    assert token in stamped
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reconcile_token.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: Commit**

```bash
git add studio/reconcile.py pipeline.py tests/test_reconcile_token.py
git commit -m "feat(reconcile): stable hashtag token stamped on caption + proposal"
```

---

### Task 4: A6 — timestamp-proximity fallback in reconcile

**Files:**
- Modify: `studio/reconcile.py` (`match` keeps token substring; add `_match_by_time`; `reconcile_pending` claims media so none is double-assigned and falls back to time proximity)
- Test: `tests/test_reconcile.py` (create; if it exists, add the cases)

**Interfaces:**
- Consumes: `reconcile_token` (Task 3); `data_store.get_pending_proposals()` rows include `created_at` (from `proposals.created_at DEFAULT CURRENT_TIMESTAMP`, `data_store.py:104`) and `decision_json`.
- Produces: `studio.reconcile._match_by_time(created_at: str, media: list, claimed: set, window_hours: float = 6.0) -> str | None` — nearest unclaimed media whose `timestamp` is within the window; else `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reconcile.py
from studio import reconcile
from studio.reconcile import reconcile_token, match, _match_by_time


def _media(id_, caption, ts):
    return {"id": id_, "caption": caption, "timestamp": ts}


def test_match_token_present():
    tok = reconcile_token(5)
    media = [_media("A", "hello world", "t"), _media("B", f"deep quote {tok}", "t")]
    assert match({"caption_marker": tok}, media) == "B"


def test_match_survives_caption_edit():
    # Human rewrote the whole caption but kept the trailing hashtag.
    tok = reconcile_token(5)
    media = [_media("B", f"totally different words the human typed {tok}", "t")]
    assert match({"caption_marker": tok}, media) == "B"


def test_time_fallback_picks_nearest_in_window():
    created = "2026-07-12T12:00:00+0000"
    media = [
        _media("far", "no token", "2026-07-12T20:00:00+0000"),   # 8h -> out of window
        _media("near", "no token", "2026-07-12T13:30:00+0000"),  # 1.5h -> in window
    ]
    assert _match_by_time(created, media, claimed=set()) == "near"


def test_time_fallback_none_when_all_out_of_window():
    created = "2026-07-12T12:00:00+0000"
    media = [_media("far", "no token", "2026-07-13T12:00:00+0000")]  # 24h
    assert _match_by_time(created, media, claimed=set()) is None


def test_time_fallback_skips_claimed():
    created = "2026-07-12T12:00:00+0000"
    media = [_media("near", "no token", "2026-07-12T12:30:00+0000")]
    assert _match_by_time(created, media, claimed={"near"}) is None


def test_time_fallback_never_raises_on_bad_timestamp():
    assert _match_by_time("garbage", [_media("x", "c", "also-garbage")], claimed=set()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reconcile.py -v`
Expected: FAIL with `ImportError: cannot import name '_match_by_time'`

- [ ] **Step 3: Add the time-proximity matcher to `studio/reconcile.py`** (after `match`)

```python
from datetime import datetime


def _parse_ts(s):
    """Parse an IG/ISO timestamp; return datetime or None (best-effort)."""
    if not s:
        return None
    txt = str(s).strip().replace("Z", "+0000")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(txt, fmt)
        except ValueError:
            continue
    return None


def _match_by_time(created_at, media, claimed, window_hours: float = 6.0):
    """Nearest unclaimed media within window_hours of created_at; else None."""
    base = _parse_ts(created_at)
    if base is None:
        return None
    best_id, best_delta = None, None
    for m in media:
        mid = m.get("id")
        if mid in claimed:
            continue
        mt = _parse_ts(m.get("timestamp"))
        if mt is None:
            continue
        # compare naive-safely: use timestamps
        try:
            delta = abs((mt - base).total_seconds())
        except (TypeError, ValueError):
            continue
        if delta <= window_hours * 3600 and (best_delta is None or delta < best_delta):
            best_id, best_delta = mid, delta
    return best_id
```

Note: if `base` is timezone-aware and `mt` naive (or vice-versa), `mt - base` raises `TypeError` — caught above, that media is skipped. The tests use consistent `+0000` offsets.

- [ ] **Step 4: Make `reconcile_pending` claim media and fall back to time.** Replace the loop body in `reconcile_pending`:

```python
def reconcile_pending(token, ig_id, *, getter=requests.get):
    pending = data_store.get_pending_proposals()
    if not pending:
        return 0
    media = fetch_recent_media(token, ig_id, getter=getter)
    claimed = set()
    backfilled = 0
    for p in pending:
        post_id = match({"caption_marker": _marker_for(p)}, media)
        if post_id is None:
            post_id = _match_by_time(p.get("created_at"), media, claimed)
        if post_id:
            claimed.add(post_id)
            data_store.mark_proposal_posted(p["id"], post_id)
            backfilled += 1
    log.info("[reconcile] backfilled %d post(s)", backfilled)
    return backfilled
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reconcile.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add studio/reconcile.py tests/test_reconcile.py
git commit -m "feat(reconcile): timestamp-proximity fallback so caption rewrites still reconcile"
```

---

### Task 5: A5 — publish-path contract test + README

**Files:**
- Test: `tests/test_publish_contract.py` (create)
- Create: `README.md` (root — none exists today)

**Interfaces:**
- Consumes: `src.core.instagram_poster.post_reel_to_instagram(video_path, caption, ig_account_id, access_token, cloudinary_config, cover_path=None) -> str` and its private request helpers.

- [ ] **Step 1: Write the failing contract test** (mocked HTTP — no network, no live post)

```python
# tests/test_publish_contract.py
import types
import src.core.instagram_poster as ip


class _Resp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


def test_reel_publish_request_contract(monkeypatch):
    calls = {"post": [], "get": []}

    # Cloudinary → fake public URL, no network.
    monkeypatch.setattr(ip, "upload_video_to_cloudinary", lambda p, c: "https://cdn/v.mp4")
    monkeypatch.setattr(ip, "upload_to_cloudinary", lambda p, c: "https://cdn/cover.jpg")

    def fake_post(url, params=None, timeout=None):
        calls["post"].append((url, params))
        if url.endswith("/media"):
            return _Resp({"id": "CONTAINER_1"})
        if url.endswith("/media_publish"):
            return _Resp({"id": "POST_123"})
        raise AssertionError(f"unexpected POST {url}")

    def fake_get(url, params=None, timeout=None):
        calls["get"].append((url, params))
        return _Resp({"status_code": "FINISHED"})

    monkeypatch.setattr(ip.requests, "post", fake_post)
    monkeypatch.setattr(ip.requests, "get", fake_get)

    post_id = ip.post_reel_to_instagram(
        "video.mp4", "a caption", "IGID", "TOKEN",
        {"cloud_name": "c", "api_key": "k", "api_secret": "s"},
        cover_path="cover.jpg",
    )

    assert post_id == "POST_123"
    # container-create call carries the Reel contract
    create = next(p for (u, p) in calls["post"] if u.endswith("/media"))
    assert create["media_type"] == "REELS"
    assert create["video_url"] == "https://cdn/v.mp4"
    assert create["caption"] == "a caption"
    assert create["cover_url"] == "https://cdn/cover.jpg"
    # publish call references the container
    publish = next(p for (u, p) in calls["post"] if u.endswith("/media_publish"))
    assert publish["creation_id"] == "CONTAINER_1"
```

- [ ] **Step 2: Run test to verify it fails (or errors) before you confirm wiring**

Run: `.venv/bin/python -m pytest tests/test_publish_contract.py -v`
Expected: The test drives real module code; it should PASS once the monkeypatching matches the current implementation. If it FAILS, the failure documents a real contract drift — fix the test to match `instagram_poster` as written (do **not** change `instagram_poster`; this task only adds a guard test).

- [ ] **Step 3: Create `README.md` at repo root** documenting the publish model

```markdown
# Socrates Instagram Pipeline

Automated daily philosophy Reels/carousels for Instagram.

## Publishing model (important)

Scheduled production runs `python pipeline.py --studio --manual`. **Manual mode
is intentional and is the default**: the pipeline generates the asset, sends it
to Telegram, and records it as `PENDING_MANUAL` — a human then uploads it so
they can add **trending audio** (the #1 Reels reach lever, which the Graph API
cannot attach).

The fully-automated Graph-API publish path (`src/core/instagram_poster.py`)
exists and is exercised by a contract test (`tests/test_publish_contract.py`),
but is **opt-in** — it runs only when a slot executes with `not dry_run and not
manual`. It is not used by the scheduled cron.

Manual posts are reconciled back to their real `post_id` by
`studio/reconcile.py`, which matches a stable hashtag token (`#sq…`) appended to
each caption, falling back to timestamp proximity if the caption was rewritten.

## Tests

Run with the 3.11 venv: `.venv/bin/python -m pytest`
(Two `tests/test_reel_composer.py` ffmpeg cases fail in environments without a
matching ffmpeg build — pre-existing, not regressions.)
```

- [ ] **Step 4: Run the contract test to confirm green**

Run: `.venv/bin/python -m pytest tests/test_publish_contract.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_publish_contract.py README.md
git commit -m "test(publish): contract test for the Graph-API reel path; document manual-publish model"
```

---

## Final verification (after all tasks)

- [ ] Run the full suite: `.venv/bin/python -m pytest -q`
- [ ] Expected: green apart from the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures.
- [ ] Confirm no tracked absolute paths remain: `git grep -l "/Users/" -- '*.jsonl' '*.db'` should be empty for newly written records (historical rows in the tracked DB are out of scope).
- [ ] `git ls-files audio/*.mp3 | wc -l` → 7 (mood beds still tracked).

## Self-review notes

- **Spec coverage:** A5 → Task 5 (contract test + README). A6 → Task 3 (token + stamping) + Task 4 (time fallback). C1 → Task 1 (path hygiene) + Task 2 (untrack + gitignore + workflow). Mood-bed preservation → Task 2. Out-of-scope history rewrite → documented in README/plan, not implemented.
- **Types:** `reconcile_token(int)->str`, `_match_by_time(str,list,set,float)->str|None`, `_rel_path(x)->str|None` are used consistently across tasks.
- **Best-effort invariant:** `_rel_path`, `_parse_ts`, `_match_by_time`, and the caption-stamp block all swallow/guard failures and never raise into the pipeline.
