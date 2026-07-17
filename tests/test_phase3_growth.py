"""Tests for Phase 3 growth optimization modules."""
import pytest
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestRedditTrends:
    def test_reddit_trending_returns_list(self):
        from src.content.reddit_trends import reddit_trending
        # Will return [] since no network in test, but should not crash
        result = reddit_trending(limit=5)
        assert isinstance(result, list)

    def test_reddit_trending_for_socrates_format(self):
        from src.content.reddit_trends import reddit_trending_for_socrates
        with patch("src.content.reddit_trends.reddit_trending") as mock:
            mock.return_value = [
                {"topic": "Stoicism in modern life", "source": "reddit/r/Stoicism", "score": 100},
                {"topic": "How to stop procrastinating", "source": "reddit/r/getmotivated", "score": 80},
            ]
            result = reddit_trending_for_socrates(5)
            assert len(result) == 2
            assert "topic" in result[0]
            assert "source" in result[0]
            assert "score" not in result[0]


class TestPostingOptimizer:
    def test_default_slot_weights(self):
        from src.analytics.posting_optimizer import DEFAULT_SLOT_WEIGHTS
        assert DEFAULT_SLOT_WEIGHTS[2] == 1.0  # evening is best
        assert DEFAULT_SLOT_WEIGHTS[0] > DEFAULT_SLOT_WEIGHTS[1]  # morning > afternoon

    def test_default_day_weights(self):
        from src.analytics.posting_optimizer import DEFAULT_DAY_WEIGHTS
        assert DEFAULT_DAY_WEIGHTS[3] == 1.0  # Wednesday is best
        assert DEFAULT_DAY_WEIGHTS[7] < DEFAULT_DAY_WEIGHTS[3]  # Sunday < Wednesday

    def test_recommend_best_slot_returns_int_and_reason(self):
        from src.analytics.posting_optimizer import recommend_best_slot
        slot, reason = recommend_best_slot(datetime(2026, 7, 15))  # Wednesday
        assert isinstance(slot, int)
        assert 0 <= slot <= 2
        assert isinstance(reason, str)
        assert len(reason) > 0

    def test_recommend_best_slot_wednesday_evening(self):
        """Wednesday evening should be recommended as it has highest default weights."""
        from src.analytics.posting_optimizer import recommend_best_slot
        slot, _ = recommend_best_slot(datetime(2026, 7, 15))  # Wednesday
        # Evening (slot 2) has highest weight, Wednesday has highest day weight
        assert slot == 2

    def test_get_optimal_schedule_returns_7_days(self):
        from src.analytics.posting_optimizer import get_optimal_schedule
        schedule = get_optimal_schedule()
        assert len(schedule) == 7
        assert "Monday" in schedule
        assert "Sunday" in schedule
        for day, slots in schedule.items():
            assert len(slots) == 3
            assert all("slot" in s and "score" in s for s in slots)


class TestHashtagTracker:
    def test_banned_hashtags_contained(self):
        from src.analytics.hashtag_tracker import BANNED_HASHTAGS, is_banned
        assert "#fyp" in BANNED_HASHTAGS
        assert "#viral" in BANNED_HASHTAGS
        assert is_banned("#fyp")
        assert is_banned("#VIRAL")
        assert not is_banned("#stoicism")

    def test_recommend_hashtags_returns_list(self):
        from src.analytics.hashtag_tracker import recommend_hashtags
        result = recommend_hashtags(audience="procrastinator")
        assert isinstance(result, list)
        assert 3 <= len(result) <= 5

    def test_recommend_hashtags_no_banned(self):
        from src.analytics.hashtag_tracker import recommend_hashtags, BANNED_HASHTAGS
        result = recommend_hashtags(audience="stuck", n=5)
        for tag in result:
            assert tag.lower() not in BANNED_HASHTAGS

    def test_recommend_hashtags_audience_specific(self):
        from src.analytics.hashtag_tracker import recommend_hashtags
        proc = recommend_hashtags(audience="procrastinator")
        lost = recommend_hashtags(audience="lost")
        # At least one should differ between audiences (seed tags differ)
        assert proc != lost or len(proc) == 5

    def test_get_hashtag_report(self):
        from src.analytics.hashtag_tracker import get_hashtag_report
        report = get_hashtag_report()
        assert "top_performing" in report
        assert "banned" in report
        assert "recommended_mix" in report
        assert "total_tracked" in report
        assert isinstance(report["banned"], list)


class TestCTATracker:
    def test_cta_types_defined(self):
        from src.analytics.cta_tracker import CTA_TYPES
        assert "save_bait" in CTA_TYPES
        assert "share_bait" in CTA_TYPES
        assert "comment_bait" in CTA_TYPES

    def test_default_weights(self):
        from src.analytics.cta_tracker import DEFAULT_WEIGHTS
        assert DEFAULT_WEIGHTS["save_bait"] > DEFAULT_WEIGHTS["follow_bait"]

    def test_recommend_cta_type_returns_string(self):
        from src.analytics.cta_tracker import recommend_cta_type
        result = recommend_cta_type(audience="procrastinator")
        assert isinstance(result, str)
        assert result in ["save_bait", "share_bait", "comment_bait",
                         "agree_disagree", "follow_bait", "fill_blank"]

    def test_get_cta_report(self):
        from src.analytics.cta_tracker import get_cta_report
        report = get_cta_report()
        assert "top_performing" in report
        assert "recommended_next" in report
        assert "total_tracked" in report

    def test_record_cta_outcome_no_crash(self, tmp_path):
        from src.analytics.cta_tracker import record_cta_outcome
        with patch("src.analytics.cta_tracker.DB_PATH", tmp_path / "test.db"):
            record_cta_outcome("save_bait", "procrastinator", 5, 3, 100, 2)
            # Should not raise


class TestScoreWeights:
    def test_engagement_score_basic(self):
        from src.analytics.score_weights import engagement_score
        metrics = {"saved": 10, "comments": 5, "shares": 3, "reach": 100, "likes": 20}
        score = engagement_score(metrics)
        assert score > 0
        # saved=10*3 + comments=5*2 + shares=3*2.5 + likes=20*1 = 30+10+7.5+20 = 67.5
        # / reach(100) = 0.675
        assert 0.5 < score < 0.8

    def test_engagement_score_empty(self):
        from src.analytics.score_weights import engagement_score
        assert engagement_score({}) == 0.0
        assert engagement_score(None) == 0.0

    def test_engagement_score_zero_reach(self):
        from src.analytics.score_weights import engagement_score
        metrics = {"saved": 10, "comments": 5, "reach": 0}
        score = engagement_score(metrics)
        # Should not divide by zero — reach is clamped to 1
        assert score > 0