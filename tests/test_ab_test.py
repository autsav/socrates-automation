import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.ab_test import pick_caption_variant, pick_mood, pick_optimal_slot


class MockDataStore:
    """In-memory data store for testing."""
    def __init__(self):
        self.ab_results = {}

    def get_ab_results(self, dimension, variant_a, variant_b):
        key = (dimension, variant_a, variant_b)
        return self.ab_results.get(key, {"wins_a": 0, "wins_b": 0, "trials": 0})


def test_pick_caption_variant_cold_start_randomises():
    mock_db = MockDataStore()
    results = set()
    for _ in range(20):
        results.add(pick_caption_variant("stuck", mock_db.get_ab_results))
    assert len(results) == 2  # Both 0 and 1 seen


def test_pick_caption_variant_prefers_winner():
    mock_db = MockDataStore()
    mock_db.ab_results[("caption", "hook_first", "story_first")] = {
        "wins_a": 20, "wins_b": 2, "trials": 22
    }
    winners = sum(pick_caption_variant("stuck", mock_db.get_ab_results) for _ in range(100))
    assert winners < 50


def test_pick_optimal_slot_returns_valid_value():
    mock_db = MockDataStore()
    slot = pick_optimal_slot("procrastinator", mock_db.get_ab_results)
    assert slot in [0, 1, 2]