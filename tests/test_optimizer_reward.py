import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import reward


def test_reward_weights_saves_highest():
    saves = reward.reward({"saved": 10, "reach": 100})
    likes = reward.reward({"likes": 10, "reach": 100})
    assert saves > likes


def test_reward_is_rate_not_volume():
    small = reward.reward({"saved": 5, "reach": 50})
    big = reward.reward({"saved": 50, "reach": 500})
    assert abs(small - big) < 1e-9   # same rate → same reward


def test_reward_missing_keys_zero():
    assert reward.reward({}) == 0.0
