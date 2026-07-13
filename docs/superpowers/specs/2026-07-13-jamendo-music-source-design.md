# Jamendo music-source swap

Date: 2026-07-13
Status: Approved

## Goal

Replace the Music Director's dead music source (Pixabay has no public music API —
`https://pixabay.com/api/music/` returns 404) with the **Jamendo API**, which is
real, free, and returns instrumental, downloadable, CC-licensed tracks. The
reasoning agent (`compose_query` / `rank_tracks`) is unchanged; only the source
layer swaps. The now-unused Pixabay module is deleted.

## Prerequisite (done)

`JAMENDO_CLIENT_ID` is set in `.env` (gitignored). Validated live against
`https://api.jamendo.com/v3.0/tracks/` — key returns instrumental results.

## Key API facts (verified)

- `GET https://api.jamendo.com/v3.0/tracks/` — params: `client_id`, `format=json`,
  `limit` (max 200), `fuzzytags` (OR-match tags), `vocalinstrumental=instrumental`,
  `speed` (`verylow`..`veryhigh`), `include=musicinfo`.
- Each result has `id`, `name`, `duration`, `audio` (stream), `audiodownload`
  (download URL), `audiodownload_allowed` (bool), `license_ccurl`, `artist_name`.
- **The server-side `audiodownloadallowed` query param is unreliable** (returns
  non-downloadable tracks anyway) → we MUST post-filter hits on
  `audiodownload_allowed == True` in code.
- Tracks are full-length (3–6 min); fine — only the reel's first ~9 s is heard as
  the bed, so no trimming needed.

## Components

### 1. `config.py` + `.env.example`
Add `JAMENDO_CLIENT_ID` (optional string, default `""`), same pattern as
`PIXABAY_API_KEY`. Add a placeholder line to `.env.example`.

### 2. New module `src/audio/jamendo_music.py` (self-contained source)
Self-contained because `src/audio/download_music.py` is deleted (Component 5),
taking its shared helpers with it.

- `search_tracks(direction, client_id, limit=20) -> list[dict]` — builds the
  Jamendo query from a `MusicDirection`:
  - `fuzzytags` = whitespace→`+` of `direction.search_query`
  - `vocalinstrumental=instrumental` (always — no vocals under the sage VO)
  - `speed` mapped from `direction.energy` (`low`→`low`, `medium`→`medium`,
    `high`→`high`)
  - `format=json`, `limit`, `include=musicinfo`
  - HTTP via `requests` (timeout 15); on any error returns `[]`
  - **Post-filters** the returned hits to `audiodownload_allowed == True`.
- `extract_meta(hit) -> dict` → `{id, name, tags, duration}` for the ranking prompt
  (tags from `hit["musicinfo"]["tags"]` when present, else `name`).
- `pick_audio_url(hit) -> str | None` → `hit["audiodownload"]` when
  `audiodownload_allowed` and it is an http URL, else `None`.
- `download_track(url, output_path) -> bool` → GET + write + `_validate_audio_file`
  (validation: size floor + MP3 magic bytes; ported from the deleted module).
- `pick_from_pool(hits) -> dict | None` → minimal heuristic fallback: keep hits
  with a valid `audiodownload_allowed`, prefer duration ≥ 15 s, return the first;
  `None` if none usable.
- Lightweight cache (`_load_cache`/`_save_cache` in `audio/music/.jamendo.json`):
  records `{track_id, artist_name, license_ccurl, last_used}` for the chosen track
  — supports the licensing caveat and light novelty; failures are non-fatal.

### 3. `studio/music_director.py` — swap the source
`select_music` and `_tracks_for_prompt` call `jamendo_music.*` instead of
`download_music.*`:
- `_tracks_for_prompt` → `jamendo_music.extract_meta`
- search → `jamendo_music.search_tracks(direction, client_id, limit=20)`
- heuristic fallback → `jamendo_music.pick_from_pool(hits)`
- url → `jamendo_music.pick_audio_url(chosen)`
- download → `jamendo_music.download_track(url, output_path)`

`compose_query` and `rank_tracks` (the LLM calls) are untouched. `select_music`
keeps its signature `(client, ctx, api_key, output_dir) -> Path | None` and its
never-raises contract; `api_key` now carries the Jamendo client_id.

### 4. `pipeline._select_reel_music` — swap the gate
Gate the agent path on `cfg.JAMENDO_CLIENT_ID` (+ `cfg.ANTHROPIC_API_KEY`) instead
of `cfg.PIXABAY_API_KEY`; pass `cfg.JAMENDO_CLIENT_ID` as the `api_key` arg.
Fallback to `download_music_for_mood(mood)` (the `trending_audio` mood bed)
unchanged. Never raises.

### 5. Delete `src/audio/download_music.py`
Verified the only importer is `studio/music_director.py` (rewired in Component 3);
`reel_composer` and `trending_audio` use their own `download_music_for_mood`.
Delete the module. (Its generic download/validate logic is ported into
`jamendo_music.py`.)

## Data flow (shape unchanged)

```
reel ctx ─ compose_query (LLM1) ─▶ MusicDirection
                                     │
      jamendo_music.search_tracks(direction, client_id)  ─▶ hits (dl-allowed only)
                                     │
reel ctx + hits ─ rank_tracks (LLM2) ─▶ MusicPick.track_id
                                     │
      jamendo_music.pick_audio_url ▶ download_track ─▶ music bed .mp3
```

## Fallback chain (never crashes a reel)

`no client_id` → `compose_query error` → `no hits (or none dl-allowed)` →
`rank error / unknown id` (→ `jamendo_music.pick_from_pool`) → `no download URL`
→ `download fail` ⟶ `download_music_for_mood(mood)` ⟶ local synth bed. Each step
logs and continues.

## Licensing caveat (flagged, not automated)

Jamendo tracks are CC (mostly CC-BY), which for commercial use wants artist
attribution. `jamendo_music` records `artist_name` + `license_ccurl` in its cache
and logs them on selection so attribution is possible. Automating
attribution-in-caption is OUT OF SCOPE.

## Out of scope (YAGNI)

- Trimming tracks to reel length (Remotion truncates the bed to the reel).
- Attribution-in-caption automation.
- A `download_all_music`-style batch prefetch (the deleted module had one; not
  needed for the on-demand agent).

## Testing

- `search_tracks`: monkeypatch `requests.get` to return a canned Jamendo JSON
  body → assert the request used `vocalinstrumental=instrumental` and the mapped
  `speed`/`fuzzytags`, and that a hit with `audiodownload_allowed=false` is
  filtered out of the result.
- `pick_audio_url`: returns the URL only when `audiodownload_allowed`; `None`
  otherwise.
- `download_track`: monkeypatch `requests.get` → writes file, validates, returns
  bool.
- `select_music` (in `tests/test_studio_music_director.py`, updated from the
  Pixabay monkeypatches to `jamendo_music.*`): no key → None; no hits → None;
  agent pick downloaded; unknown id → heuristic `pick_from_pool`; download fail →
  None. Never raises (malformed hit test retained).
- `pipeline._select_reel_music`: no `JAMENDO_CLIENT_ID` → agent not called, mood
  fallback used; keys present → agent path used.
- Full suite green except the 2 pre-existing `tests/test_reel_composer.py` ffmpeg
  failures.
