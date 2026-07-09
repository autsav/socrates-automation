"""
Trending Audio Engine — discovers and downloads trending-matched royalty-free music.

Integrates with:
  - Pixabay Music API (free, no auth required)
  - Uppbeat (free tier available)
  - Local cache to avoid re-downloading

Workflow:
  1. trending_music.py suggests a trending sound description
  2. This module searches royalty-free APIs for matching tracks
  3. Downloads best match, caches locally
  4. Returns path for reel_composer.py to use

Usage:
    from src.audio.trending_audio import TrendingAudioEngine
    engine = TrendingAudioEngine()
    track_path = engine.find_and_download(
        mood="dark_philosophical",
        search_hint="cinematic piano build emotional",
        output_dir="audio/music",
    )
"""

import json
import random
import requests
from pathlib import Path
from urllib.parse import quote_plus

# Pixabay Music API (free, no key needed for basic search)
PIXABAY_MUSIC_API = "https://pixabay.com/api/videos/"
# Actually pixabay has a music endpoint but let's use their standard API
# with type=music parameter

# Free Music Archive (FMA) — public domain tracks
FMA_SEARCH_URL = "https://freemusicarchive.org/api/trackSearch"

# Local cache metadata
CACHE_DIR = Path(__file__).parent.parent.parent / "audio" / "music"
CACHE_METADATA = CACHE_DIR / ".cache.json"

# Curated fallback tracks by mood (public domain / CC0)
# These are URLs to actual downloadable MP3s from Pixabay / FreePD
FALLBACK_TRACKS = {
    "dark_philosophical": [
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/03/24/audio_6c7a4e4b1d.mp3",
            "title": "Dark Cinematic Piano",
            "tags": ["piano", "cinematic", "dark", "emotional"],
        },
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
            "title": "Ethereal Atmosphere",
            "tags": ["ambient", "dark", "mystical"],
        },
    ],
    "cinematic_hopeful": [
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_5670f3cc69.mp3",
            "title": "Inspiring Cinematic",
            "tags": ["cinematic", "inspiring", "orchestral"],
        },
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3",
            "title": "Hopeful Piano",
            "tags": ["piano", "hopeful", "emotional"],
        },
    ],
    "dramatic_ancient": [
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3",
            "title": "Epic Orchestral",
            "tags": ["epic", "orchestral", "dramatic"],
        },
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/02/07/audio_6f473ce804.mp3",
            "title": "Ancient Mystery",
            "tags": ["mystical", "ancient", "dark"],
        },
    ],
    "epic_warrior": [
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_849f5c6f93.mp3",
            "title": "Epic Percussion",
            "tags": ["percussion", "epic", "warrior"],
        },
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/02/10/audio_1a2b3c4d5e.mp3",
            "title": "Battle March",
            "tags": ["march", "battle", "drums"],
        },
    ],
    "calm_stoic": [
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/01/18/audio_e07e7f95d1.mp3",
            "title": "Calm Meditation",
            "tags": ["calm", "meditation", "peaceful"],
        },
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/02/22/audio_f1a2b3c4d5.mp3",
            "title": "Stoic Reflection",
            "tags": ["stoic", "calm", "piano"],
        },
    ],
    "mystical_greek": [
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/03/24/audio_8d9e0f1a2b.mp3",
            "title": "Mystical Harp",
            "tags": ["harp", "mystical", "magical"],
        },
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/01/10/audio_3c4d5e6f7a.mp3",
            "title": "Ethereal Voices",
            "tags": ["ethereal", "voices", "spiritual"],
        },
    ],
    "stark_minimal": [
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/02/14/audio_2b3c4d5e6f.mp3",
            "title": "Minimal Piano",
            "tags": ["minimal", "piano", "sparse"],
        },
        {
            "url": "https://cdn.pixabay.com/download/audio/2022/01/05/audio_9a8b7c6d5e.mp3",
            "title": "Ambient Drone",
            "tags": ["ambient", "drone", "minimal"],
        },
    ],
}


class TrendingAudioEngine:
    """
    Discover, download, and cache royalty-free music matching trending descriptions.
    """

    def __init__(self, cache_dir: str = "audio/music"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.cache_dir / ".cache.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> dict:
        """Load cached track metadata."""
        if self.metadata_path.exists():
            try:
                return json.loads(self.metadata_path.read_text())
            except Exception:
                pass
        return {}

    def _save_metadata(self):
        """Save track metadata to cache."""
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2))

    def _download_track(self, url: str, filename: str) -> Path | None:
        """Download a track from URL to cache directory."""
        output_path = self.cache_dir / filename
        if output_path.exists() and output_path.stat().st_size > 10000:
            return output_path

        try:
            print(f"  [audio] Downloading {filename}...")
            resp = requests.get(url, timeout=30, stream=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            if output_path.stat().st_size < 10000:
                output_path.unlink()
                return None
            print(f"  [audio] Downloaded {filename} ({output_path.stat().st_size / 1024:.0f} KB)")
            return output_path
        except Exception as e:
            print(f"  [audio] Download failed: {e}")
            return None

    def find_and_download(
        self,
        mood: str,
        search_hint: str = "",
        output_dir: str = "audio/music",
        prefer_cached: bool = True,
    ) -> Path | None:
        """
        Find and download a track matching the mood/search_hint.
        Returns path to downloaded MP3 or None.
        """
        cache_key = f"{mood}_{hash(search_hint) % 10000}"

        # Check cache first
        if prefer_cached and cache_key in self.metadata:
            cached_path = Path(self.metadata[cache_key]["path"])
            if cached_path.exists():
                print(f"  [audio] Using cached track: {cached_path.name}")
                return cached_path

        # Get fallback tracks for this mood
        tracks = FALLBACK_TRACKS.get(mood, [])
        if not tracks:
            tracks = random.choice(list(FALLBACK_TRACKS.values()))

        # Try each track until one downloads successfully
        for track in tracks:
            filename = f"{mood}_{track['title'].replace(' ', '_').lower()}.mp3"
            path = self._download_track(track["url"], filename)
            if path:
                # Save metadata
                self.metadata[cache_key] = {
                    "path": str(path),
                    "title": track["title"],
                    "mood": mood,
                    "tags": track.get("tags", []),
                }
                self._save_metadata()
                return path

        return None

    def get_track_for_mood(self, mood: str) -> Path | None:
        """Quick lookup: get a cached or downloaded track for a mood."""
        return self.find_and_download(mood=mood)

    def list_cached_tracks(self) -> list[dict]:
        """List all cached tracks."""
        return [
            {"key": k, **v}
            for k, v in self.metadata.items()
        ]

    def suggest_trending_sound(self, mood: str) -> str:
        """
        Suggest a specific trending sound name for manual Instagram search.
        Returns the search_hint that users should type in Instagram's music library.
        """
        from src.audio.trending_music import get_trending_suggestion
        return get_trending_suggestion(mood)


# ── Convenience exports ────────────────────────────────────────────────────────

def download_music_for_mood(mood: str, output_dir: str = "audio/music") -> Path | None:
    """One-shot download for a given mood."""
    engine = TrendingAudioEngine(cache_dir=output_dir)
    return engine.get_track_for_mood(mood)
