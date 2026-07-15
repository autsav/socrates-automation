"""Phase 2 — Selection Policy Bandit.

Thompson sampling (Beta-Bernoulli) over discrete policy arms (mood, slot,
hook, format) using the existing ``ab_results`` table.  When ``use_rewards``
is True the bandit also reads ``post_metrics`` to build a reward-based
posterior, falling back to ab_results win/loss counts otherwise.

The bandit is registered as a ``policy.*`` asset in the optimizer registry
so the self-improving loop can version and propose alternative arm sets.
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Sequence

from src.optimizer import registry
from src.optimizer.reward import reward as compute_reward

# ── public helpers ────────────────────────────────────────────────────────

DIMENSIONS = ("mood", "slot", "hook", "format")


def select(
    dimension: str,
    arms: Sequence[str],
    db_path: str | Path = registry.DB_PATH,
    seed: int | None = None,
    use_rewards: bool = False,
) -> str:
    """Pick one arm via Thompson sampling.

    Parameters
    ----------
    dimension : "mood" | "slot" | "hook" | "format"
    arms      : list of candidate values for this dimension.
    db_path   : path to the SQLite DB containing ``ab_results`` (and
                ``post_metrics`` when *use_rewards* is True).
    seed      : deterministic RNG seed for reproducible tests.
    use_rewards : if True, use reward-weighted Beta priors from
                  ``post_metrics`` instead of ab_results win/loss.

    Returns the chosen arm string.
    """
    if not arms:
        raise ValueError("arms must not be empty")
    if len(arms) == 1:
        return arms[0]

    rng = random.Random(seed)

    if use_rewards:
        posteriors = _reward_posteriors(dimension, arms, db_path)
    else:
        posteriors = _ab_posteriors(dimension, arms, db_path)

    # Sample from each arm's Beta(α, β) and pick the highest sample.
    best_arm = arms[0]
    best_sample = -1.0
    for arm in arms:
        alpha, beta = posteriors.get(arm, (1.0, 1.0))  # uniform prior
        sample = rng.betavariate(alpha, beta)
        if sample > best_sample:
            best_sample = sample
            best_arm = arm

    return best_arm


def register_policy_asset(
    key: str,
    arms: Sequence[str],
    db_path: str | Path = registry.DB_PATH,
) -> int:
    """Register a ``policy.*`` asset whose seed value is the comma-joined
    arm list.  Idempotent — returns the champion version id."""
    seed_value = ",".join(arms)
    return registry.register_asset(key, "policy", seed_value, db_path)


def propose_policy(
    key: str,
    arms: Sequence[str],
    db_path: str | Path = registry.DB_PATH,
) -> dict:
    """Propose a revised arm ordering for the given policy asset.

    Reorders arms by their Thompson-sampled posterior mean so the strongest
    arms come first.  Returns a dict with ``candidate``, ``rationale``, and
    ``predicted_delta`` suitable for the optimizer loop.
    """
    if not arms:
        return {"candidate": "", "rationale": "no arms", "predicted_delta": 0.0}

    posteriors = _ab_posteriors(key.split(".")[-1], arms, db_path)
    # posterior mean = α / (α + β)
    scored = []
    for arm in arms:
        a, b = posteriors.get(arm, (1.0, 1.0))
        scored.append((a / (a + b), arm))
    scored.sort(reverse=True)

    reordered = [arm for _, arm in scored]
    candidate = ",".join(reordered)

    # predicted_delta: difference between best and worst posterior mean
    if scored:
        delta = scored[0][0] - scored[-1][0]
    else:
        delta = 0.0

    champ = registry.get_champion(key, db_path)
    if champ and champ["value"] == candidate:
        rationale = "Current ordering already optimal"
    else:
        rationale = f"Reordered arms by posterior mean: {scored[0][1]} → {scored[-1][1]}"

    return {
        "candidate": candidate,
        "rationale": rationale,
        "predicted_delta": round(delta, 4),
    }


# ── internals ─────────────────────────────────────────────────────────────


def _ab_posteriors(
    dimension: str,
    arms: Sequence[str],
    db_path: str | Path,
) -> dict[str, tuple[float, float]]:
    """Build Beta(α, β) priors from pairwise ab_results.

    For each arm we aggregate wins/trials across all pairwise comparisons
    where it appears as variant_a or variant_b.  α = wins + 1, β = losses + 1.
    """
    con = sqlite3.connect(str(db_path))
    try:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "ab_results" not in tables:
            return {arm: (1.0, 1.0) for arm in arms}

        posteriors: dict[str, list[float]] = {arm: [1.0, 1.0] for arm in arms}  # [alpha, beta]
        for arm in arms:
            # wins as variant_a
            rows = con.execute(
                "SELECT wins_a, wins_b, trials FROM ab_results "
                "WHERE dimension=? AND variant_a=?",
                (dimension, arm),
            ).fetchall()
            for wins_a, wins_b, trials in rows:
                losses = trials - wins_a
                posteriors[arm][0] += wins_a
                posteriors[arm][1] += losses

            # wins as variant_b
            rows = con.execute(
                "SELECT wins_a, wins_b, trials FROM ab_results "
                "WHERE dimension=? AND variant_b=?",
                (dimension, arm),
            ).fetchall()
            for wins_a, wins_b, trials in rows:
                losses = trials - wins_b
                posteriors[arm][0] += wins_b
                posteriors[arm][1] += losses
    finally:
        con.close()

    return {arm: (a, b) for arm, (a, b) in posteriors.items()}


def _reward_posteriors(
    dimension: str,
    arms: Sequence[str],
    db_path: str | Path,
) -> dict[str, tuple[float, float]]:
    """Build Beta priors from per-arm reward rates in post_metrics.

    Joins ``posts`` to ``post_metrics``, groups by the dimension column,
    computes a scalar reward per post, then converts to pseudo win/loss
    counts (reward scaled to [0, 1] × trials).
    """
    col_map = {"mood": "mood", "slot": "posting_slot", "hook": "hook_id", "format": "format"}
    col = col_map.get(dimension, dimension)

    con = sqlite3.connect(str(db_path))
    try:
        # Check tables exist
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "posts" not in tables or "post_metrics" not in tables:
            return {arm: (1.0, 1.0) for arm in arms}

        posteriors: dict[str, tuple[float, float]] = {}
        for arm in arms:
            rows = con.execute(
                "SELECT m.likes, m.comments, m.reach, m.impressions, m.saved, m.shares "
                "FROM posts p JOIN post_metrics m ON p.post_id = m.post_id "
                f"WHERE p.{col} = ?",
                (str(arm),),
            ).fetchall()
            if not rows:
                posteriors[arm] = (1.0, 1.0)
                continue

            total_reward = 0.0
            for row in rows:
                metrics = dict(zip(
                    ("likes", "comments", "reach", "impressions", "saved", "shares"),
                    row,
                ))
                total_reward += compute_reward(metrics)

            avg_reward = total_reward / len(rows)
            # Convert to pseudo win/loss: α = avg_reward * n + 1, β = (1 - avg_reward) * n + 1
            n = len(rows)
            alpha = avg_reward * n + 1.0
            beta = (1.0 - avg_reward) * n + 1.0
            posteriors[arm] = (alpha, beta)
    finally:
        con.close()

    return posteriors