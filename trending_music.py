"""
Trending Music — curated database of trending sounds for the stoic/philosophy niche.

Since Instagram's API does not allow attaching trending audio to posts,
this module provides a manually-curated list of sounds that perform well
in our niche. The list is updated weekly based on what's trending on
Instagram/TikTok for stoic/motivational/philosophy content.

Usage: After posting a Reel, suggest a trending sound the user can
manually add via the Instagram app.
"""

import json
import random
from pathlib import Path
from datetime import datetime, timedelta

# ── Curated trending sounds database ──────────────────────────────────────────
# Updated manually every 1-2 weeks based on:
#   - Instagram Reels trending sounds in stoic/motivational niche
#   - TikTok viral sounds repurposed for wisdom content
#   - Classical/orchestral tracks gaining traction
#   - User feedback on which sounds drove engagement

_CURATED_SOUNDS = [
    {
        "id": "ts_001",
        "name": "Cinematic Piano Build",
        "search_hint": "cinematic piano build emotional",
        "moods": ["cinematic_hopeful", "mystical_greek", "calm_stoic"],
        "genre": "emotional_build",
        "notes": "Top trending for hope/reflection content. Soft piano → strings crescendo.",
    },
    {
        "id": "ts_002",
        "name": "Dark Orchestral Drop",
        "search_hint": "dark orchestral dramatic drop",
        "moods": ["dark_philosophical", "dramatic_ancient"],
        "genre": "dramatic_cinematic",
        "notes": "Heavy engagement for edgy philosophy. Low cello → brass explosion.",
    },
    {
        "id": "ts_003",
        "name": "Epic Percussion March",
        "search_hint": "epic percussion march battle",
        "moods": ["epic_warrior", "dramatic_ancient"],
        "genre": "upbeat_energetic",
        "notes": "High-energy taiko/orchestral hybrid. Perfect for discipline/warrior quotes.",
    },
    {
        "id": "ts_004",
        "name": "Lo-Fi Study Beat",
        "search_hint": "lo-fi study beat chill",
        "moods": ["calm_stoic", "stark_minimal"],
        "genre": "nostalgic_warm",
        "notes": "Understated lo-fi hip-hop. Great for calm stoic/mindfulness content.",
    },
    {
        "id": "ts_005",
        "name": "Ethereal Harp Glissando",
        "search_hint": "ethereal harp ambient magical",
        "moods": ["mystical_greek", "cinematic_hopeful"],
        "genre": "emotional_build",
        "notes": "Light, mystical harp → ambient pad. High saves on spiritual content.",
    },
    {
        "id": "ts_006",
        "name": "Minimal Piano Sparse",
        "search_hint": "minimal piano sparse instrumental",
        "moods": ["stark_minimal", "calm_stoic"],
        "genre": "minimalist_focus",
        "notes": "Single piano notes with heavy reverb. Clean, modern, high completion rate.",
    },
    {
        "id": "ts_007",
        "name": "Phonk Drift Bass",
        "search_hint": "phonk drift bass cowbell",
        "moods": ["dark_philosophical", "epic_warrior"],
        "genre": "upbeat_energetic",
        "notes": "Memphis phonk with heavy bass. Unexpected pairing with ancient wisdom = high shares.",
    },
    {
        "id": "ts_008",
        "name": "Cinematic Strings Swell",
        "search_hint": "cinematic strings swell emotional",
        "moods": ["cinematic_hopeful", "mystical_greek"],
        "genre": "emotional_build",
        "notes": "Slow violin/cello swell. Classic for motivational quote content.",
    },
]

# Weekly rotation: avoid suggesting the same sound repeatedly
# Deterministic based on ISO week number so it's consistent across runs
_WEEK_OF_YEAR = datetime.now().isocalendar().week


def get_trending_suggestion(mood: str) -> str:
    """
    Return a trending sound recommendation for the given mood.
    Rotates weekly to keep suggestions fresh.
    """
    # Filter sounds matching this mood
    matching = [s for s in _CURATED_SOUNDS if mood in s.get("moods", [])]
    if not matching:
        # Fall back to any sound
        matching = _CURATED_SOUNDS

    # Deterministic weekly rotation
    idx = (_WEEK_OF_YEAR + hash(mood)) % len(matching)
    sound = matching[idx]

    return f"{sound['name']} (search: '{sound['search_hint']}') — {sound['notes']}"


def get_all_suggestions_for_mood(mood: str, top_n: int = 3) -> list[str]:
    """Return top N trending sound suggestions for a mood."""
    matching = [s for s in _CURATED_SOUNDS if mood in s.get("moods", [])]
    if not matching:
        matching = _CURATED_SOUNDS

    # Shuffle deterministically by week
    rng = random.Random(_WEEK_OF_YEAR)
    shuffled = matching[:]
    rng.shuffle(shuffled)

    return [get_trending_suggestion(mood) for mood in [mood] * min(top_n, len(shuffled))]


def list_all_sounds() -> list[dict]:
    """Return the full curated database (for admin/curator use)."""
    return _CURATED_SOUNDS[:]


def refresh_weekly_rotation():
    """Recalculate week-based rotation (call if date changes mid-run)."""
    global _WEEK_OF_YEAR
    _WEEK_OF_YEAR = datetime.now().isocalendar().week


if __name__ == "__main__":
    import sys
    mood = sys.argv[1] if len(sys.argv) > 1 else "dark_philosophical"
    print(f"Trending suggestion for '{mood}':")
    print(get_trending_suggestion(mood))
    print()
    print("All curated sounds:")
    for s in list_all_sounds():
        print(f"  - {s['name']} ({', '.join(s['moods'])})")
