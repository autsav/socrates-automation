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
