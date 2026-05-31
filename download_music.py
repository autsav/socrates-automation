"""
Music Downloader — fetches royalty-free instrumental music from Pixabay Music API.

TWO STRATEGIES:
1. Mood-matched tracks  — cinematic/epic/calm tracks baked into MP4 (always works)
2. Trending-vibe tracks — tracks matching the ENERGY of currently trending Instagram
   audio (upbeat, dramatic, emotional, minimal) for maximum algorithmic boost

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
import requests
from pathlib import Path

MUSIC_DIR = Path(__file__).parent / "audio" / "music"
PIXABAY_MUSIC_API = "https://pixabay.com/api/music/"   # ← Correct music endpoint

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
    "upbeat_energetic":   "upbeat energetic pop happy 120bpm",        # like Forrest Frank, GloRilla
    "dramatic_cinematic": "cinematic dramatic orchestral emotional",   # like epic movie scores
    "nostalgic_warm":     "nostalgic warm retro lo-fi cozy",          # like oldies/lo-fi trends
    "emotional_build":    "emotional build piano strings crescendo",  # like faith/reflection content
    "minimalist_focus":   "minimal clean focus productivity ambient", # like calm/stoic content
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


def _search_pixabay_music(query: str, api_key: str, per_page: int = 5) -> list[dict]:
    """Search Pixabay Music API. Returns list of hit dicts."""
    try:
        resp = requests.get(
            PIXABAY_MUSIC_API,
            params={"key": api_key, "q": query, "per_page": per_page},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("hits", [])
    except Exception as e:
        print(f"  [music] Search error ({query[:30]}): {e}")
        return []


def _download_track(url: str, output_path: Path) -> bool:
    """Download a single audio track. Returns True on success."""
    try:
        dl = requests.get(url, timeout=45, stream=True)
        dl.raise_for_status()
        output_path.write_bytes(dl.content)
        size_kb = output_path.stat().st_size / 1024
        print(f"  [music] ✅ Saved {output_path.name} ({size_kb:.0f} KB)")
        return size_kb > 10  # Reject suspiciously small files
    except Exception as e:
        print(f"  [music] Download error: {e}")
        return False


def _pick_audio_url(hits: list[dict]) -> str | None:
    """Extract usable audio URL from Pixabay hit. Tries multiple field names."""
    for hit in hits:
        for field in ("audio", "audioURL", "previewURL", "url"):
            url = hit.get(field)
            if url and url.endswith((".mp3", ".ogg", ".wav", "/")):
                return url
            if url and "audio" in url:
                return url
    return None


def download_music_for_mood(
    mood: str,
    api_key: str,
    output_dir: str | Path = "",
    use_trending_vibe: bool = True,
    force_refresh: bool = False,
) -> Path | None:
    """
    Download a royalty-free music track for the given mood.

    Strategy:
    1. Try trending-vibe search first (matches energy of Instagram trends)
    2. Fall back to mood-specific search
    3. Fall back to cached file
    4. Return None (pipeline uses generated audio fallback)

    Args:
        mood: One of the mood keys
        api_key: Pixabay API key
        output_dir: Where to save. Defaults to audio/music/
        use_trending_vibe: If True, prioritise trending-energy tracks
        force_refresh: Re-download even if cached
    """
    if not api_key:
        return None

    out_dir = Path(output_dir) if output_dir else MUSIC_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{mood}.mp3"

    # Return cached unless force refresh
    if not force_refresh and output_path.exists() and output_path.stat().st_size > 10_000:
        print(f"  [music] Cached: {output_path.name}")
        return output_path

    # Strategy 1: Trending vibe search
    if use_trending_vibe:
        vibe = MOOD_TO_TRENDING_VIBE.get(mood)
        if vibe:
            query = TRENDING_VIBES[vibe]
            print(f"  [music] Trending-vibe search: {mood} → '{query[:40]}'")
            hits = _search_pixabay_music(query, api_key)
            if hits:
                # Pick a random hit for variety across posts
                random.shuffle(hits)
                url = _pick_audio_url(hits)
                if url and _download_track(url, output_path):
                    time.sleep(0.3)
                    return output_path

    # Strategy 2: Mood-specific search
    query = MOOD_SEARCH.get(mood, "instrumental ambient")
    print(f"  [music] Mood search: {mood} → '{query}'")
    hits = _search_pixabay_music(query, api_key)
    if hits:
        url = _pick_audio_url(hits)
        if url and _download_track(url, output_path):
            time.sleep(0.3)
            return output_path

    print(f"  [music] ⚠️  No track found for {mood} — using generated audio fallback")
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


if __name__ == "__main__":
    import sys
    key = os.getenv("PIXABAY_API_KEY", "")
    if not key:
        print("Set PIXABAY_API_KEY env var to download music.")
        sys.exit(1)
    refresh = "--refresh" in sys.argv
    download_all_music(key, force_refresh=refresh)
