import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock, patch
from src.core.excel_reader import get_mood_prompt


def test_get_mood_prompt_returns_string():
    """Mood prompt should be a non-empty string from Claude."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"text": "  mystical_greek  "}]
    }

    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        MockClient.return_value = mock_client

        mood = get_mood_prompt("Know thyself", "philosophy students", api_key="test-key")
        assert isinstance(mood, str)
        assert len(mood) > 0
        assert mood == "mystical_greek"


def test_get_mood_prompt_fallback_on_error():
    """When Claude API fails, fall back to hardcoded mood."""
    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.side_effect = Exception("API down")
        MockClient.return_value = mock_client

        mood = get_mood_prompt(
            "Know thyself", "overwhelmed",
            api_key="bad-key"
        )
        assert mood == "calm_stoic"


def test_get_mood_prompt_no_api_key():
    """With no API key, return hardcoded fallback."""
    mood = get_mood_prompt("Know thyself", "stuck", api_key="")
    assert mood == "cinematic_hopeful"
