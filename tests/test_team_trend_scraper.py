from unittest.mock import MagicMock, patch

from team.models import TrendReport
from team.trend_scraper import TrendScraperAgent


def _resp(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return r


_HASHTAG_PAYLOAD = {
    "data": {"list": [
        {"hashtag_name": "stoicism", "video_views": 1000, "publish_cnt": 50, "trend": 1},
        {"hashtag_name": "philosophy", "video_views": 500, "publish_cnt": 20, "trend": -1},
    ]}
}
_SOUND_PAYLOAD = {
    "data": {"list": [
        {"title": "Epic Theme", "author": "Composer X", "video_cnt": 300},
    ]}
}


def test_run_success_returns_trend_report():
    agent = TrendScraperAgent()
    with patch.object(agent.session, "get") as mock_get:
        mock_get.side_effect = [_resp(_HASHTAG_PAYLOAD), _resp(_SOUND_PAYLOAD)]
        report = agent.run(niche="stoicism", country="US")

    assert isinstance(report, TrendReport)
    assert report.niche == "stoicism"
    assert report.hashtags[0]["name"] == "stoicism"
    assert report.hashtags[0]["views"] == 1000
    assert report.sounds[0]["title"] == "Epic Theme"
    assert report.fetched_at


def test_run_falls_back_to_generic_hashtags_on_repeated_failure():
    agent = TrendScraperAgent()
    agent.retry_delay = 0  # keep the test fast
    with patch.object(agent.session, "get", side_effect=Exception("network down")):
        report = agent.run(niche="stoicism", country="US")

    names = [h["name"] for h in report.hashtags]
    assert "stoicism" in names
    assert "fyp" in names
    assert report.sounds == []


def test_run_retries_before_succeeding():
    agent = TrendScraperAgent()
    agent.retry_delay = 0
    with patch.object(agent.session, "get") as mock_get:
        mock_get.side_effect = [
            Exception("transient"),
            _resp(_HASHTAG_PAYLOAD),
            _resp(_SOUND_PAYLOAD),
        ]
        report = agent.run(niche="", country="US")

    assert mock_get.call_count == 3
    assert report.hashtags[0]["name"] == "stoicism"


def test_trend_report_round_trips_through_dict():
    report = TrendReport(niche="x", hashtags=[{"name": "a"}], sounds=[], fetched_at="now")
    assert TrendReport.from_dict(report.to_dict()) == report
