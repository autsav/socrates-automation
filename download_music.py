"""
Music Downloader — fetches royalty-free instrumental music from Pixabay
for each mood and caches it in audio/music/.

Requires: PIXABAY_API_KEY (free at pixabay.com/api/docs)
Fallback: Uses existing audio/ tracks if API unavailable
"""

import os
import time
import requests
from pathlib import Path

MUSIC_DIR = Path(__file__).parent / "audio" / "music"
PIXABAY_API = "https://pixabay.com/api/"

# Mood → Pixabay search terms for instrumental music
MOOD_SEARCH = {
    "calm_stoic":       "soft piano ambient meditation calm instrumental",
    "cinematic_hopeful": "cinematic orchestral strings hopeful uplifting instrumental",
    "dark_philosophical": "deep cello dark atmospheric contemplative instrumental",
    "dramatic_ancient":  "epic percussion dramatic ancient instrumental",
    "epic_warrior":      "battle drums brass epic powerful instrumental",
    "mystical_greek":    "ethereal choir harp mystical instrumental",
    "stark_minimal":     "minimal piano single instrument sparse instrumental",
}


def download_music_for_mood(
    mood: str,
    api_key: str,
    output_dir: str | Path = "",
) -> Path | None:
    """
    Download a royalty-free music track from Pixabay for the given mood.

    Args:
        mood: One of the mood keys in MOOD_SEARCH
        api_key: Pixabay API key
        output_dir: Directory to save MP3. Defaults to audio/music/

    Returns:
        Path to downloaded MP3, or None if download failed.
    """
    if not api_key:
        return None

    out_dir = Path(output_dir) if output_dir else MUSIC_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    search = MOOD_SEARCH.get(mood)
    if not search:
        print(f"  [music] Unknown mood '{mood}' — skipping")
        return None

    output_path = out_dir / f"{mood}.mp3"

    # Already cached?
    if output_path.exists() and output_path.stat().st_size > 1000:
        print(f"  [music] Cached: {output_path}")
        return output_path

    try:
        resp = requests.get(
            PIXABAY_API,
            params={
                "key": api_key,
                "q": search,
                "category": "music",
                "per_page": 3,
                "orientation": "all",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("hits", [])
        if not hits:
            print(f"  [music] No results for '{search}'")
            return None

        # Pick first result with a preview URL
        for hit in hits:
            preview_url = hit.get("previewURL") or hit.get("audio")
            if preview_url:
                break
        else:
            print(f"  [music] No preview URL found")
            return None

        # Download preview MP3
        print(f"  [music] Downloading {mood} from Pixabay...")
        dl_resp = requests.get(preview_url, timeout=30)
        dl_resp.raise_for_status()

        output_path.write_bytes(dl_resp.content)
        size = output_path.stat().st_size
        print(f"  [music] Saved: {output_path} ({size / 1024:.0f} KB)")

        # Rate-limit safety
        time.sleep(0.5)
        return output_path

    except requests.HTTPError as e:
        print(f"  [music] HTTP error: {e}")
    except Exception as e:
        print(f"  [music] Error: {e}")

    return None


def download_all_music(api_key: str, output_dir: str | Path = ""):
    """Download music for all moods."""
    for mood in MOOD_SEARCH:
        download_music_for_mood(mood, api_key, output_dir)


if __name__ == "__main__":
    import sys
    key = os.getenv("PIXABAY_API_KEY", "")
    if not key:
        print("Set PIXABAY_API_KEY env var to download music.")
        sys.exit(1)
    download_all_music(key)
