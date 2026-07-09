import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics import fetch_post_metrics, ingest_all_pending
from src.core.data_store import init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    from src.core import data_store
    data_store.DB_PATH = tmp_path / "test_pipeline.db"
    init_db()


def test_fetch_post_metrics_parses_response():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"name": "likes", "values": [{"value": 42}]},
            {"name": "comments", "values": [{"value": 5}]},
            {"name": "reach", "values": [{"value": 1000}]},
            {"name": "impressions", "values": [{"value": 2500}]},
        ]
    }

    with patch("src.analytics.metrics.requests.get", return_value=mock_response) as mock_get:
        metrics = fetch_post_metrics("media_123", "token", "ig_123")
        assert metrics["likes"] == 42
        assert metrics["comments"] == 5
        assert metrics["reach"] == 1000
        assert metrics["impressions"] == 2500
        assert metrics["shares"] == 0
        assert metrics["saved"] == 0


def test_ingest_all_pending_skips_when_no_posts():
    with patch("src.analytics.metrics.requests.get") as mock_get:
        count = ingest_all_pending("token", "ig_123", dry_run=True)
        mock_get.assert_not_called()
        assert count == 0
