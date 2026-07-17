"""Real stock photo source — fetches cinematic photography from Pexels (free API).

For image posts and Reel thumbnails when stock video isn't available.
Same API as stock_footage.py but for photos instead of videos.
"""
import requests
from pathlib import Path
import logging

log = logging.getLogger(__name__)

PEXELS_PHOTO_API = "https://api.pexels.com/v1/search"

# Mood -> search terms for stock photos
MOOD_SEARCH_TERMS = {
    "calm_stoic":         ["meditation", "calm", "minimalism"],
    "cinematic_hopeful":  ["sunrise", "golden hour", "hope"],
    "dark_philosophical": ["dark clouds", "moody", "contemplation"],
    "dramatic_ancient":   ["ancient ruins", "greek", "marble"],
    "epic_warrior":       ["mountain", "storm", "strength"],
    "mystical_greek":    ["temple", "candle", "mist"],
    "stark_minimal":      ["minimal", "concrete", "empty"],
}


def search_stock_photo(mood: str, api_key: str, per_page: int = 10) -> list[dict]:
    """Search Pexels for stock photos matching the mood."""
    if not api_key:
        return []

    search_terms = MOOD_SEARCH_TERMS.get(mood, ["philosophy", "nature"])
    all_results = []

    for term in search_terms:
        try:
            response = requests.get(
                PEXELS_PHOTO_API,
                headers={"Authorization": api_key},
                params={
                    "query": term,
                    "per_page": per_page,
                    "orientation": "portrait",
                },
                timeout=15,
            )
            response.raise_for_status()
            photos = response.json().get("photos", [])
            for p in photos:
                all_results.append({
                    "id": p.get("id"),
                    "url": p.get("src", {}).get("large2x", p.get("src", {}).get("large", "")),
                    "width": p.get("width"),
                    "height": p.get("height"),
                    "photographer": p.get("photographer", ""),
                    "search_term": term,
                })
        except Exception as e:
            log.warning(f"[stock-photo] Pexels search failed for '{term}': {e}")
            continue

    return all_results


def download_stock_photo(url: str, output_path: Path | str) -> Path | None:
    """Download a stock photo."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
    except Exception as e:
        log.warning(f"[stock-photo] Download failed: {e}")
    return None


def fetch_stock_photo(mood: str, api_key: str, output_path: Path | str) -> Path | None:
    """Search + download a stock photo for the given mood."""
    photos = search_stock_photo(mood, api_key)
    if not photos:
        return None

    import random
    # Pick a random photo from the first 5 results (variety)
    top = photos[:5]
    photo = random.choice(top)
    url = photo.get("url")
    if not url:
        return None

    return download_stock_photo(url, output_path)