import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.token_manager import refresh_if_needed, _is_token_expiring_soon


def test_is_token_expiring_soon_true():
    soon = datetime.now(timezone.utc) + timedelta(days=3)
    assert _is_token_expiring_soon(soon) is True


def test_is_token_expiring_soon_false():
    future = datetime.now(timezone.utc) + timedelta(days=30)
    assert _is_token_expiring_soon(future) is False


def test_refresh_if_needed_returns_current_when_fresh():
    token = "valid_token_123"
    future = datetime.now(timezone.utc) + timedelta(days=30)

    with patch("src.core.token_manager.requests.post") as mock_post:
        result = refresh_if_needed(token, "app_id", "app_secret", expires_at=future)
        mock_post.assert_not_called()
        assert result == token


def test_refresh_if_needed_calls_api_when_expiring():
    token = "old_token"
    soon = datetime.now(timezone.utc) + timedelta(days=3)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"access_token": "new_token_456"}

    with patch("src.core.token_manager.requests.post", return_value=mock_response) as mock_post:
        result = refresh_if_needed(token, "app_id", "app_secret", expires_at=soon)
        mock_post.assert_called_once()
        assert result == "new_token_456"
