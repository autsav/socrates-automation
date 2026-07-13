"""Jamendo music source for the Music Director.

Searches the Jamendo API (https://api.jamendo.com/v3.0/tracks/) for instrumental,
downloadable, CC-licensed tracks and downloads the chosen one. Self-contained:
HTTP, metadata extraction, download + validation, and a heuristic fallback pick.
Every function degrades gracefully — search/download failures return []/False so
the Music Director can fall back to the mood-based bed.
"""
from pathlib import Path

import requests

JAMENDO_TRACKS_API = "https://api.jamendo.com/v3.0/tracks/"

# MusicDirection.energy -> Jamendo `speed` (verylow..veryhigh). We only emit the
# three the agent produces; everything else defaults to medium.
_ENERGY_TO_SPEED = {"low": "low", "medium": "medium", "high": "high"}


def search_tracks(direction, client_id, limit=20):
    """Query Jamendo from a MusicDirection. Returns only tracks whose
    ``audiodownload_allowed`` is true (the server-side filter is unreliable).
    Returns [] on missing key or any error."""
    if not client_id:
        return []
    query = getattr(direction, "search_query", "") or ""
    params = {
        "client_id": client_id,
        "format": "json",
        "limit": limit,
        "fuzzytags": " ".join(query.split()),
        "vocalinstrumental": "instrumental",
        "speed": _ENERGY_TO_SPEED.get(getattr(direction, "energy", ""), "medium"),
        "include": "musicinfo",
    }
    try:
        resp = requests.get(JAMENDO_TRACKS_API, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as e:  # noqa: BLE001 - degrade gracefully
        print(f"  [jamendo] search error ({query[:30]}): {e}")
        return []
    return [h for h in results if h.get("audiodownload_allowed")]


def extract_meta(hit):
    """Compact metadata for the ranking prompt: id, name, flattened tags, duration."""
    info = hit.get("musicinfo") or {}
    tagblob = info.get("tags")
    if isinstance(tagblob, dict):
        tags = " ".join(t for vals in tagblob.values()
                        if isinstance(vals, list) for t in vals)
    else:
        tags = str(tagblob or "")
    return {"id": str(hit.get("id")), "name": hit.get("name", ""),
            "tags": tags or hit.get("name", ""), "duration": hit.get("duration")}


def pick_audio_url(hit):
    """The track's downloadable URL, or None when not allowed / absent."""
    if not hit.get("audiodownload_allowed"):
        return None
    url = hit.get("audiodownload", "")
    return url if isinstance(url, str) and url.startswith("http") else None


def _validate_audio_file(path):
    """True if `path` looks like a real audio file (size + MP3 magic bytes)."""
    if not path.exists():
        return False
    size = path.stat().st_size
    if size < 10_000:
        return False
    try:
        header = path.read_bytes()[:4]
        if header[:3] == b"ID3":
            return True
        if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return True
    except Exception:
        pass
    return size > 50_000


def download_track(url, output_path):
    """Download `url` to `output_path` and validate it. Returns True on success."""
    try:
        output_path = Path(output_path)
        dl = requests.get(url, timeout=45, stream=True)
        dl.raise_for_status()
        output_path.write_bytes(dl.content)
        size_kb = output_path.stat().st_size / 1024
        print(f"  [jamendo] Saved {output_path.name} ({size_kb:.0f} KB)")
        ok = _validate_audio_file(output_path)
        if not ok:
            output_path.unlink(missing_ok=True)
        return ok
    except Exception as e:  # noqa: BLE001
        print(f"  [jamendo] download error: {e}")
        return False


def pick_from_pool(hits):
    """Heuristic fallback when the agent doesn't pick a usable id: the first
    downloadable track, preferring duration >= 15s. None if none usable."""
    usable = [h for h in hits if pick_audio_url(h)]
    if not usable:
        return None
    longish = [h for h in usable if (h.get("duration") or 0) >= 15]
    return (longish or usable)[0]
