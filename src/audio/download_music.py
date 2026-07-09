"""
Music Downloader — fetches royalty-free instrumental music from Pixabay Music API.

THREE STRATEGIES:
1. Mood-matched tracks  — cinematic/epic/calm tracks baked into MP4 (always works)
2. Trending-vibe tracks — tracks matching the ENERGY of currently trending Instagram
   audio (upbeat, dramatic, emotional, minimal) for maximum algorithmic boost
3. Weekly rotation pool — picks from top-N hits to avoid repetitive audio

TRENDING AUDIO NOTE:
Instagram's Content Publishing API does not allow attaching trending audio IDs
to videos uploaded via API (only available in-app). The workaround: download
royalty-free tracks that match the vibe/energy of trending sounds. This gives
the emotional hook of trending music while staying within API limits.

Pixabay Music API: https://pixabay.com/api/docs/#api_music
PIXABAY_API_KEY required (free at pixabay.com)
"""

import os
import time
import random
import json
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timedelta

MUSIC_DIR = Path(__file__).parent.parent.parent / "audio" / "music"
PIXABAY_MUSIC_API = "https://pixabay.com/api/music/"
CACHE_FILE = MUSIC_DIR / ".track_cache.json"

# ── Mood → search terms ────────────────────────────────────────────────────────
MOOD_SEARCH = {
    "calm_stoic":         "calm piano ambient meditation",
    "cinematic_hopeful":  "cinematic orchestral hopeful uplifting",
    "dark_philosophical": "dark atmospheric cello contemplative",
    "dramatic_ancient":   "epic percussion dramatic powerful",
    "epic_warrior":       "battle epic brass powerful",
    "mystical_greek":     "ethereal mystical harp ambient",
    "stark_minimal":      "minimal piano sparse instrumental",
}

# ── Trending vibe map ─────────────────────────────────────────────────────────
# Research: Instagram trends in May/Jun 2026 favour these energy profiles.
# Maps trending-vibe name → Pixabay search terms + BPM hints.
# Updated manually when Instagram trends shift (every ~4-6 weeks).
TRENDING_VIBES = {
    "upbeat_energetic":   "upbeat energetic pop happy 120bpm",
    "dramatic_cinematic": "cinematic dramatic orchestral emotional",
    "nostalgic_warm":     "nostalgic warm retro lo-fi cozy",
    "emotional_build":    "emotional build piano strings crescendo",
    "minimalist_focus":   "minimal clean focus productivity ambient",
}

# Which trending vibe fits each mood best
MOOD_TO_TRENDING_VIBE = {
    "calm_stoic":         "minimalist_focus",
    "cinematic_hopeful":  "emotional_build",
    "dark_philosophical": "dramatic_cinematic",
    "dramatic_ancient":   "dramatic_cinematic",
    "epic_warrior":       "upbeat_energetic",
    "mystical_greek":     "emotional_build",
    "stark_minimal":      "minimalist_focus",
}


def _load_cache() -> dict:
    """Load track metadata cache from disk."""
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"tracks": {}, "last_refresh": None, "weekly_pool": {}}


def _save_cache(cache: dict) -> None:
    """Save track metadata cache to disk."""
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2, default=str), encoding="utf-8")


def _search_pixabay_music(query: str, api_key: str, per_page: int = 10) -> list[dict]:
    """Search Pixabay Music API. Returns list of hit dicts."""
    try:
        resp = requests.get(
            PIXABAY_MUSIC_API,
            params={"key": api_key, "q": query, "per_page": per_page},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("hits", [])
    except Exception as e:
        print(f"  [music] Search error ({query[:30]}): {e}")
        return []


def _extract_track_meta(hit: dict) -> dict:
    """Extract useful metadata from a Pixabay hit."""
    return {
        "id": hit.get("id"),
        "title": hit.get("tags", "")[:40] if hit.get("tags") else "Unknown",
        "tags": hit.get("tags", ""),
        "user": hit.get("user", ""),
        "duration": hit.get("duration"),
        "preview": hit.get("previewURL", ""),
        "audio": hit.get("audio", ""),
        "audioURL": hit.get("audioURL", ""),
    }


def _pick_audio_url(hit: dict) -> str | None:
    """Extract the best downloadable audio URL from a Pixabay hit."""
    # Pixabay music API returns the direct download in these fields
    for field in ("audio", "audioURL"):
        url = hit.get(field, "")
        if url and isinstance(url, str) and url.startswith("http"):
            return url
    # Fallback: try preview URL if it's a direct audio link
    preview = hit.get("previewURL", "")
    if preview and isinstance(preview, str) and preview.startswith("http"):
        # Some preview URLs are MP3s
        if ".mp3" in preview.lower():
            return preview
    return None


def _validate_audio_file(path: Path) -> bool:
    """
    Validate that a downloaded file is actually an audio file.
    Checks file size and MP3 magic bytes.
    """
    if not path.exists():
        return False
    size = path.stat().st_size
    if size < 10_000:  # Less than 10KB is suspicious
        return False
    # Check MP3 magic bytes (ID3 tag or MPEG sync word)
    try:
        header = path.read_bytes()[:4]
        # ID3v2 header
        if header[:3] == b"ID3":
            return True
        # MPEG audio sync word (0xFFE or 0xFFF at start)
        if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return True
    except Exception:
        pass
    # If we can't verify header but size is reasonable, accept it
    return size > 50_000


def _score_track(hit: dict, mood: str, cache: dict) -> float:
    """
    Score a track for selection. Higher = better fit.

    Scoring criteria:
      - Duration match (15-30s ideal for Reels): +10
      - Duration too short (<10s): -20
      - Duration too long (>60s): -5
      - Not used recently (novelty): +5
      - Has valid audio URL: +10
      - User rating / popularity (downloads, likes): +1 to +5
    """
    score = 0.0
    track_id = str(hit.get("id", ""))
    duration = hit.get("duration")

    # Duration scoring
    if duration:
        if 15 <= duration <= 30:
            score += 10
        elif 10 <= duration < 15:
            score += 5
        elif duration < 10:
            score -= 20
        elif duration > 60:
            score -= 5

    # Novelty: prefer tracks not recently used
    cache_tracks = cache.get("tracks", {})
    if track_id in cache_tracks:
        last_used = cache_tracks[track_id].get("last_used")
        if last_used:
            try:
                lu = datetime.fromisoformat(last_used)
                days_ago = (datetime.now() - lu).days
                if days_ago < 3:
                    score -= 10  # Recently used — avoid
                elif days_ago > 14:
                    score += 5   # Not used in 2 weeks — bonus
            except Exception:
                pass
    else:
        score += 5  # Never used — bonus

    # URL availability
    if _pick_audio_url(hit):
        score += 10
    else:
        score -= 50  # Can't download — useless

    # Popularity signals from Pixabay
    downloads = hit.get("downloads", 0)
    likes = hit.get("likes", 0)
    score += min(downloads / 100, 5)
    score += min(likes / 50, 3)

    return score


def _pick_from_pool(hits: list[dict], mood: str, cache: dict, pool_size: int = 3) -> dict | None:
    """
    Score all hits and pick from the top `pool_size` randomly.
    This ensures variety across posts while still picking high-quality tracks.
    """
    if not hits:
        return None

    scored = [(h, _score_track(h, mood, cache)) for h in hits]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Take top N as the selection pool
    pool = scored[:pool_size]
    if not pool:
        return None

    # Weighted random choice from pool (higher score = higher chance)
    weights = [max(s, 0.1) for _, s in pool]
    total = sum(weights)
    r = random.uniform(0, total)
    cumulative = 0
    for hit, w in pool:
        cumulative += w
        if r <= cumulative:
            return hit

    return pool[0][0]


def _download_track(url: str, output_path: Path) -> bool:
    """Download a single audio track. Returns True on success."""
    try:
        dl = requests.get(url, timeout=45, stream=True)
        dl.raise_for_status()
        output_path.write_bytes(dl.content)
        size_kb = output_path.stat().st_size / 1024
        print(f"  [music] ✅ Saved {output_path.name} ({size_kb:.0f} KB)")
        return _validate_audio_file(output_path)
    except Exception as e:
        print(f"  [music] Download error: {e}")
        return False


def download_music_for_mood(
    mood: str,
    api_key: str,
    output_dir: str | Path = "",
    use_trending_vibe: bool = True,
    force_refresh: bool = False,
    pool_size: int = 3,
) -> Path | None:
    """
    Download a royalty-free music track for the given mood.

    Strategy:
    1. Try trending-vibe search first (matches energy of Instagram trends)
    2. Fall back to mood-specific search
    3. Score and pick from top-N pool for variety
    4. Fall back to cached file
    5. Return None (pipeline uses generated audio fallback)

    Args:
        mood: One of the mood keys
        api_key: Pixabay API key
        output_dir: Where to save. Defaults to audio/music/
        use_trending_vibe: If True, prioritise trending-energy tracks
        force_refresh: Re-download even if cached
        pool_size: Number of top hits to randomly pick from
    """
    if not api_key:
        return None

    out_dir = Path(output_dir) if output_dir else MUSIC_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{mood}.mp3"

    cache = _load_cache()

    # Return cached unless force refresh
    if not force_refresh and output_path.exists() and _validate_audio_file(output_path):
        # Update last_used in cache
        if mood in cache.get("tracks", {}):
            cache["tracks"][mood]["last_used"] = datetime.now().isoformat()
            _save_cache(cache)
        print(f"  [music] Cached: {output_path.name}")
        return output_path

    # Strategy 1: Trending vibe search
    hits = []
    if use_trending_vibe:
        vibe = MOOD_TO_TRENDING_VIBE.get(mood)
        if vibe:
            query = TRENDING_VIBES[vibe]
            print(f"  [music] Trending-vibe search: {mood} → '{query[:40]}'")
            hits = _search_pixabay_music(query, api_key, per_page=10)

    # Strategy 2: Mood-specific search (fallback or supplement)
    if not hits:
        query = MOOD_SEARCH.get(mood, "instrumental ambient")
        print(f"  [music] Mood search: {mood} → '{query}'")
        hits = _search_pixabay_music(query, api_key, per_page=10)

    if not hits:
        print(f"  [music] ⚠️  No tracks found for {mood} — using generated audio fallback")
        return None

    # Score and pick from pool
    selected = _pick_from_pool(hits, mood, cache, pool_size=pool_size)
    if not selected:
        print(f"  [music] ⚠️  No usable track found for {mood}")
        return None

    url = _pick_audio_url(selected)
    if not url:
        print(f"  [music] ⚠️  Selected track has no download URL")
        return None

    if _download_track(url, output_path):
        # Update cache with metadata
        meta = _extract_track_meta(selected)
        meta["last_used"] = datetime.now().isoformat()
        meta["mood"] = mood
        cache.setdefault("tracks", {})[mood] = meta
        _save_cache(cache)
        print(f"  [music] Selected: '{meta.get('title', 'Unknown')}' ({meta.get('duration', '?')}s)")
        time.sleep(0.3)
        return output_path

    print(f"  [music] ⚠️  Download failed — using generated audio fallback")
    return None


def download_all_music(api_key: str, output_dir: str | Path = "", force_refresh: bool = False):
    """Download trending-vibe tracks for all moods."""
    print(f"[music] Downloading tracks for {len(MOOD_SEARCH)} moods...")
    results = {}
    for mood in MOOD_SEARCH:
        path = download_music_for_mood(mood, api_key, output_dir, force_refresh=force_refresh)
        results[mood] = "✅" if path else "❌ fallback"
        time.sleep(0.2)
    print("[music] Summary:", results)
    return results


def refresh_trending_music(api_key: str, output_dir: str | Path = ""):
    """Force-refresh all music tracks to get fresh trending-energy tracks.
    Run this weekly to keep audio feeling current."""
    print("[music] 🔄 Refreshing all music tracks with latest trending vibes...")
    download_all_music(api_key, output_dir, force_refresh=True)


def get_track_info(mood: str) -> dict:
    """Return cached metadata for a mood's current track."""
    cache = _load_cache()
    return cache.get("tracks", {}).get(mood, {})


if __name__ == "__main__":
    import sys
    key = os.getenv("PIXABAY_API_KEY", "")
    if not key:
        print("Set PIXABAY_API_KEY env var to download music.")
        sys.exit(1)
    refresh = "--refresh" in sys.argv
    download_all_music(key, force_refresh=refresh)
