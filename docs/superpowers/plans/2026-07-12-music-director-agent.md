# Music Director Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Music Director" reasoning agent that forms a Pixabay search query from a reel's quote/hook/mood and ranks the returned tracks by emotional fit, replacing the flat mood→track lookup.

**Architecture:** A new `studio/music_director.py` agent (mirrors `studio/director.py`) makes two `StudioClient` calls — `compose_query` then `rank_tracks` — reusing the existing `src/audio/download_music.py` Pixabay plumbing for search/download. `pipeline.py`'s POV-reel path calls it through a small `_select_reel_music` helper, falling back to today's mood-based track on any failure or missing key.

**Tech Stack:** Python 3.11, Anthropic SDK (via `studio.client.StudioClient`), Pixabay Music API (via `src/audio/download_music.py`), pytest.

## Global Constraints

- Python 3.11; run tests with `.venv/bin/python -m pytest`.
- The agent must NEVER crash a reel: every failure path returns/falls back silently (logs only).
- Two `claude-sonnet-4-6` calls per reel max, gated by the existing `StudioClient.over_daily_ceiling()`.
- Reuse existing helpers in `src/audio/download_music.py`; do not duplicate Pixabay logic.
- Studio agent modules follow the existing shape: `_PREFIX`, `_ROLE`, public functions calling `client.call(role, shared_prefix, role_system, user_content, schema)`.
- Never commit `data/pipeline.db` changes (the secret-leak guard test forbids a token in it); if a run dirties it, `git checkout -- data/pipeline.db` before committing.

---

### Task 1: Types + role registration

**Files:**
- Modify: `studio/types.py` (append dataclasses + schemas)
- Modify: `studio/settings.py` (add `music_director` to `ROLE_MODELS` and `ROLE_EFFORT`)
- Test: `tests/test_studio_types.py` (append)

**Interfaces:**
- Produces: `MusicDirection(search_query: str, energy: str, bpm_range: list, instruments: list, avoid: list)` with `.to_dict()` / `.from_dict(d)`; `MusicPick(track_id: str, rationale: str, runner_up_id: str | None = None)` with `.to_dict()` / `.from_dict(d)`; module constants `MUSIC_DIRECTION_SCHEMA`, `MUSIC_PICK_SCHEMA`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_studio_types.py`:

```python
def test_music_direction_roundtrip():
    from studio.types import MusicDirection, MUSIC_DIRECTION_SCHEMA
    d = {"search_query": "somber cello adagio", "energy": "low",
         "bpm_range": [55, 65], "instruments": ["cello"], "avoid": ["drums"]}
    md = MusicDirection.from_dict(d)
    assert md.search_query == "somber cello adagio"
    assert md.to_dict() == d
    assert MUSIC_DIRECTION_SCHEMA["properties"]["energy"]["enum"] == ["low", "medium", "high"]


def test_music_pick_roundtrip_and_optional_runner_up():
    from studio.types import MusicPick, MUSIC_PICK_SCHEMA
    mp = MusicPick.from_dict({"track_id": "123", "rationale": "fits grief"})
    assert mp.track_id == "123"
    assert mp.runner_up_id is None
    assert "track_id" in MUSIC_PICK_SCHEMA["required"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_studio_types.py::test_music_direction_roundtrip tests/test_studio_types.py::test_music_pick_roundtrip_and_optional_runner_up -v`
Expected: FAIL with `ImportError: cannot import name 'MusicDirection'`.

- [ ] **Step 3: Add dataclasses + schemas**

Append to `studio/types.py` (after the `Decision` dataclass and after the `DECISION_SCHEMA` block respectively — dataclasses go with the dataclasses, schemas with the schemas):

```python
@dataclass
class MusicDirection:
    search_query: str
    energy: str
    bpm_range: list
    instruments: list
    avoid: list

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class MusicPick:
    track_id: str
    rationale: str
    runner_up_id: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)
```

And append after `DECISION_SCHEMA`:

```python
MUSIC_DIRECTION_SCHEMA = _obj({
    "search_query": {"type": "string"},
    "energy": {"type": "string", "enum": ["low", "medium", "high"]},
    "bpm_range": {"type": "array", "items": {"type": "integer"}},
    "instruments": {"type": "array", "items": {"type": "string"}},
    "avoid": {"type": "array", "items": {"type": "string"}},
}, ["search_query", "energy", "bpm_range", "instruments", "avoid"])

MUSIC_PICK_SCHEMA = _obj({
    "track_id": {"type": "string"},
    "rationale": {"type": "string"},
    "runner_up_id": {"type": ["string", "null"]},
}, ["track_id", "rationale"])
```

- [ ] **Step 4: Register the role**

In `studio/settings.py`, add to `ROLE_MODELS` (alongside the other roles):

```python
    "music_director":         "claude-sonnet-4-6",
```

and to `ROLE_EFFORT`:

```python
    "music_director":         "medium",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_studio_types.py -v`
Expected: PASS (all, including the two new tests).

- [ ] **Step 6: Commit**

```bash
git add studio/types.py studio/settings.py tests/test_studio_types.py
git commit -m "feat(music-director): add MusicDirection/MusicPick types + role"
```

---

### Task 2: compose_query + rank_tracks agent calls

**Files:**
- Create: `studio/music_director.py`
- Test: `tests/test_studio_music_director.py`

**Interfaces:**
- Consumes: `MusicDirection`, `MUSIC_DIRECTION_SCHEMA`, `MusicPick`, `MUSIC_PICK_SCHEMA` from Task 1; `download_music._extract_track_meta(hit) -> dict` (existing, returns keys `id`, `tags`, `duration`, ...); a client object with `call(role, shared_prefix, role_system, user_content, schema) -> dict`.
- Produces: `compose_query(client, ctx: dict) -> MusicDirection`; `rank_tracks(client, ctx: dict, hits: list[dict]) -> MusicPick`; module constant `_PREFIX`. `ctx` keys: `quote`, `hook`, `mood`, optional `studio` (dict with `theme`/`angle`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_studio_music_director.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import music_director as md
from studio.types import MusicDirection, MusicPick


class _SeqClient:
    """Returns queued payloads in order; records role per call."""
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.roles = []

    def call(self, role, *a, **k):
        self.roles.append(role)
        return self.payloads.pop(0)


def _ctx():
    return {"quote": "First say to yourself what you would be.",
            "hook": "You've delayed this long enough.", "mood": "dark_philosophical"}


def test_compose_query_returns_direction():
    client = _SeqClient([{
        "search_query": "somber cello adagio", "energy": "low",
        "bpm_range": [55, 65], "instruments": ["cello"], "avoid": ["drums"]}])
    direction = md.compose_query(client, _ctx())
    assert isinstance(direction, MusicDirection)
    assert direction.search_query == "somber cello adagio"
    assert client.roles == ["music_director"]


def test_rank_tracks_returns_pick():
    hits = [{"id": 11, "tags": "cello, sad", "duration": 30},
            {"id": 22, "tags": "drums, epic", "duration": 20}]
    client = _SeqClient([{"track_id": "11", "rationale": "grief fits", "runner_up_id": "22"}])
    pick = md.rank_tracks(client, _ctx(), hits)
    assert isinstance(pick, MusicPick)
    assert pick.track_id == "11"
    assert client.roles == ["music_director"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_studio_music_director.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.music_director'`.

- [ ] **Step 3: Create the agent module (query + rank only)**

Create `studio/music_director.py`:

```python
"""Music Director agent — a music-supervisor persona that forms a Pixabay search
query from a reel's content and ranks the returned tracks by emotional fit.

Two LLM calls (role ``music_director``): ``compose_query`` then ``rank_tracks``.
The orchestrator ``select_music`` (Task 3) chains them with the Pixabay plumbing
in ``src/audio/download_music.py`` and degrades gracefully.
"""
import json

from studio.types import (
    MusicDirection, MUSIC_DIRECTION_SCHEMA,
    MusicPick, MUSIC_PICK_SCHEMA,
)
from src.audio import download_music

_PREFIX = (
    "You are a music supervisor with 10 years scoring short-form video for a "
    "stoic-philosophy Instagram account. You choose instrumental, royalty-free "
    "music that matches the emotional arc of a spoken quote and sits well under "
    "a slow, deep narration — never fighting the voice."
)

_QUERY_ROLE = (
    "Reel content:\n{ctx}\n"
    "Compose ONE Pixabay music search query (2-5 words, instrumental) plus the "
    "target energy, bpm range, instruments to feature, and things to avoid. Match "
    "the quote's emotion, not just the mood label. Output a MusicDirection as JSON only."
)

_RANK_ROLE = (
    "Reel content:\n{ctx}\n"
    "Candidate tracks (from Pixabay; choose the single best emotional fit):\n{tracks}\n"
    "Pick track_id (it MUST be one of the listed ids). Give a one-line rationale and "
    "an optional runner_up_id. Prefer 15-40s instrumental beds that won't fight a slow "
    "deep voice. Output a MusicPick as JSON only."
)


def _ctx_json(ctx):
    studio = ctx.get("studio") or {}
    return json.dumps({
        "quote": ctx.get("quote", ""),
        "hook": ctx.get("hook", ""),
        "mood": ctx.get("mood", ""),
        "theme": studio.get("theme", ""),
        "angle": studio.get("angle", ""),
    }, indent=2)


def compose_query(client, ctx) -> MusicDirection:
    role = _QUERY_ROLE.format(ctx=_ctx_json(ctx))
    d = client.call("music_director", _PREFIX, role,
                    "Compose the music direction now.", MUSIC_DIRECTION_SCHEMA)
    return MusicDirection.from_dict(d)


def _tracks_for_prompt(hits):
    out = []
    for h in hits:
        meta = download_music._extract_track_meta(h)
        out.append({"id": str(meta["id"]), "tags": meta["tags"],
                    "duration": meta["duration"]})
    return out


def rank_tracks(client, ctx, hits) -> MusicPick:
    role = _RANK_ROLE.format(ctx=_ctx_json(ctx),
                             tracks=json.dumps(_tracks_for_prompt(hits), indent=2))
    d = client.call("music_director", _PREFIX, role,
                    "Pick the best track now.", MUSIC_PICK_SCHEMA)
    return MusicPick.from_dict(d)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_studio_music_director.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add studio/music_director.py tests/test_studio_music_director.py
git commit -m "feat(music-director): compose_query + rank_tracks agent calls"
```

---

### Task 3: select_music orchestration + fallback chain

**Files:**
- Modify: `studio/music_director.py` (add `select_music`)
- Test: `tests/test_studio_music_director.py` (append)

**Interfaces:**
- Consumes: `compose_query`, `rank_tracks` from Task 2; `download_music._search_pixabay_music(query, api_key, per_page) -> list[dict]`, `download_music._pick_audio_url(hit) -> str | None`, `download_music._download_track(url, output_path) -> bool`, `download_music._pick_from_pool(hits, mood, cache, pool_size=3) -> dict | None`, `download_music._load_cache() -> dict` (all existing).
- Produces: `select_music(client, ctx: dict, api_key: str, output_dir) -> Path | None`. Returns the downloaded `Path`, or `None` to signal the caller to fall back. Never raises.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_studio_music_director.py`:

```python
def test_select_music_none_without_api_key():
    assert md.select_music(_SeqClient([]), _ctx(), "", "/tmp") is None


def test_select_music_none_when_no_hits(monkeypatch):
    monkeypatch.setattr(md.download_music, "_search_pixabay_music",
                        lambda q, k, per_page=20: [])
    client = _SeqClient([{"search_query": "x", "energy": "low",
                          "bpm_range": [50, 60], "instruments": [], "avoid": []}])
    assert md.select_music(client, _ctx(), "KEY", "/tmp") is None


def test_select_music_downloads_agent_pick(tmp_path, monkeypatch):
    hits = [{"id": 11, "tags": "cello", "duration": 30, "audio": "http://x/a.mp3"},
            {"id": 22, "tags": "drums", "duration": 20, "audio": "http://x/b.mp3"}]
    monkeypatch.setattr(md.download_music, "_search_pixabay_music",
                        lambda q, k, per_page=20: hits)
    captured = {}

    def fake_dl(url, output_path):
        captured["url"] = url
        Path(output_path).write_bytes(b"ID3fake")
        return True

    monkeypatch.setattr(md.download_music, "_download_track", fake_dl)
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": ["cello"], "avoid": []},
        {"track_id": "11", "rationale": "grief fits", "runner_up_id": "22"},
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is not None and Path(out).exists()
    assert captured["url"] == "http://x/a.mp3"  # the id=11 track the agent picked


def test_select_music_unknown_id_falls_back_to_heuristic(tmp_path, monkeypatch):
    hits = [{"id": 11, "tags": "cello", "duration": 30, "audio": "http://x/a.mp3"}]
    monkeypatch.setattr(md.download_music, "_search_pixabay_music",
                        lambda q, k, per_page=20: hits)
    monkeypatch.setattr(md.download_music, "_load_cache", lambda: {})
    picked = {}
    monkeypatch.setattr(md.download_music, "_pick_from_pool",
                        lambda h, mood, cache, pool_size=3: (picked.setdefault("used", True), h[0])[1])
    monkeypatch.setattr(md.download_music, "_download_track",
                        lambda url, output_path: (Path(output_path).write_bytes(b"ID3x"), True)[1])
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": [], "avoid": []},
        {"track_id": "999", "rationale": "not in list"},  # unknown id
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is not None
    assert picked.get("used") is True  # heuristic fallback ran
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_studio_music_director.py -k select_music -v`
Expected: FAIL with `AttributeError: module 'studio.music_director' has no attribute 'select_music'`.

- [ ] **Step 3: Add select_music**

Append to `studio/music_director.py`:

```python
def select_music(client, ctx, api_key, output_dir):
    """compose query -> Pixabay search -> rank -> download. Returns the track
    Path, or None to signal the caller to fall back. Never raises."""
    from pathlib import Path

    if not api_key:
        return None

    try:
        direction = compose_query(client, ctx)
    except Exception as e:  # noqa: BLE001 - never crash a reel
        print(f"  [music-director] query failed ({e})")
        return None

    hits = download_music._search_pixabay_music(direction.search_query, api_key, per_page=20)
    if not hits:
        print("  [music-director] no Pixabay hits")
        return None

    chosen = None
    try:
        pick = rank_tracks(client, ctx, hits)
        chosen = next((h for h in hits if str(h.get("id")) == pick.track_id), None)
        if chosen is not None:
            print(f"  [music-director] picked {pick.track_id}: {pick.rationale[:60]}")
    except Exception as e:  # noqa: BLE001
        print(f"  [music-director] rank failed ({e}) — heuristic fallback")
    if chosen is None:
        chosen = download_music._pick_from_pool(hits, ctx.get("mood", ""),
                                                download_music._load_cache())
    if chosen is None:
        return None

    url = download_music._pick_audio_url(chosen)
    if not url:
        print("  [music-director] chosen track has no download URL")
        return None

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"music_director_{ctx.get('mood', 'track')}.mp3"
    if download_music._download_track(url, output_path):
        return output_path
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_studio_music_director.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add studio/music_director.py tests/test_studio_music_director.py
git commit -m "feat(music-director): select_music orchestration + fallback chain"
```

---

### Task 4: Wire into the reel pipeline

**Files:**
- Modify: `pipeline.py` (add `_select_reel_music` helper; call it in `_run_pov_reel` where music is currently fetched — around lines 501-505)
- Test: `tests/test_reel_music_selection.py`

**Interfaces:**
- Consumes: `studio.music_director.select_music`, `studio.client.StudioClient`, `src.audio.trending_audio.download_music_for_mood(mood, output_dir="")`, `config.Config`.
- Produces: `_select_reel_music(cfg, quote_data: dict, hook_text: str, mood: str) -> Path | None` in `pipeline.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_reel_music_selection.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


class _Cfg:
    PIXABAY_API_KEY = ""
    ANTHROPIC_API_KEY = "A"


def test_falls_back_to_mood_music_without_pixabay_key(monkeypatch):
    # No Pixabay key -> music director must NOT be invoked; mood path used.
    called = {"director": False, "mood": False}

    def fake_director(*a, **k):
        called["director"] = True
        return None

    def fake_mood(mood, output_dir=""):
        called["mood"] = True
        return Path("/tmp/mood.mp3")

    monkeypatch.setattr(pipeline.music_director, "select_music", fake_director)
    monkeypatch.setattr(pipeline, "download_music_for_mood", fake_mood, raising=False)

    out = pipeline._select_reel_music(_Cfg(), {"quote": "q"}, "hook", "dark_philosophical")
    assert out == Path("/tmp/mood.mp3")
    assert called["director"] is False
    assert called["mood"] is True


def test_uses_music_director_when_keys_present(monkeypatch):
    class _Cfg2:
        PIXABAY_API_KEY = "P"
        ANTHROPIC_API_KEY = "A"

    monkeypatch.setattr(pipeline, "StudioClient",
                        lambda key: type("C", (), {"over_daily_ceiling": lambda self: False})())
    monkeypatch.setattr(pipeline.music_director, "select_music",
                        lambda client, ctx, key, out: Path("/tmp/director.mp3"))
    out = pipeline._select_reel_music(_Cfg2(), {"quote": "q"}, "hook", "dark_philosophical")
    assert out == Path("/tmp/director.mp3")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reel_music_selection.py -v`
Expected: FAIL with `AttributeError: module 'pipeline' has no attribute '_select_reel_music'` (or on the `music_director` attribute).

- [ ] **Step 3: Add the import + helper**

In `pipeline.py`, add near the other studio imports (top of file, with `from studio.reconcile import reconcile_token`):

```python
from studio.client import StudioClient
from studio import music_director
from src.audio.trending_audio import download_music_for_mood
```

Then add the helper (place it just above `def _run_pov_reel(`):

```python
def _select_reel_music(cfg, quote_data, hook_text, mood):
    """Pick the reel's music bed. Uses the Music Director agent when both
    PIXABAY_API_KEY and ANTHROPIC_API_KEY are set (studio-aware via any theme/
    angle already on quote_data); otherwise, or on any failure, falls back to the
    mood-based track. Never raises."""
    music_path = None
    if getattr(cfg, "PIXABAY_API_KEY", "") and getattr(cfg, "ANTHROPIC_API_KEY", ""):
        try:
            client = StudioClient(cfg.ANTHROPIC_API_KEY)
            if not client.over_daily_ceiling():
                ctx = {
                    "quote": quote_data.get("quote", ""),
                    "hook": hook_text,
                    "mood": mood,
                    "studio": {"theme": quote_data.get("topic_theme", ""),
                               "angle": quote_data.get("angle", "")},
                }
                music_path = music_director.select_music(
                    client, ctx, cfg.PIXABAY_API_KEY, OUTPUT_DIR)
        except Exception as e:  # noqa: BLE001 - never crash a reel
            log.warning(f"  [music-director] unavailable ({e}) — mood fallback")
    if music_path is None:
        try:
            music_path = download_music_for_mood(mood)
        except Exception as e:  # noqa: BLE001
            log.warning(f"  [remotion] music bed unavailable ({e}) — VO-only reel")
    return music_path
```

- [ ] **Step 4: Replace the inline music fetch in `_run_pov_reel`**

Find this block in `_run_pov_reel` (currently around lines 501-505):

```python
        try:
            from src.audio.trending_audio import download_music_for_mood
            music_path = download_music_for_mood(mood)
        except Exception as e:
            log.warning(f"  [remotion] music bed unavailable ({e}) — VO-only reel")
```

Replace it with:

```python
        music_path = _select_reel_music(cfg, quote_data, hook_text, mood)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reel_music_selection.py -v`
Expected: PASS (both).

- [ ] **Step 6: Run the full suite (no regressions)**

Run: `.venv/bin/python -m pytest -q`
Expected: only the two pre-existing `tests/test_reel_composer.py` ffmpeg failures; everything else passes. If `tests/test_workflow_reliability.py::test_committed_db_has_no_token` fails, run `git checkout -- data/pipeline.db` and re-run.

- [ ] **Step 7: Commit**

```bash
git add pipeline.py tests/test_reel_music_selection.py
git commit -m "feat(music-director): wire content-aware music selection into POV reels"
```

---

## Notes for the implementer

- `_run_pov_reel` receives `cfg`, `quote_data`, `mood`, and computes `hook_text` before the music block — all four args for `_select_reel_music` are already in scope at the replacement site.
- Do NOT change `_run_pov_reel`'s signature. Studio-awareness is best-effort via `quote_data.get("topic_theme"/"angle")`; those keys may be absent (empty strings), which is fine.
- End-to-end manual check (optional, costs API + needs `PIXABAY_API_KEY`): add the key to `.env`, then `.venv/bin/python pipeline.py --remotion --dry-run` and look for a `[music-director] picked …` log line; without the key you should see the normal mood-music log instead.
