"""Scalar reward for a post's engagement. Reuses predictive_scoring's research
weights; normalized by reach so it measures engagement *rate*, not raw volume
(a high-reach post shouldn't win just for being distributed)."""

REWARD_WEIGHTS = {
    "saved": 3.0, "shares": 2.5, "comments": 2.0,
    "reach": 1.5, "likes": 1.0, "impressions": 0.0,
}


def reward(metrics):
    if not metrics:
        return 0.0
    reach = max(float(metrics.get("reach", 0) or 0), 1.0)
    total = 0.0
    for k, w in REWARD_WEIGHTS.items():
        if k == "reach":
            continue
        total += w * float(metrics.get(k, 0) or 0)
    return total / reach
