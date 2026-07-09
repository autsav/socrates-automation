import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.analytics_analyst import AnalyticsAnalystAgent
from team.models import AnalyticsReport


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def call(self, role, shared_prefix, role_system, user_content, schema):
        self.calls.append(
            {
                "role": role,
                "shared_prefix": shared_prefix,
                "role_system": role_system,
                "user_content": user_content,
                "schema": schema,
            }
        )
        return self.payload


def _payload():
    return {
        "date": "2026-07-09",
        "total_posts": 10,
        "avg_engagement_rate": 0.05,
        "top_performing_hooks": ["hook_a"],
        "top_performing_moods": ["stoic_calm"],
        "best_posting_times": ["07:00"],
        "worst_performing_content": ["hook_z"],
        "recommendations": ["Post more at 07:00"],
        "follower_growth": 100,
        "save_rate": 0.02,
    }


_FAKE_AGGREGATE = {
    "sample_size": 42,
    "window_days": 90,
    "overall_avg_reach": 1234.5,
    "overall_avg_saved": 12.3,
    "by_mood": {"stoic_calm": {"n": 10, "avg_reach": 1500.0, "avg_saved": 20.0}},
    "by_audience": {"procrastinator": {"n": 8, "avg_reach": 1100.0, "avg_saved": 9.0}},
    "by_slot": {"07:00": {"n": 5, "avg_reach": 1800.0, "avg_saved": 25.0}},
}

_FAKE_RANKINGS = [
    {"hook_id": "hook_a", "composite_score": 0.9, "n": 12, "category": "curiosity"},
    {"hook_id": "hook_z", "composite_score": 0.1, "n": 1, "category": "shock"},
]


@patch("team.analytics_analyst.hook_tracker")
@patch("team.analytics_analyst.data_store")
def test_run_builds_valid_analytics_report(mock_data_store, mock_hook_tracker):
    mock_data_store.aggregate_performance.return_value = _FAKE_AGGREGATE
    mock_hook_tracker.get_all_hook_rankings.return_value = _FAKE_RANKINGS
    mock_hook_tracker.get_hook_leaderboard.return_value = {"top_overall": []}

    client = _FakeClient(_payload())
    agent = AnalyticsAnalystAgent(client)

    report = agent.run()

    assert isinstance(report, AnalyticsReport)
    assert report.total_posts == 10
    assert report.recommendations == ["Post more at 07:00"]


@patch("team.analytics_analyst.hook_tracker")
@patch("team.analytics_analyst.data_store")
def test_run_passes_role_and_stats_to_client(mock_data_store, mock_hook_tracker):
    mock_data_store.aggregate_performance.return_value = _FAKE_AGGREGATE
    mock_hook_tracker.get_all_hook_rankings.return_value = _FAKE_RANKINGS
    mock_hook_tracker.get_hook_leaderboard.return_value = {"top_overall": []}

    client = _FakeClient(_payload())
    agent = AnalyticsAnalystAgent(client)

    agent.run(window_days=90)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["role"] == "analytics_analyst"
    # real aggregated stats show up in the prompt sent to the model
    assert "42" in call["shared_prefix"]
    assert "hook_a" in call["shared_prefix"]
    assert "stoic_calm" in call["shared_prefix"]
    assert call["schema"] is not None


@patch("team.analytics_analyst.hook_tracker")
@patch("team.analytics_analyst.data_store")
def test_run_requests_hook_rankings_within_30_day_cap(mock_data_store, mock_hook_tracker):
    mock_data_store.aggregate_performance.return_value = _FAKE_AGGREGATE
    mock_hook_tracker.get_all_hook_rankings.return_value = _FAKE_RANKINGS
    mock_hook_tracker.get_hook_leaderboard.return_value = {"top_overall": []}

    client = _FakeClient(_payload())
    agent = AnalyticsAnalystAgent(client)

    agent.run(window_days=90)

    mock_data_store.aggregate_performance.assert_called_once_with(90)
    _, kwargs = mock_hook_tracker.get_all_hook_rankings.call_args
    assert kwargs.get("window_days", 30) <= 30


@patch("team.analytics_analyst.hook_tracker")
@patch("team.analytics_analyst.data_store")
def test_run_uses_fixed_now_for_deterministic_date(mock_data_store, mock_hook_tracker):
    mock_data_store.aggregate_performance.return_value = {"sample_size": 0}
    mock_hook_tracker.get_all_hook_rankings.return_value = []
    mock_hook_tracker.get_hook_leaderboard.return_value = {"top_overall": []}

    client = _FakeClient(_payload())
    agent = AnalyticsAnalystAgent(client)

    fixed_now = datetime(2026, 1, 15, 12, 0, 0)
    agent.run(now=fixed_now)

    call = client.calls[0]
    assert "2026-01-15" in call["shared_prefix"]


@patch("team.analytics_analyst.hook_tracker")
@patch("team.analytics_analyst.data_store")
def test_run_handles_zero_sample_size_without_special_case(mock_data_store, mock_hook_tracker):
    mock_data_store.aggregate_performance.return_value = {"sample_size": 0}
    mock_hook_tracker.get_all_hook_rankings.return_value = []
    mock_hook_tracker.get_hook_leaderboard.return_value = {
        "top_overall": [],
        "needs_more_data": [],
    }

    empty_payload = {
        "date": "2026-07-09",
        "total_posts": 0,
        "avg_engagement_rate": 0.0,
        "top_performing_hooks": [],
        "top_performing_moods": [],
        "best_posting_times": [],
        "worst_performing_content": [],
        "recommendations": [],
        "follower_growth": 0,
        "save_rate": 0.0,
    }
    client = _FakeClient(empty_payload)
    agent = AnalyticsAnalystAgent(client)

    report = agent.run()

    assert len(client.calls) == 1  # still calls through, no fallback branch
    assert report.total_posts == 0
    assert report.recommendations == []
