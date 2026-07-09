import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock, patch

import pytest
import requests
from src.visual.image_generator import generate_background, MOOD_PROMPTS


def test_generate_background_success(tmp_path):
    """Happy path: API returns image URL, download succeeds, file saved correctly."""
    with patch("src.visual.image_generator.requests.post") as mock_post, \
         patch("src.visual.image_generator.requests.get") as mock_get, \
         patch("src.visual.image_generator.time.time", return_value=1234567890):
        # Mock Fal.ai API response
        mock_post_resp = MagicMock()
        mock_post_resp.raise_for_status = MagicMock()
        mock_post_resp.json.return_value = {
            "images": [{"url": "https://fal.ai/images/test.jpg"}]
        }
        mock_post.return_value = mock_post_resp

        # Mock image download response
        mock_get_resp = MagicMock()
        mock_get_resp.raise_for_status = MagicMock()
        mock_get_resp.content = b"fake_image_bytes"
        mock_get.return_value = mock_get_resp

        output_dir = tmp_path / "output"
        result = generate_background(
            "dark_philosophical", api_key="test-key", output_dir=str(output_dir)
        )

        assert result.exists()
        assert result.read_bytes() == b"fake_image_bytes"
        assert result.name == "bg_dark_philosophical_1234567890.jpg"

        # Verify API call
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Key test-key"
        assert kwargs["json"]["prompt"] == MOOD_PROMPTS["dark_philosophical"]
        assert kwargs["json"]["image_size"] == "portrait_16_9"
        assert kwargs["timeout"] == 60

        # Verify download call
        mock_get.assert_called_once_with("https://fal.ai/images/test.jpg", timeout=30)


def test_generate_background_default_mood(tmp_path):
    """Unknown mood falls back to default prompt."""
    with patch("src.visual.image_generator.requests.post") as mock_post, \
         patch("src.visual.image_generator.requests.get") as mock_get, \
         patch("src.visual.image_generator.time.time", return_value=0):
        mock_post_resp = MagicMock()
        mock_post_resp.raise_for_status = MagicMock()
        mock_post_resp.json.return_value = {"images": [{"url": "https://fal.ai/images/x.jpg"}]}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.raise_for_status = MagicMock()
        mock_get_resp.content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        mock_get.return_value = mock_get_resp

        generate_background("nonexistent_mood", api_key="key", output_dir=str(tmp_path))

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["prompt"] == MOOD_PROMPTS["dark_philosophical"]


def test_generate_background_api_401(tmp_path):
    """Fal.ai API returns 401 — should raise HTTPError."""
    with patch("src.visual.image_generator.requests.post") as mock_post:
        mock_post_resp = MagicMock()
        mock_post_resp.raise_for_status.side_effect = requests.HTTPError("401 Client Error")
        mock_post.return_value = mock_post_resp

        with pytest.raises(requests.HTTPError):
            generate_background("dark_philosophical", api_key="bad-key", output_dir=str(tmp_path))


def test_generate_background_api_timeout(tmp_path):
    """Fal.ai API call times out."""
    with patch("src.visual.image_generator.requests.post", side_effect=Exception("Read timed out.")):
        with pytest.raises(Exception, match="timed out"):
            generate_background("dark_philosophical", api_key="key", output_dir=str(tmp_path))


def test_generate_background_no_images(tmp_path):
    """Fal.ai returns 200 but empty images list — should raise ValueError."""
    with patch("src.visual.image_generator.requests.post") as mock_post:
        mock_post_resp = MagicMock()
        mock_post_resp.raise_for_status = MagicMock()
        mock_post_resp.json.return_value = {"images": []}
        mock_post.return_value = mock_post_resp

        with pytest.raises(ValueError, match="no images"):
            generate_background("dark_philosophical", api_key="key", output_dir=str(tmp_path))


def test_generate_background_invalid_json(tmp_path):
    """Fal.ai returns non-JSON response — should raise on response.json()."""
    with patch("src.visual.image_generator.requests.post") as mock_post:
        mock_post_resp = MagicMock()
        mock_post_resp.raise_for_status = MagicMock()
        mock_post_resp.json.side_effect = ValueError("No JSON")
        mock_post.return_value = mock_post_resp

        with pytest.raises(ValueError, match="No JSON"):
            generate_background("dark_philosophical", api_key="key", output_dir=str(tmp_path))


def test_generate_background_image_download_fails(tmp_path):
    """Image URL returns 404 on download — should raise HTTPError."""
    with patch("src.visual.image_generator.requests.post") as mock_post, \
         patch("src.visual.image_generator.requests.get") as mock_get:
        mock_post_resp = MagicMock()
        mock_post_resp.raise_for_status = MagicMock()
        mock_post_resp.json.return_value = {"images": [{"url": "https://bad.url/img.jpg"}]}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_get_resp

        with pytest.raises(requests.HTTPError):
            generate_background("dark_philosophical", api_key="key", output_dir=str(tmp_path))


def test_generate_background_missing_image_url(tmp_path):
    """API response has images list but dict missing 'url' key — should raise KeyError."""
    with patch("src.visual.image_generator.requests.post") as mock_post:
        mock_post_resp = MagicMock()
        mock_post_resp.raise_for_status = MagicMock()
        mock_post_resp.json.return_value = {"images": [{}]}
        mock_post.return_value = mock_post_resp

        with pytest.raises(KeyError):
            generate_background("dark_philosophical", api_key="key", output_dir=str(tmp_path))
