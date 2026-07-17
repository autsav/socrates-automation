"""Canonical engagement-score weights — the single source of truth.

All modules that compute an engagement score (cohort_analysis,
predictive_scoring, optimizer/reward) must import from here instead of
duplicating the formula. This prevents silent desync when weights change.
"""

# Engagement metric weights (multiplier per unit)
SCORE_WEIGHTS = {
    "saved": 3.0,
    "shares": 2.5,
    "comments": 2.0,
    "reach": 1.5,
    "likes": 1.0,
    "impressions": 0.0,
}


def engagement_score(metrics: dict) -> float:
    """Compute the scalar engagement score from a metrics dict.

    Normalized by reach so it measures engagement *rate*, not raw volume.
    """
    if not metrics:
        return 0.0
    reach = max(float(metrics.get("reach", 0) or 0), 1.0)
    total = 0.0
    for k, w in SCORE_WEIGHTS.items():
        if k == "reach":
            continue
        total += w * float(metrics.get(k, 0) or 0)
    return total / reach