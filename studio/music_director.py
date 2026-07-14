"""Music Director agent — a music-supervisor persona that forms a music-library search
query from a reel's content and ranks the returned tracks by emotional fit.

Two LLM calls (role ``music_director``): ``compose_query`` then ``rank_tracks``.
The orchestrator ``select_music`` (Task 3) chains them with the Jamendo source
in ``src/audio/jamendo_music.py`` and degrades gracefully.
"""
import json

from studio.types import (
    MusicDirection, MUSIC_DIRECTION_SCHEMA,
    MusicPick, MUSIC_PICK_SCHEMA,
)
from src.audio import jamendo_music
from src.optimizer import prompt_store

_PREFIX = (
    "You are a music supervisor with 10 years scoring short-form video for a "
    "stoic-philosophy Instagram account. You choose instrumental, royalty-free "
    "music that matches the emotional arc of a spoken quote and sits well under "
    "a slow, deep narration — never fighting the voice."
)

_QUERY_ROLE_DEFAULT = (
    "Reel content:\n{ctx}\n"
    "Compose ONE music search query (2-5 words, instrumental) plus the "
    "target energy, bpm range, instruments to feature, and things to avoid. Match "
    "the quote's emotion, not just the mood label. Output a MusicDirection as JSON only."
)

_RANK_ROLE_DEFAULT = (
    "Reel content:\n{ctx}\n"
    "Candidate tracks (choose the single best emotional fit):\n{tracks}\n"
    "Pick track_id (it MUST be one of the listed ids). Give a one-line rationale and "
    "an optional runner_up_id. Prefer 15-40s instrumental beds that won't fight a slow "
    "deep voice. Output a MusicPick as JSON only."
)

# Backward-compat aliases.
_QUERY_ROLE = _QUERY_ROLE_DEFAULT
_RANK_ROLE = _RANK_ROLE_DEFAULT


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
    tmpl = prompt_store.get("prompt.music_director.query", _QUERY_ROLE_DEFAULT)
    role = tmpl.format(ctx=_ctx_json(ctx))
    d = client.call("music_director", _PREFIX, role,
                    "Compose the music direction now.", MUSIC_DIRECTION_SCHEMA)
    return MusicDirection.from_dict(d)


def _tracks_for_prompt(hits):
    out = []
    for h in hits:
        meta = jamendo_music.extract_meta(h)
        out.append({"id": meta["id"], "tags": meta["tags"],
                    "duration": meta["duration"]})
    return out


def rank_tracks(client, ctx, hits) -> MusicPick:
    tmpl = prompt_store.get("prompt.music_director.rank", _RANK_ROLE_DEFAULT)
    role = tmpl.format(ctx=_ctx_json(ctx),
                       tracks=json.dumps(_tracks_for_prompt(hits), indent=2))
    d = client.call("music_director", _PREFIX, role,
                    "Pick the best track now.", MUSIC_PICK_SCHEMA)
    return MusicPick.from_dict(d)


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
