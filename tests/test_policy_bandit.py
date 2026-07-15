"""Tests for the Phase 2 selection-policy bandit (src/optimizer/proposers/policy_bandit)."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer.proposers import policy_bandit
from src.optimizer import registry


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    return p


def _insert_ab_row(db, dimension, va, vb, wins_a, wins_b, trials):
    con = sqlite3.connect(str(db))
    # Ensure ab_results table exists (optimizer init may not create it)
    con.execute(
        "CREATE TABLE IF NOT EXISTS ab_results ("
        "dimension TEXT NOT NULL, variant_a TEXT NOT NULL, variant_b TEXT NOT NULL, "
        "wins_a INTEGER DEFAULT 0, wins_b INTEGER DEFAULT 0, trials INTEGER DEFAULT 0, "
        "PRIMARY KEY (dimension, variant_a, variant_b))"
    )
    con.execute(
        "INSERT OR REPLACE INTO ab_results "
        "(dimension, variant_a, variant_b, wins_a, wins_b, trials) "
        "VALUES (?,?,?,?,?,?)",
        (dimension, va, vb, wins_a, wins_b, trials),
    )
    con.commit()
    con.close()


def _insert_post_with_metrics(db, mood, slot, hook, fmt, reward_val):
    """Insert a post + metrics row so the bandit can read historical rewards."""
    con = sqlite3.connect(str(db))
    # posts table
    con.execute(
        "CREATE TABLE IF NOT EXISTS posts ("
        "post_id TEXT PRIMARY KEY, post_date TEXT, posting_slot INTEGER DEFAULT 0,"
        "mood TEXT, hook_id TEXT, format TEXT, dry_run INTEGER DEFAULT 0)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS post_metrics ("
        "post_id TEXT PRIMARY KEY, likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,"
        "reach INTEGER DEFAULT 0, impressions INTEGER DEFAULT 0, saved INTEGER DEFAULT 0,"
        "shares INTEGER DEFAULT 0)"
    )
    pid = f"p_{mood}_{slot}_{hook}_{fmt}_{reward_val}"
    reach = 100
    likes = int(reward_val * reach)  # reward ≈ likes/reach
    con.execute(
        "INSERT OR REPLACE INTO posts (post_id, post_date, posting_slot, mood, hook_id, format, dry_run) "
        "VALUES (?,?,?, ?, ?, ?, 0)",
        (pid, "2026-07-01", slot, mood, hook, fmt),
    )
    con.execute(
        "INSERT OR REPLACE INTO post_metrics (post_id, likes, comments, reach, impressions, saved, shares) "
        "VALUES (?, ?, 0, ?, ?, 0, 0)",
        (pid, likes, reach, reach),
    )
    con.commit()
    con.close()


# ── tests ─────────────────────────────────────────────────────────────────

def test_cold_start_returns_random_arm(db):
    """With no ab_results data, the bandit should still return a valid arm."""
    arms = ["dark_philosophical", "epic_warrior", "calm_stoic"]
    choice = policy_bandit.select("mood", arms, db_path=db)
    assert choice in arms


def test_winning_arm_selected_with_enough_data(db):
    """When one arm has clearly more wins, Thompson sampling should favour it."""
    _insert_ab_row(db, "mood", "dark_philosophical", "epic_warrior", 50, 5, 60)
    _insert_ab_row(db, "mood", "dark_philosophical", "calm_stoic", 50, 5, 60)
    arms = ["dark_philosophical", "epic_warrior", "calm_stoic"]
    # With 90%+ win rate for dark_philosophical, it should dominate in samples
    counts = {"dark_philosophical": 0, "epic_warrior": 0, "calm_stoic": 0}
    for i in range(100):
        choice = policy_bandit.select("mood", arms, db_path=db, seed=i)
        counts[choice] += 1
    assert counts["dark_philosophical"] > 80  # should be chosen most often


def test_register_policy_asset(db):
    """register_policy_asset creates a 'policy' kind asset in the registry."""
    vid = policy_bandit.register_policy_asset("policy.mood", ["dark_philosophical", "epic_warrior"], db)
    champ = registry.get_champion("policy.mood", db)
    assert champ is not None
    assert champ["value"] == "dark_philosophical,epic_warrior"
    assert champ["version_num"] == 1


def test_propose_policy_returns_candidate(db):
    """propose_policy should return a candidate string + rationale."""
    _insert_ab_row(db, "mood", "dark_philosophical", "epic_warrior", 30, 10, 45)
    arms = ["dark_philosophical", "epic_warrior", "calm_stoic"]
    result = policy_bandit.propose_policy("policy.mood", arms, db_path=db)
    assert "candidate" in result
    assert "rationale" in result
    assert result["predicted_delta"] >= 0


def test_select_uses_seed_for_determinism(db):
    """Same seed should produce the same choice."""
    arms = ["a", "b", "c"]
    c1 = policy_bandit.select("hook", arms, db_path=db, seed=42)
    c2 = policy_bandit.select("hook", arms, db_path=db, seed=42)
    assert c1 == c2


def test_empty_arms_raises():
    """No arms provided should raise ValueError."""
    with pytest.raises(ValueError):
        policy_bandit.select("mood", [], db_path="dummy")


def test_reward_based_selection(db):
    """When post_metrics has reward data, the bandit should prefer high-reward arms."""
    _insert_post_with_metrics(db, "dark_philosophical", 0, "hook_a", "reel", 0.15)
    _insert_post_with_metrics(db, "dark_philosophical", 0, "hook_a", "reel", 0.14)
    _insert_post_with_metrics(db, "calm_stoic", 0, "hook_b", "reel", 0.02)
    _insert_post_with_metrics(db, "calm_stoic", 0, "hook_b", "reel", 0.01)
    arms = ["dark_philosophical", "calm_stoic"]
    counts = {"dark_philosophical": 0, "calm_stoic": 0}
    for i in range(100):
        choice = policy_bandit.select("mood", arms, db_path=db, seed=i, use_rewards=True)
        counts[choice] += 1
    assert counts["dark_philosophical"] > counts["calm_stoic"]