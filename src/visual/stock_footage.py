"""Real stock footage source — fetches cinematic videos from Pexels (free API).

Replaces AI-generated backgrounds (FLUX) with real stock footage.
Instagram's 2025 algorithm suppresses AI-generated visuals, so using
real footage removes that penalty entirely.

Pexels API is free (no attribution required, no usage limits for reasonable use).
API key: https://www.pexels.com/api/
"""
import requests
from pathlib import Path
from typing import Optional
import logging

log = logging.getLogger(__name__)

PEXELS_API = "https://api.pexels.com/videos/search"

# Mood -> search terms for stock footage
MOOD_SEARCH_TERMS = {
    "calm_stoic":         ["meditation", "calm ocean", "mountain fog"],
    "cinematic_hopeful":  ["sunrise", "golden hour", "open road"],
    "dark_philosophical": ["dark clouds", "rain window", "moody forest"],
    "dramatic_ancient":   ["ancient ruins", "greek architecture", "marble statue"],
    "epic_warrior":       ["storm clouds", "mountain peak", "dramatic landscape"],
    "mystical_greek":     ["ancient temple", "candle light", "misty mountains"],
    "stark_minimal":      ["minimal architecture", "concrete wall", "empty room"],
}

# Cache for fetched video URLs (simple in-memory, per session)
_CACHE: dict = {}


def search_stock_video(
    mood: str,
    api_key: str,
    per_page: int = 15,
    query: str | None = None,
) -> list[dict]:
    """Search Pexels for stock videos matching the mood.

    Returns a list of video dicts: {id, url, width, height, duration, video_files}
    Empty list on any error.
    """
    if not api_key:
        log.info("[stock] no Pexels API key — falling back to AI art")
        return []

    search_terms = MOOD_SEARCH_TERMS.get(mood, ["philosophy", "nature", "cinematic"])
    if query:
        # Topic-matched visuals (story/weird arcs): try the story's own visual
        # world first; mood terms remain as fallback in the same sweep.
        search_terms = [query] + list(search_terms)
    all_results = []

    for term in search_terms:
        try:
            response = requests.get(
                PEXELS_API,
                headers={"Authorization": api_key},
                params={
                    "query": term,
                    "per_page": per_page,
                    "orientation": "portrait",  # Reels are 9:16
                    "size": "medium",
                },
                timeout=15,
            )
            response.raise_for_status()
            videos = response.json().get("videos", [])
            for v in videos:
                all_results.append({
                    "id": v.get("id"),
                    "duration": v.get("duration"),
                    "width": v.get("width"),
                    "height": v.get("height"),
                    "video_files": v.get("video_files", []),
                    "search_term": term,
                })
        except Exception as e:
            log.warning(f"[stock] Pexels search failed for '{term}': {e}")
            continue

    return all_results


def pick_best_video(videos: list[dict], min_duration: int = 5, max_duration: int = 30) -> dict | None:
    """Pick the best video for a Reel: portrait orientation, 5-30 seconds, HD+ quality.

    Returns the video dict or None.
    """
    if not videos:
        return None

    for video in videos:
        duration = video.get("duration", 0)
        if duration < min_duration or duration > max_duration:
            continue

        # Find the best video file: portrait, 720p+, mp4
        best_file = None
        best_quality = 0
        for vf in video.get("video_files", []):
            width = vf.get("width", 0)
            height = vf.get("height", 0)
            file_type = vf.get("file_type", "")
            if file_type != "video/mp4":
                continue
            # Prefer portrait or square (for Reels)
            if height >= width:
                quality = width * height
                if quality > best_quality:
                    best_quality = quality
                    best_file = vf

        if best_file:
            return {**video, "selected_file": best_file}

    # Fallback: take first available video with any mp4
    for video in videos:
        for vf in video.get("video_files", []):
            if vf.get("file_type") == "video/mp4":
                return {**video, "selected_file": vf}

    return None


def download_stock_video(video: dict, output_path: Path | str) -> Path | None:
    """Download a stock video file. Returns the path or None on failure."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    selected = video.get("selected_file")
    if not selected:
        return None

    download_url = selected.get("link")
    if not download_url:
        return None

    try:
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        if output_path.exists() and output_path.stat().st_size > 0:
            size_mb = output_path.stat().st_size / (1024 * 1024)
            log.info(f"[stock] Downloaded {output_path.name} ({size_mb:.1f} MB)")
            return output_path
    except Exception as e:
        log.warning(f"[stock] Download failed: {e}")

    return None


def fetch_stock_background(
    mood: str,
    api_key: str,
    output_path: Path | str,
    query: str | None = None,
) -> Path | None:
    """Main entry: search + pick + download a stock video for a Reel background.

    Returns the path to the downloaded video file, or None on any failure
    (caller falls back to FLUX AI art).
    """
    output_path = Path(output_path)

    # Check cache first
    cache_key = f"stock_{query or mood}"
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        if cached.get("path") and Path(cached["path"]).exists():
            return Path(cached["path"])

    videos = search_stock_video(mood, api_key, query=query)
    if not videos:
        return None

    best = pick_best_video(videos)
    if not best:
        return None

    downloaded = download_stock_video(best, output_path)
    if downloaded:
        _CACHE[cache_key] = {"path": str(downloaded), "video_id": best.get("id")}

    return downloaded


def pexels_available(api_key: str = "") -> bool:
    """Check if Pexels API is available."""
    return bool(api_key)