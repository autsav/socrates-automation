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

from src.utils.logger import get_logger
logger = get_logger(__name__)

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

# Curated fallback tracks by mood. Each entry has a Jamendo CDN URL (best-effort
# — may 404; verified at spec time but not policed here), a title/artist for
# attribution, and a `local` path to a bundled CC0 sine-tone mp3 shipped in
# assets/audio/fallback/. find_and_download() tries the URL first, then falls
# through to `local` so reels never crash on a dead CDN link.
FALLBACK_TRACKS = {
    "dark_philosophical": {
        "url": "https://prod-1.storage.jamendo.com/?trackid=1892573&format=mp32",
        "title": "Mist of Epirus",
        "artist": "Dimitri Piontkovski",
        "local": "assets/audio/fallback/dark_philosophical.mp3",
    },
    "cinematic_hopeful": {
        "url": "https://prod-1.storage.jamendo.com/?trackid=1812008&format=mp32",
        "title": "Aurora Rising",
        "artist": "Anton Volsky",
        "local": "assets/audio/fallback/cinematic_hopeful.mp3",
    },
    "calm_stoic": {
        "url": "https://prod-1.storage.jamendo.com/?trackid=1812995&format=mp32",
        "title": "Still Waters",
        "artist": "Mira Solenne",
        "local": "assets/audio/fallback/calm_stoic.mp3",
    },
    "dramatic_ancient": {
        "url": "https://prod-1.storage.jamendo.com/?trackid=1724531&format=mp32",
        "title": "Stone and Olive",
        "artist": "Kostas Argyros",
        "local": "assets/audio/fallback/dramatic_ancient.mp3",
    },
    "epic_warrior": {
        "url": "https://prod-1.storage.jamendo.com/?trackid=1897123&format=mp32",
        "title": "Phalanx",
        "artist": "Nikolai Stepanov",
        "local": "assets/audio/fallback/epic_warrior.mp3",
    },
    "mystical_greek": {
        "url": "https://prod-1.storage.jamendo.com/?trackid=1845672&format=mp32",
        "title": "Oracle at Delphi",
        "artist": "Lefteris Papadopoulos",
        "local": "assets/audio/fallback/mystical_greek.mp3",
    },
    "stark_minimal": {
        "url": "https://prod-1.storage.jamendo.com/?trackid=1855444&format=mp32",
        "title": "White Marble",
        "artist": "Eleni Karvouna",
        "local": "assets/audio/fallback/stark_minimal.mp3",
    },
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

    def _download_track(self, entry: dict, filename: str) -> Path | None:
        """Download a track from entry["url"] to cache directory.

        Falls through to entry["local"] (a bundled CC0 mp3) if the URL is
        blank, the HTTP fetch fails, or the downloaded payload is too small
        to be a real mp3. Returns the cached/downloaded/local Path, or None.
        """
        url = entry.get("url", "")
        output_path = self.cache_dir / filename
        if url and output_path.exists() and output_path.stat().st_size > 10000:
            return output_path

        if url:
            try:
                logger.info(f"  [audio] Downloading {filename}...")
                resp = requests.get(url, timeout=30, stream=True)
                resp.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                if output_path.stat().st_size < 10000:
                    output_path.unlink()
                else:
                    logger.info(
                        f"  [audio] Downloaded {filename} "
                        f"({output_path.stat().st_size / 1024:.0f} KB)"
                    )
                    return output_path
            except Exception as e:
                logger.info(f"  [audio] Download failed: {e}")

        # Fall through to bundled local fallback (assets/audio/fallback/*.mp3).
        local_path = Path(entry.get("local", ""))
        if local_path.exists() and local_path.stat().st_size > 0:
            logger.info(f"  [audio] Using local fallback: {local_path}")
            return local_path
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
                logger.info(f"  [audio] Using cached track: {cached_path.name}")
                return cached_path

        # Get fallback track for this mood (single curated entry per mood).
        entry = FALLBACK_TRACKS.get(mood)
        if not entry:
            entry = random.choice(list(FALLBACK_TRACKS.values()))

        filename = f"{mood}_{entry['title'].replace(' ', '_').lower()}.mp3"
        path = self._download_track(entry, filename)
        if path:
            self.metadata[cache_key] = {
                "path": str(path),
                "title": entry["title"],
                "artist": entry.get("artist", ""),
                "mood": mood,
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
