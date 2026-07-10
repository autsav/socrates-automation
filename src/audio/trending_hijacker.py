"""
Trending Audio Hijacker — rides Instagram's trending Reels sounds.

Instagram's algorithm pushes trending-audio content to non-followers, making
this the #1 reach multiplier for Reels. Instagram does not expose a public
API for trending sounds, so this module maintains a small JSON file
(data/trending_audio.json) that's updated manually on a weekly cadence, and
matches those tracks to content moods.

Each entry:
    {
      "track_name": "...",
      "artist": "...",
      "instagram_audio_id": "...",   # from the trending sound's IG share URL
      "mood_match": ["dark_philosophical", "epic_warrior"],
      "download_url": "https://...", # optional — direct royalty-free/licensed audio
      "date_added": "2026-07-01"
    }

If a track has no usable download_url (or the download fails), this module
falls back to the existing generated-ambient pipeline so a Reel is never
blocked on audio.

Usage:
    from src.audio.trending_hijacker import TrendingHijacker, get_audio_for_mood

    hijacker = TrendingHijacker()
    track = hijacker.match_mood("dark_philosophical")
    path = hijacker.get_track_path("dark_philosophical")
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import requests

DATA_PATH = Path(__file__).parent.parent.parent / "data" / "trending_audio.json"
CACHE_DIR = Path(__file__).parent.parent.parent / "audio" / "music" / "trending"

REQUIRED_FIELDS = ("track_name", "artist", "instagram_audio_id", "mood_match", "download_url", "date_added")


def _default_list() -> list[dict]:
    """Seed list — replace/extend weekly with real trending sounds observed
    on Instagram's Reels 'Trending' audio shelf. download_url intentionally
    blank until a verified royalty-free/licensed source is wired up; the
    engine falls back to generated ambient audio when blank."""
    return [
        {
            "track_name": "Dark Cinematic Build",
            "artist": "unknown",
            "instagram_audio_id": "",
            "mood_match": ["dark_philosophical", "dramatic_ancient"],
            "download_url": "",
            "date_added": "2026-07-01",
        },
        {
            "track_name": "Hopeful Piano Rise",
            "artist": "unknown",
            "instagram_audio_id": "",
            "mood_match": ["cinematic_hopeful", "calm_stoic"],
            "download_url": "",
            "date_added": "2026-07-01",
        },
        {
            "track_name": "Epic Percussion Hit",
            "artist": "unknown",
            "instagram_audio_id": "",
            "mood_match": ["epic_warrior", "dramatic_ancient"],
            "download_url": "",
            "date_added": "2026-07-01",
        },
        {
            "track_name": "Mystic Ambient Drift",
            "artist": "unknown",
            "instagram_audio_id": "",
            "mood_match": ["mystical_greek", "stark_minimal"],
            "download_url": "",
            "date_added": "2026-07-01",
        },
    ]


def load_trending_list(path: str | Path = DATA_PATH) -> list[dict]:
    """Load the weekly trending-audio JSON. Creates a seed file if missing."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        seed = _default_list()
        path.write_text(json.dumps(seed, indent=2))
        return seed
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return _default_list()


def save_trending_list(tracks: list[dict], path: str | Path = DATA_PATH) -> None:
    """Persist the trending-audio list (used when adding/updating tracks)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tracks, indent=2))


def add_track(
    track_name: str,
    artist: str,
    mood_match: list[str],
    instagram_audio_id: str = "",
    download_url: str = "",
    date_added: str = "",
    path: str | Path = DATA_PATH,
) -> list[dict]:
    """Append a newly-observed trending track to the weekly list and save it."""
    tracks = load_trending_list(path)
    tracks.append({
        "track_name": track_name,
        "artist": artist,
        "instagram_audio_id": instagram_audio_id,
        "mood_match": mood_match,
        "download_url": download_url,
        "date_added": date_added,
    })
    save_trending_list(tracks, path)
    return tracks


class TrendingHijacker:
    """Matches trending Instagram audio to content moods and resolves a
    local, playable audio file for the video pipeline."""

    def __init__(self, data_path: str | Path = DATA_PATH, cache_dir: str | Path = CACHE_DIR):
        self.data_path = Path(data_path)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.tracks = load_trending_list(self.data_path)

    def tracks_for_mood(self, mood: str) -> list[dict]:
        """All trending tracks tagged for the given mood."""
        return [t for t in self.tracks if mood in t.get("mood_match", [])]

    def match_mood(self, mood: str, seed: int = 0) -> dict | None:
        """Pick one trending track matching the mood, deterministically by seed."""
        candidates = self.tracks_for_mood(mood)
        if not candidates:
            return None
        if seed:
            random.seed(seed)
            return random.choice(candidates)
        return candidates[0]

    def _download(self, track: dict) -> Path | None:
        url = track.get("download_url", "")
        if not url:
            return None
        filename = f"{track['track_name'].replace(' ', '_').lower()}.mp3"
        output_path = self.cache_dir / filename
        if output_path.exists() and output_path.stat().st_size > 10000:
            return output_path
        try:
            resp = requests.get(url, timeout=30, stream=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            if output_path.stat().st_size < 10000:
                output_path.unlink(missing_ok=True)
                return None
            return output_path
        except Exception as e:
            print(f"  [trending-audio] Download failed for {track['track_name']}: {e}")
            return None

    def get_track_path(self, mood: str, seed: int = 0) -> Path | None:
        """
        Resolve a playable local audio file for the mood:
        1. Best matching trending track (downloaded if it has a URL).
        2. Fall back to the generated-ambient audio pipeline.
        3. None if nothing is available (caller should treat as silent).
        """
        track = self.match_mood(mood, seed=seed)
        if track:
            downloaded = self._download(track)
            if downloaded:
                return downloaded

        try:
            from src.audio.trending_audio import download_music_for_mood
            fallback = download_music_for_mood(mood)
            if fallback and Path(fallback).exists():
                return Path(fallback)
        except Exception:
            pass

        try:
            from generate_audio import prepare_reel_audio
            fallback = prepare_reel_audio(mood, target_duration=15.0, output_dir=str(self.cache_dir))
            if fallback and Path(fallback).exists():
                return Path(fallback)
        except Exception:
            pass

        return None

    def suggest_for_manual_posting(self, mood: str) -> str:
        """Human-readable suggestion for manually attaching the trending
        sound in Instagram's own Reel editor (audio can't be auto-attached
        via the Graph API)."""
        track = self.match_mood(mood)
        if track and track.get("track_name"):
            artist = f" — {track['artist']}" if track.get("artist") else ""
            return f"Use trending sound: {track['track_name']}{artist}"
        return "No trending sound matched — use any trending audio for this mood."


# ── Convenience exports ──────────────────────────────────────────────────

def get_audio_for_mood(mood: str, seed: int = 0) -> Path | None:
    """One-shot: resolve a local audio file for the given mood."""
    return TrendingHijacker().get_track_path(mood, seed=seed)
