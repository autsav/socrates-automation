"""
Point 45: Comment Sentiment Analysis.

Lightweight keyword-based sentiment classifier for Instagram comments.
Categorises as: positive | negative | neutral | question | fire.
No external ML dependency — uses curated keyword lists.
"""

import re
from typing import Literal

SentimentLabel = Literal["positive", "negative", "neutral", "question", "fire"]

_POSITIVE_WORDS = {
    "love", "amazing", "beautiful", "perfect", "needed", "true", "yes", "exactly",
    "resonated", "powerful", "hit", "real", "same", "facts", "goat", "inspired",
    "inspiring", "saved", "sharing", "thank", "thanks", "grateful", "moved",
    "crying", "gold", "gem", "treasure", "wisdom", "brilliant", "deep", "wow",
}

_NEGATIVE_WORDS = {
    "disagree", "wrong", "bad", "hate", "stupid", "dumb", "fake", "not",
    "don't", "disagree", "nope", "no", "lie", "lies", "skip", "boring",
    "overrated", "cliche", "already", "nothing", "useless", "cringe",
}

_QUESTION_PATTERNS = [
    r"\?",
    r"^(what|how|why|when|who|where|can|is|are|does|do|would|should|could)\b",
]

_FIRE_MARKERS = {
    "🔥", "💯", "❤️", "🙌", "✨", "⚡", "💪", "🫀", "💥", "fire", "goated", "slap",
    "banger", "w post", "w post", "must share",
}


def classify_comment(text: str) -> SentimentLabel:
    """
    Classify a single comment string into a sentiment label.
    Returns: positive | negative | neutral | question | fire
    """
    lower = text.lower().strip()

    # Fire check first (high-value signals)
    for marker in _FIRE_MARKERS:
        if marker in lower:
            return "fire"

    # Question check
    for pattern in _QUESTION_PATTERNS:
        if re.search(pattern, lower):
            return "question"

    words = set(re.findall(r"\w+", lower))
    pos_hits = len(words & _POSITIVE_WORDS)
    neg_hits = len(words & _NEGATIVE_WORDS)

    if pos_hits > neg_hits:
        return "positive"
    elif neg_hits > pos_hits:
        return "negative"
    return "neutral"


def analyse_comments(comments: list[str]) -> dict:
    """
    Point 45: Analyse a list of comments and return sentiment breakdown.
    Returns: {positive: n, negative: n, neutral: n, question: n, fire: n, total: n}
    """
    counts: dict[str, int] = {
        "positive": 0, "negative": 0, "neutral": 0, "question": 0, "fire": 0
    }
    for c in comments:
        label = classify_comment(c)
        counts[label] = counts.get(label, 0) + 1

    total = len(comments)
    counts["total"] = total
    if total > 0:
        counts["positivity_rate"] = round(
            (counts["positive"] + counts["fire"]) / total * 100, 1
        )
    else:
        counts["positivity_rate"] = 0.0
    return counts


def sentiment_report(post_id: str, comments: list[str]) -> dict:
    """Analyse + return a structured report for a post's comments."""
    analysis = analyse_comments(comments)
    return {
        "post_id": post_id,
        "comment_count": analysis["total"],
        "sentiment": analysis,
        "top_sentiment": max(
            ["positive", "negative", "neutral", "question", "fire"],
            key=lambda k: analysis.get(k, 0),
        ),
        "positivity_rate": analysis.get("positivity_rate", 0.0),
    }
