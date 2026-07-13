# Jamendo Music-Source Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Music Director's dead Pixabay music source with the Jamendo API (real, free, instrumental, downloadable) and delete the unused Pixabay module — the reasoning agent is unchanged.

**Architecture:** A new self-contained `src/audio/jamendo_music.py` provides search/meta/url/download over `https://api.jamendo.com/v3.0/tracks/`. `studio/music_director.select_music` swaps its source calls from `download_music.*` to `jamendo_music.*`; `pipeline._select_reel_music` gates on `JAMENDO_CLIENT_ID`. `src/audio/download_music.py` is deleted (its only importer was `music_director`).

**Tech Stack:** Python 3.11, `requests`, Anthropic SDK (unchanged agent), pytest.

## Global Constraints

- Python 3.11; run tests with `.venv/bin/python -m pytest`.
- Jamendo endpoint: `GET https://api.jamendo.com/v3.0/tracks/` with `client_id`, `format=json`, `limit`, `fuzzytags`, `vocalinstrumental=instrumental` (ALWAYS), `speed`, `include=musicinfo`.
- **Always post-filter** returned hits on `audiodownload_allowed == True` — the server-side param is unreliable.
- The Music Director must NEVER crash a reel: every failure path returns `None`/falls back, logging only.
- `select_music` keeps its signature `(client, ctx, api_key, output_dir) -> Path | None`; `api_key` now carries the Jamendo client_id.
- Do NOT commit `data/pipeline.db` (secret-leak guard); if a run dirties it, `git checkout -- data/pipeline.db` before committing.
- Unrelated uncommitted artifacts exist (quotes.xlsx, remotion/public/*.mp3, reel-data.json) — never stage them. Only `git add` the exact files each task's commit step names.
- Full suite is green EXCEPT the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures.

---

### Task 1: Config — add JAMENDO_CLIENT_ID

**Files:**
- Modify: `config.py` (class attr near line 25; `_get_opt` assignment near line 45)
- Modify: `.env.example`
- Test: `tests/test_config_jamendo.py`

**Interfaces:**
- Produces: `Config().JAMENDO_CLIENT_ID -> str` (empty string when unset).

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_jamendo.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_exposes_jamendo_client_id(monkeypatch):
    monkeypatch.setenv("JAMENDO_CLIENT_ID", "abc123")
    # Config reads os.environ via _get_opt; construct fresh.
    from config import Config
    cfg = Config()
    assert cfg.JAMENDO_CLIENT_ID == "abc123"


def test_config_jamendo_defaults_empty(monkeypatch):
    monkeypatch.delenv("JAMENDO_CLIENT_ID", raising=False)
    from config import Config
    cfg = Config()
    assert cfg.JAMENDO_CLIENT_ID == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config_jamendo.py -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'JAMENDO_CLIENT_ID'`.

- [ ] **Step 3: Add the config field**

In `config.py`, add a class attribute next to the existing `PIXABAY_API_KEY: str = ""` line (~line 25):

```python
    JAMENDO_CLIENT_ID: str = ""      # Optional — Jamendo royalty-free music
```

And add the assignment next to `self.PIXABAY_API_KEY = self._get_opt("PIXABAY_API_KEY")` (~line 45):

```python
        self.JAMENDO_CLIENT_ID       = self._get_opt("JAMENDO_CLIENT_ID")
```

- [ ] **Step 4: Add the .env.example placeholder**

In `.env.example`, under the Pixabay section, add:

```
# Jamendo Music — https://devportal.jamendo.com (free client_id)
JAMENDO_CLIENT_ID=your_jamendo_client_id_here
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_config_jamendo.py -v`
Expected: PASS (both).

- [ ] **Step 6: Commit**

```bash
git add config.py .env.example tests/test_config_jamendo.py
git commit -m "feat(jamendo): add JAMENDO_CLIENT_ID config"
```

---

### Task 2: `src/audio/jamendo_music.py` source module

**Files:**
- Create: `src/audio/jamendo_music.py`
- Test: `tests/test_jamendo_music.py`

**Interfaces:**
- Consumes: `MusicDirection` (has `.search_query: str`, `.energy: str`) from `studio.types`.
- Produces:
  - `search_tracks(direction, client_id, limit=20) -> list[dict]` (only `audiodownload_allowed` hits)
  - `extract_meta(hit) -> dict` → `{id: str, name: str, tags: str, duration}`
  - `pick_audio_url(hit) -> str | None`
  - `download_track(url, output_path) -> bool`
  - `pick_from_pool(hits) -> dict | None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_jamendo_music.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio import jamendo_music as jm


class _Dir:
    def __init__(self, search_query="dark ambient", energy="low"):
        self.search_query = search_query
        self.energy = energy


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_search_tracks_sends_instrumental_and_filters_disallowed(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _Resp({"results": [
            {"id": 1, "name": "ok", "duration": 30, "audiodownload": "http://x/1.mp3",
             "audiodownload_allowed": True},
            {"id": 2, "name": "no", "duration": 30, "audiodownload": "http://x/2.mp3",
             "audiodownload_allowed": False},
        ]})

    monkeypatch.setattr(jm.requests, "get", fake_get)
    hits = jm.search_tracks(_Dir(search_query="dark ambient", energy="low"), "KEY", limit=20)

    assert captured["params"]["vocalinstrumental"] == "instrumental"
    assert captured["params"]["speed"] == "low"
    assert captured["params"]["fuzzytags"] == "dark+ambient"
    assert captured["params"]["client_id"] == "KEY"
    assert [h["id"] for h in hits] == [1]  # disallowed hit filtered out


def test_search_tracks_http_error_returns_empty(monkeypatch):
    def boom(url, params=None, timeout=None):
        raise RuntimeError("network")
    monkeypatch.setattr(jm.requests, "get", boom)
    assert jm.search_tracks(_Dir(), "KEY") == []


def test_search_tracks_no_client_id_returns_empty():
    assert jm.search_tracks(_Dir(), "") == []


def test_extract_meta_flattens_tags():
    hit = {"id": 7, "name": "Cello Piece", "duration": 42,
           "musicinfo": {"tags": {"genres": ["classical"], "instruments": ["cello"]}}}
    meta = jm.extract_meta(hit)
    assert meta["id"] == "7"
    assert meta["duration"] == 42
    assert "cello" in meta["tags"] and "classical" in meta["tags"]


def test_pick_audio_url_respects_allowed():
    assert jm.pick_audio_url({"audiodownload_allowed": True,
                              "audiodownload": "http://x/a.mp3"}) == "http://x/a.mp3"
    assert jm.pick_audio_url({"audiodownload_allowed": False,
                              "audiodownload": "http://x/a.mp3"}) is None
    assert jm.pick_audio_url({"audiodownload_allowed": True, "audiodownload": ""}) is None


def test_download_track_writes_and_validates(tmp_path, monkeypatch):
    class _DL:
        content = b"ID3" + b"\x00" * 60_000
        def raise_for_status(self): pass
    monkeypatch.setattr(jm.requests, "get", lambda url, timeout=None, stream=None: _DL())
    out = tmp_path / "t.mp3"
    assert jm.download_track("http://x/a.mp3", out) is True
    assert out.exists()


def test_download_track_error_returns_false(tmp_path, monkeypatch):
    def boom(url, timeout=None, stream=None):
        raise RuntimeError("nope")
    monkeypatch.setattr(jm.requests, "get", boom)
    assert jm.download_track("http://x/a.mp3", tmp_path / "t.mp3") is False


def test_pick_from_pool_prefers_downloadable_and_longish():
    hits = [
        {"id": 1, "audiodownload_allowed": True, "audiodownload": "http://x/1.mp3", "duration": 8},
        {"id": 2, "audiodownload_allowed": True, "audiodownload": "http://x/2.mp3", "duration": 30},
        {"id": 3, "audiodownload_allowed": False, "audiodownload": "http://x/3.mp3", "duration": 30},
    ]
    assert jm.pick_from_pool(hits)["id"] == 2  # downloadable + duration>=15
    assert jm.pick_from_pool([]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_jamendo_music.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.audio.jamendo_music'`.

- [ ] **Step 3: Create the module**

Create `src/audio/jamendo_music.py`:

```python
"""Jamendo music source for the Music Director.

Searches the Jamendo API (https://api.jamendo.com/v3.0/tracks/) for instrumental,
downloadable, CC-licensed tracks and downloads the chosen one. Self-contained:
HTTP, metadata extraction, download + validation, and a heuristic fallback pick.
Every function degrades gracefully — search/download failures return []/False so
the Music Director can fall back to the mood-based bed.
"""
from pathlib import Path

import requests

JAMENDO_TRACKS_API = "https://api.jamendo.com/v3.0/tracks/"

# MusicDirection.energy -> Jamendo `speed` (verylow..veryhigh). We only emit the
# three the agent produces; everything else defaults to medium.
_ENERGY_TO_SPEED = {"low": "low", "medium": "medium", "high": "high"}


def search_tracks(direction, client_id, limit=20):
    """Query Jamendo from a MusicDirection. Returns only tracks whose
    ``audiodownload_allowed`` is true (the server-side filter is unreliable).
    Returns [] on missing key or any error."""
    if not client_id:
        return []
    query = getattr(direction, "search_query", "") or ""
    params = {
        "client_id": client_id,
        "format": "json",
        "limit": limit,
        "fuzzytags": "+".join(query.split()),
        "vocalinstrumental": "instrumental",
        "speed": _ENERGY_TO_SPEED.get(getattr(direction, "energy", ""), "medium"),
        "include": "musicinfo",
    }
    try:
        resp = requests.get(JAMENDO_TRACKS_API, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as e:  # noqa: BLE001 - degrade gracefully
        print(f"  [jamendo] search error ({query[:30]}): {e}")
        return []
    return [h for h in results if h.get("audiodownload_allowed")]


def extract_meta(hit):
    """Compact metadata for the ranking prompt: id, name, flattened tags, duration."""
    info = hit.get("musicinfo") or {}
    tagblob = info.get("tags")
    if isinstance(tagblob, dict):
        tags = " ".join(t for vals in tagblob.values()
                        if isinstance(vals, list) for t in vals)
    else:
        tags = str(tagblob or "")
    return {"id": str(hit.get("id")), "name": hit.get("name", ""),
            "tags": tags or hit.get("name", ""), "duration": hit.get("duration")}


def pick_audio_url(hit):
    """The track's downloadable URL, or None when not allowed / absent."""
    if not hit.get("audiodownload_allowed"):
        return None
    url = hit.get("audiodownload", "")
    return url if isinstance(url, str) and url.startswith("http") else None


def _validate_audio_file(path):
    """True if `path` looks like a real audio file (size + MP3 magic bytes)."""
    if not path.exists():
        return False
    size = path.stat().st_size
    if size < 10_000:
        return False
    try:
        header = path.read_bytes()[:4]
        if header[:3] == b"ID3":
            return True
        if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return True
    except Exception:
        pass
    return size > 50_000


def download_track(url, output_path):
    """Download `url` to `output_path` and validate it. Returns True on success."""
    output_path = Path(output_path)
    try:
        dl = requests.get(url, timeout=45, stream=True)
        dl.raise_for_status()
        output_path.write_bytes(dl.content)
        size_kb = output_path.stat().st_size / 1024
        print(f"  [jamendo] Saved {output_path.name} ({size_kb:.0f} KB)")
        return _validate_audio_file(output_path)
    except Exception as e:  # noqa: BLE001
        print(f"  [jamendo] download error: {e}")
        return False


def pick_from_pool(hits):
    """Heuristic fallback when the agent doesn't pick a usable id: the first
    downloadable track, preferring duration >= 15s. None if none usable."""
    usable = [h for h in hits if pick_audio_url(h)]
    if not usable:
        return None
    longish = [h for h in usable if (h.get("duration") or 0) >= 15]
    return (longish or usable)[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_jamendo_music.py -v`
Expected: PASS (all 8).

- [ ] **Step 5: Commit**

```bash
git add src/audio/jamendo_music.py tests/test_jamendo_music.py
git commit -m "feat(jamendo): self-contained Jamendo music source module"
```

---

### Task 3: Rewire Music Director to Jamendo + delete Pixabay module

**Files:**
- Modify: `studio/music_director.py`
- Delete: `src/audio/download_music.py`
- Modify: `tests/test_studio_music_director.py` (repoint monkeypatches to `jamendo_music.*`, Jamendo hit shapes)

**Interfaces:**
- Consumes: `jamendo_music.search_tracks/extract_meta/pick_audio_url/pick_from_pool/download_track` from Task 2.
- Produces: `select_music(client, ctx, api_key, output_dir) -> Path | None` (unchanged signature; source now Jamendo). `compose_query`/`rank_tracks` unchanged.

- [ ] **Step 1: Update the tests (RED)**

Replace `tests/test_studio_music_director.py` with (Jamendo shapes; monkeypatch `md.jamendo_music.*`):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import music_director as md
from studio.types import MusicDirection, MusicPick


class _SeqClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.roles = []

    def call(self, role, *a, **k):
        self.roles.append(role)
        return self.payloads.pop(0)


def _ctx():
    return {"quote": "First say to yourself what you would be.",
            "hook": "You've delayed this long enough.", "mood": "dark_philosophical"}


def _hit(i, allowed=True, duration=30):
    return {"id": i, "name": f"track{i}", "duration": duration,
            "audiodownload": f"http://x/{i}.mp3", "audiodownload_allowed": allowed,
            "musicinfo": {"tags": {"instruments": ["cello"]}}}


def test_compose_query_returns_direction():
    client = _SeqClient([{
        "search_query": "somber cello adagio", "energy": "low",
        "bpm_range": [55, 65], "instruments": ["cello"], "avoid": ["drums"]}])
    direction = md.compose_query(client, _ctx())
    assert isinstance(direction, MusicDirection)
    assert direction.search_query == "somber cello adagio"
    assert client.roles == ["music_director"]


def test_rank_tracks_returns_pick():
    hits = [_hit(11), _hit(22)]
    client = _SeqClient([{"track_id": "11", "rationale": "grief fits", "runner_up_id": "22"}])
    pick = md.rank_tracks(client, _ctx(), hits)
    assert isinstance(pick, MusicPick)
    assert pick.track_id == "11"


def test_select_music_none_without_api_key():
    assert md.select_music(_SeqClient([]), _ctx(), "", "/tmp") is None


def test_select_music_none_when_no_hits(monkeypatch):
    monkeypatch.setattr(md.jamendo_music, "search_tracks",
                        lambda direction, client_id, limit=20: [])
    client = _SeqClient([{"search_query": "x", "energy": "low",
                          "bpm_range": [50, 60], "instruments": [], "avoid": []}])
    assert md.select_music(client, _ctx(), "KEY", "/tmp") is None


def test_select_music_downloads_agent_pick(tmp_path, monkeypatch):
    hits = [_hit(11), _hit(22)]
    monkeypatch.setattr(md.jamendo_music, "search_tracks",
                        lambda direction, client_id, limit=20: hits)
    captured = {}

    def fake_dl(url, output_path):
        captured["url"] = url
        Path(output_path).write_bytes(b"ID3fake")
        return True

    monkeypatch.setattr(md.jamendo_music, "download_track", fake_dl)
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": ["cello"], "avoid": []},
        {"track_id": "11", "rationale": "grief fits", "runner_up_id": "22"},
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is not None and Path(out).exists()
    assert captured["url"] == "http://x/11.mp3"


def test_select_music_unknown_id_falls_back_to_heuristic(tmp_path, monkeypatch):
    hits = [_hit(11)]
    monkeypatch.setattr(md.jamendo_music, "search_tracks",
                        lambda direction, client_id, limit=20: hits)
    monkeypatch.setattr(md.jamendo_music, "download_track",
                        lambda url, output_path: (Path(output_path).write_bytes(b"ID3x"), True)[1])
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": [], "avoid": []},
        {"track_id": "999", "rationale": "not in list"},  # unknown -> heuristic
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is not None  # heuristic pick_from_pool chose the single hit


def test_select_music_malformed_hit_does_not_raise(tmp_path, monkeypatch):
    # Non-numeric duration makes pick_from_pool's `>= 15` raise TypeError;
    # select_music must swallow it and return None (never raises).
    bad = _hit(11)
    bad["duration"] = "lots"
    monkeypatch.setattr(md.jamendo_music, "search_tracks",
                        lambda direction, client_id, limit=20: [bad])
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": [], "avoid": []},
        {"track_id": "999", "rationale": "not in list"},
    ])
    assert md.select_music(client, _ctx(), "KEY", tmp_path) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_studio_music_director.py -v`
Expected: FAIL (module `music_director` still references `download_music`; `md.jamendo_music` doesn't exist yet).

- [ ] **Step 3: Rewire `studio/music_director.py`**

Change the import block near the top — replace `from src.audio import download_music` with:

```python
from src.audio import jamendo_music
```

Update the module docstring's first line and the two prompt strings to drop "Pixabay" (precise substring replacements — leave all other text unchanged):
- Docstring line 1: replace the substring `forms a Pixabay search\nquery` with `forms a music-library search\nquery`.
- In `_QUERY_ROLE`: replace the substring `Compose ONE Pixabay music search query` with `Compose ONE music search query`.
- In `_RANK_ROLE`: replace the substring `Candidate tracks (from Pixabay; choose` with `Candidate tracks (choose`.

Replace `_tracks_for_prompt` body to use `jamendo_music.extract_meta`:

```python
def _tracks_for_prompt(hits):
    out = []
    for h in hits:
        meta = jamendo_music.extract_meta(h)
        out.append({"id": meta["id"], "tags": meta["tags"],
                    "duration": meta["duration"]})
    return out
```

Replace `select_music` with (Jamendo source; logs attribution; same never-raises contract):

```python
def select_music(client, ctx, api_key, output_dir):
    """compose query -> Jamendo search -> rank -> download. Returns the track
    Path, or None to signal the caller to fall back. Never raises. `api_key` is
    the Jamendo client_id."""
    from pathlib import Path

    if not api_key:
        return None

    try:
        direction = compose_query(client, ctx)
    except Exception as e:  # noqa: BLE001 - never crash a reel
        print(f"  [music-director] query failed ({e})")
        return None

    hits = jamendo_music.search_tracks(direction, api_key, limit=20)
    if not hits:
        print("  [music-director] no Jamendo hits")
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
        try:
            chosen = jamendo_music.pick_from_pool(hits)
        except Exception as e:  # noqa: BLE001 - never crash a reel
            print(f"  [music-director] heuristic fallback failed ({e})")
            chosen = None
    if chosen is None:
        return None

    # Attribution: Jamendo tracks are CC — log artist + license so the human can
    # credit them (auto-attribution in captions is out of scope).
    print(f"  [music-director] track by {chosen.get('artist_name', '?')} "
          f"({chosen.get('license_ccurl', 'CC')})")

    url = jamendo_music.pick_audio_url(chosen)
    if not url:
        print("  [music-director] chosen track has no download URL")
        return None

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"music_director_{ctx.get('mood', 'track')}.mp3"
    if jamendo_music.download_track(url, output_path):
        return output_path
    return None
```

- [ ] **Step 4: Delete the Pixabay module**

```bash
git rm src/audio/download_music.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_studio_music_director.py -v`
Expected: PASS (all).

- [ ] **Step 6: Guard against a stale importer**

Run: `.venv/bin/python -c "import pipeline, studio.music_director, src.video.reel_composer, src.audio.trending_audio; print('imports OK')"`
Expected: prints `imports OK` (no `ModuleNotFoundError` from the deletion).

- [ ] **Step 7: Commit**

```bash
git add studio/music_director.py tests/test_studio_music_director.py
git commit -m "feat(jamendo): rewire Music Director to Jamendo; delete Pixabay module"
```

(`git rm` in Step 4 already staged the deletion.)

---

### Task 4: Swap the pipeline gate to JAMENDO_CLIENT_ID

**Files:**
- Modify: `pipeline.py` (`_select_reel_music`, ~lines 459-478)
- Modify: `tests/test_reel_music_selection.py` (rename the config attr the tests set)

**Interfaces:**
- Consumes: `Config().JAMENDO_CLIENT_ID` (Task 1); `music_director.select_music` (Task 3).
- Produces: `_select_reel_music` gates on `JAMENDO_CLIENT_ID`.

- [ ] **Step 1: Update the tests (RED)**

In `tests/test_reel_music_selection.py`, change the config classes to use `JAMENDO_CLIENT_ID` instead of `PIXABAY_API_KEY`:
- In `class _Cfg`: replace `PIXABAY_API_KEY = ""` with `JAMENDO_CLIENT_ID = ""`.
- In `test_uses_music_director_when_keys_present`'s `class _Cfg2`: replace `PIXABAY_API_KEY = "P"` with `JAMENDO_CLIENT_ID = "P"`.

(Leave the `ANTHROPIC_API_KEY` fields and the rest of both tests unchanged.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_reel_music_selection.py -v`
Expected: FAIL — `_select_reel_music` still reads `PIXABAY_API_KEY`, so `test_uses_music_director_when_keys_present` no longer triggers the agent path.

- [ ] **Step 3: Swap the gate in `pipeline.py`**

In `_select_reel_music`, update the docstring mention and replace both `PIXABAY_API_KEY` references:

Change the guard:
```python
    if getattr(cfg, "PIXABAY_API_KEY", "") and getattr(cfg, "ANTHROPIC_API_KEY", ""):
```
to:
```python
    if getattr(cfg, "JAMENDO_CLIENT_ID", "") and getattr(cfg, "ANTHROPIC_API_KEY", ""):
```

Change the `select_music` call argument:
```python
                music_path = music_director.select_music(
                    client, ctx, cfg.PIXABAY_API_KEY, OUTPUT_DIR)
```
to:
```python
                music_path = music_director.select_music(
                    client, ctx, cfg.JAMENDO_CLIENT_ID, OUTPUT_DIR)
```

Update the docstring's `PIXABAY_API_KEY` wording to `JAMENDO_CLIENT_ID`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reel_music_selection.py -v`
Expected: PASS (both).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `.venv/bin/python -m pytest -q`
Expected: only the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures. If `tests/test_workflow_reliability.py::test_committed_db_has_no_token` fails, run `git checkout -- data/pipeline.db` and re-run.

- [ ] **Step 6: Commit**

```bash
git add pipeline.py tests/test_reel_music_selection.py
git commit -m "feat(jamendo): gate reel music on JAMENDO_CLIENT_ID"
```

---

## Notes for the implementer

- `select_music`'s `api_key` parameter name stays (it now carries the Jamendo client_id) to avoid churn across the agent and its tests.
- The Jamendo `speed` mapping only covers `low`/`medium`/`high` (what `compose_query` emits via `MUSIC_DIRECTION_SCHEMA`'s `energy` enum); anything else defaults to `medium`.
- End-to-end manual check (optional, needs `JAMENDO_CLIENT_ID` in `.env`): `.venv/bin/python pipeline.py --remotion --dry-run` and look for `[music-director] picked …` + `[jamendo] Saved …`; without the key you should see the mood-music log instead.
- **Deliberate spec simplification:** the spec's Component 2 "Lightweight cache" (novelty + attribution record) is intentionally omitted (YAGNI) — it would be write-only (nothing reads it: `pick_from_pool` doesn't consult it, and the agent already varies its pick by reel content). The licensing/attribution goal is met instead by the `[music-director] track by <artist> (<license>)` log line in `select_music` (Task 3). If a persisted attribution ledger is later wanted, add it as a follow-up.
