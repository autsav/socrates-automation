"""
A/B Test Engine — Thompson Sampling (Beta-Bernoulli bandit).
Selects caption variant, image mood, and posting slot based on
rolling 30-day performance data from SQLite.
"""

import random
from typing import Callable


def _thompson_sample(wins_a: int, wins_b: int, trials: int) -> str:
    """
    Sample from Beta(wins+1, trials-wins+1) for each variant.
    `trials` is the total number of trials for both variants combined.
    Returns 'a' or 'b'.
    """
    sample_a = random.betavariate(wins_a + 1, (trials - wins_a) + 1)
    sample_b = random.betavariate(wins_b + 1, (trials - wins_b) + 1)
    return "a" if sample_a > sample_b else "b"


def pick_caption_variant(
    audience: str,
    get_ab_results: Callable[[str, str, str], dict],
) -> int:
    """
    Return 0 (hook-first) or 1 (story-first) using Thompson Sampling.
    Falls back to random if < 5 trials (cold start).
    """
    results = get_ab_results("caption", "hook_first", "story_first")
    wins_a = results["wins_a"]
    wins_b = results["wins_b"]
    trials = results["trials"]

    if trials < 5:
        variant = random.choice([0, 1])
        print(f"  [ab] caption cold start ({trials} trials) → random {variant}")
        return variant

    winner = _thompson_sample(wins_a, wins_b, trials)
    variant = 0 if winner == "a" else 1
    print(f"  [ab] caption → variant {variant} (wins: {wins_a}/{wins_b}, trials: {trials})")
    return variant


def pick_mood(
    audience: str,
    quote: str,
    get_ab_results: Callable[[str, str, str], dict],
    valid_moods: list[str] | None = None,
) -> str:
    """
    Return mood from VALID_MOODS using pairwise round-robin Thompson Sampling.
    Each mood is compared against all others; the mood with the most pairwise
    wins is selected. Cold start (< 5 trials per pair) falls back to random.
    """
    if valid_moods is None:
        valid_moods = [
            "dark_philosophical", "dramatic_ancient", "cinematic_hopeful",
            "stark_minimal", "epic_warrior", "mystical_greek", "calm_stoic",
        ]

    best_mood = None
    best_score = -1

    for i, mood_a in enumerate(valid_moods):
        wins = 0
        for j, mood_b in enumerate(valid_moods):
            if i == j:
                continue
            results = get_ab_results("mood", mood_a, mood_b)
            if results["trials"] < 5:
                continue
            winner = _thompson_sample(results["wins_a"], results["wins_b"], results["trials"])
            if winner == "a":
                wins += 1

        if wins > best_score:
            best_score = wins
            best_mood = mood_a

    if best_mood is None or best_score < 0:
        best_mood = random.choice(valid_moods)
        print(f"  [ab] mood cold start → random {best_mood}")
    else:
        print(f"  [ab] mood → {best_mood} (score {best_score})")

    return best_mood


def pick_optimal_slot(
    audience: str,
    get_ab_results: Callable[[str, str, str], dict],
) -> int:
    """
    Return 0 (morning), 1 (afternoon), or 2 (evening).
    Uses pairwise Thompson Sampling on morning vs evening.
    Afternoon is only chosen during cold-start random fallback.
    """
    results = get_ab_results("slot", "morning", "evening")
    wins_a = results["wins_a"]
    wins_b = results["wins_b"]
    trials = results["trials"]

    if trials < 5:
        slot = random.choice([0, 1, 2])
        print(f"  [ab] slot cold start ({trials} trials) → random {slot}")
        return slot

    winner = _thompson_sample(wins_a, wins_b, trials)
    if winner == "a":
        slot = 0
    else:
        slot = 2

    print(f"  [ab] slot → {slot} (wins: {wins_a}/{wins_b}, trials: {trials})")
    return slot