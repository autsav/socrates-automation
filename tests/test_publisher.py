from unittest.mock import patch

import pytest

from src.core.publisher import Publisher, default_uploaders
from src.core.uploaders.base import UploadResult
from src.core.uploaders.instagram_uploader import InstagramUploader
from src.core.uploaders.youtube_uploader import YouTubeUploader
from src.core.uploaders.tiktok_uploader import TikTokUploader
from src.core.uploaders.facebook_uploader import FacebookUploader


class _FakeUploader:
    def __init__(self, result: UploadResult):
        self.result = result
        self.calls = []

    def upload(self, video_path, caption, config):
        self.calls.append((video_path, caption, config))
        return self.result


class _RaisingUploader:
    def upload(self, video_path, caption, config):
        raise RuntimeError("boom")


def test_default_uploaders_covers_all_four_platforms():
    uploaders = default_uploaders()
    assert set(uploaders.keys()) == {"instagram", "youtube", "tiktok", "facebook"}
    assert isinstance(uploaders["instagram"], InstagramUploader)
    assert isinstance(uploaders["youtube"], YouTubeUploader)
    assert isinstance(uploaders["tiktok"], TikTokUploader)
    assert isinstance(uploaders["facebook"], FacebookUploader)


def test_publish_routes_to_correct_uploader_with_its_own_config():
    ig_uploader = _FakeUploader(UploadResult(status="published", post_id="123",
                                              post_url="https://www.instagram.com/p/123/"))
    yt_uploader = _FakeUploader(UploadResult(status="draft", note="not connected"))
    publisher = Publisher({"instagram": ig_uploader, "youtube": yt_uploader})

    results = publisher.publish(
        ["instagram", "youtube"],
        video_path="/tmp/reel.mp4",
        caption="Know thyself.",
        configs={"instagram": {"access_token": "tok"}, "youtube": {}},
    )

    assert results[0] == {"platform": "instagram", "status": "published",
                          "post_id": "123", "post_url": "https://www.instagram.com/p/123/",
                          "note": None, "error": None}
    assert results[1]["platform"] == "youtube"
    assert results[1]["status"] == "draft"
    assert ig_uploader.calls[0] == ("/tmp/reel.mp4", "Know thyself.", {"access_token": "tok"})
    assert yt_uploader.calls[0] == ("/tmp/reel.mp4", "Know thyself.", {})


def test_publish_unknown_platform_is_skipped_not_raised():
    publisher = Publisher({})
    results = publisher.publish(["mastodon"], video_path="v.mp4", caption="c")

    assert results[0]["platform"] == "mastodon"
    assert results[0]["status"] == "skipped"


def test_publish_uploader_exception_is_recorded_as_failed_not_propagated():
    publisher = Publisher({"tiktok": _RaisingUploader()})
    results = publisher.publish(["tiktok"], video_path="v.mp4", caption="c")

    assert results[0]["status"] == "failed"
    assert "boom" in results[0]["error"]


def test_publish_one_bad_platform_does_not_block_the_others():
    good = _FakeUploader(UploadResult(status="published", post_id="1"))
    publisher = Publisher({"tiktok": _RaisingUploader(), "instagram": good})

    results = publisher.publish(["tiktok", "instagram"], video_path="v.mp4", caption="c")

    assert results[0]["status"] == "failed"
    assert results[1]["status"] == "published"


def test_upload_result_to_dict_shape():
    result = UploadResult(status="draft", note="pending")
    assert result.to_dict() == {
        "status": "draft", "post_id": None, "post_url": None,
        "note": "pending", "error": None,
    }


def test_instagram_uploader_wraps_post_reel_to_instagram():
    with patch("src.core.uploaders.instagram_uploader.post_reel_to_instagram",
               return_value="999") as mock_post:
        uploader = InstagramUploader()
        result = uploader.upload(
            "reel.mp4", "caption text",
            {"ig_account_id": "ig1", "access_token": "tok", "cloudinary_config": {"cloud_name": "x"}},
        )

    assert result.status == "published"
    assert result.post_id == "999"
    assert result.post_url == "https://www.instagram.com/p/999/"
    mock_post.assert_called_once_with(
        video_path="reel.mp4", caption="caption text", ig_account_id="ig1",
        access_token="tok", cloudinary_config={"cloud_name": "x"}, cover_path=None,
    )


def test_instagram_uploader_missing_config_key_fails_gracefully():
    uploader = InstagramUploader()
    result = uploader.upload("reel.mp4", "caption", {})

    assert result.status == "failed"
    assert "missing config key" in result.error


def test_instagram_uploader_propagates_api_failure_as_failed_result():
    with patch("src.core.uploaders.instagram_uploader.post_reel_to_instagram",
               side_effect=RuntimeError("graph api down")):
        uploader = InstagramUploader()
        result = uploader.upload(
            "reel.mp4", "caption",
            {"ig_account_id": "ig1", "access_token": "tok", "cloudinary_config": {}},
        )

    assert result.status == "failed"
    assert "graph api down" in result.error


@pytest.mark.parametrize("uploader_cls", [YouTubeUploader, TikTokUploader, FacebookUploader])
def test_stub_uploaders_report_draft_with_explanatory_note(uploader_cls):
    result = uploader_cls().upload("reel.mp4", "caption", {})
    assert result.status == "draft"
    assert result.note
