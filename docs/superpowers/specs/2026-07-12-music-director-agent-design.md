# Music Director agent — content-aware music selection

Date: 2026-07-12
Status: Approved

## Goal

Add a "Music Director" reasoning agent (persona: 10 years scoring short-form
video) that picks the music track which best fits a reel's emotional content —
its quote, hook, and mood — instead of the current flat mood→track lookup.

Music source: **Pixabay live search** (royalty-free), reusing the existing
`src/audio/download_music.py` plumbing. The agent adds the intelligence the
current pipeline lacks: forming a smart search query from the reel content, and
ranking the returned tracks by emotional fit (today `_score_track` ranks only on
duration / novelty / popularity — never on whether the music suits the words).

## Trigger

Runs for **every reel**, **studio-aware**: always attempted when
`PIXABAY_API_KEY` and `ANTHROPIC_API_KEY` are set; uses the richer `--studio`
creative decision (theme/angle) as query context when available, otherwise
quote + hook + mood. Degrades gracefully (see Fallback) — never blocks a reel.

## Components

### `studio/music_director.py` (new — mirrors `studio/director.py`)

Persona `_ROLE`: a music supervisor with 10 years scoring short-form video,
choosing a track that matches the emotional arc of the quote and reads well
under a slow, deep narration.

- `compose_query(client, ctx) -> MusicDirection` — **LLM call 1** (role
  `music_director`). Input: quote, hook, mood, optional studio theme/angle.
  Output: `search_query`, `energy` (low/medium/high), `bpm_range` [min,max],
  `instruments` [..], `avoid` [..].
- `rank_tracks(client, ctx, hits) -> MusicPick` — **LLM call 2**. Input: the
  reel ctx + a compact list of Pixabay hit metadata (id, tags/title, duration).
  Output: `track_id` (must be one of the given ids), `rationale`, `runner_up_id`.
- `select_music(client, ctx, api_key, output_dir) -> Path | None` — orchestrates
  call 1 → Pixabay search → call 2 → download+validate; returns the track path
  or `None` to signal the caller should fall back.

### `studio/types.py` (extend)

`MusicDirection` and `MusicPick` dataclasses with `to_dict`/`from_dict` and
`MUSIC_DIRECTION_SCHEMA` / `MUSIC_PICK_SCHEMA` JSON schemas (same style as
`Decision` / `DECISION_SCHEMA`).

### `studio/settings.py` (extend)

`music_director` already-anticipated audio role → add to `ROLE_MODELS`
(`claude-sonnet-4-6`) and `ROLE_EFFORT` (`medium`). (The unused `audio_engineer`
slot stays as-is; we use a clearly-named `music_director` role.)

### `pipeline.py` `_run_pov_reel` (integrate)

Replace the flat `download_music_for_mood(mood)` call with:

```
ctx = {"quote": ..., "hook": hook_text, "mood": mood,
       "studio": studio_decision_context_or_None}
music_path = None
if cfg.PIXABAY_API_KEY and cfg.ANTHROPIC_API_KEY:
    try:
        music_path = music_director.select_music(client, ctx,
                                                  cfg.PIXABAY_API_KEY, OUTPUT_DIR)
    except Exception as e:
        log.warning("[music-director] failed (%s) — falling back", e)
if music_path is None:
    music_path = download_music_for_mood(mood)   # existing behaviour
```

`client` is a `StudioClient` (built once; shares the daily spend ceiling).

## Data flow

```
reel content ──> compose_query (LLM1) ──> MusicDirection.search_query
                                             │
             download_music._search_pixabay_music(query, key, per_page=20)
                                             │  hits[]
reel content + hits ──> rank_tracks (LLM2) ──> MusicPick.track_id
                                             │
             download + _validate_audio_file(chosen hit) ──> music bed .mp3
```

## Fallback chain (never crashes a reel)

`missing key` → `compose_query error` → `empty hits` → `rank returns unknown
id` → `download/validate fail` ⟶ existing `download_music_for_mood(mood)` ⟶
local synthesized ambient track. Each step logs and continues.

If `rank_tracks` returns a `track_id` not in `hits`, fall back to the existing
heuristic `_score_track` over the same hits before giving up.

## Cost / budget

Two `claude-sonnet-4-6` calls per reel, gated by the existing
`DAILY_SPEND_CEILING_USD` in `StudioClient` (`over_daily_ceiling()` → skip →
fallback). Reuses the existing Pixabay novelty cache so a track is not repeated
within 3 days.

## Out of scope (YAGNI)

- Audio-content analysis of tracks (BPM/key detection). The agent ranks on
  Pixabay metadata only — we cannot stream audio into the model.
- Replacing the manual trending-audio workflow. Manual reels still go to
  Telegram for the human to add trending audio; the Director's pick is the baked
  bed under the VO for auto-posted reels and the manual preview.
- Multi-query fan-out. One query → one search → one ranked pick.

## Testing

- `compose_query` / `rank_tracks`: mock `StudioClient.call` (as existing studio
  tests do); assert schema-valid `MusicDirection` / `MusicPick` and that
  `rank_tracks` only returns an id present in the hits.
- `select_music` fallback: stub `_search_pixabay_music` to return `[]` → returns
  `None`; unknown `track_id` → heuristic `_score_track` pick; download failure →
  `None`.
- Integration: `_run_pov_reel` falls back to `download_music_for_mood` when
  `PIXABAY_API_KEY` is unset (no agent calls made).
