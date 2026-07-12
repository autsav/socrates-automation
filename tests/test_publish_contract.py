import types
import src.core.instagram_poster as ip


class _Resp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


def test_reel_publish_request_contract(monkeypatch):
    calls = {"post": [], "get": []}

    # Cloudinary → fake public URL, no network.
    monkeypatch.setattr(ip, "upload_video_to_cloudinary", lambda p, c: "https://cdn/v.mp4")
    monkeypatch.setattr(ip, "upload_to_cloudinary", lambda p, c: "https://cdn/cover.jpg")

    def fake_post(url, params=None, timeout=None):
        calls["post"].append((url, params))
        if url.endswith("/media"):
            return _Resp({"id": "CONTAINER_1"})
        if url.endswith("/media_publish"):
            return _Resp({"id": "POST_123"})
        raise AssertionError(f"unexpected POST {url}")

    def fake_get(url, params=None, timeout=None):
        calls["get"].append((url, params))
        return _Resp({"status_code": "FINISHED"})

    monkeypatch.setattr(ip.requests, "post", fake_post)
    monkeypatch.setattr(ip.requests, "get", fake_get)

    post_id = ip.post_reel_to_instagram(
        "video.mp4", "a caption", "IGID", "TOKEN",
        {"cloud_name": "c", "api_key": "k", "api_secret": "s"},
        cover_path="cover.jpg",
    )

    assert post_id == "POST_123"
    # container-create call carries the Reel contract
    create = next(p for (u, p) in calls["post"] if u.endswith("/media"))
    assert create["media_type"] == "REELS"
    assert create["video_url"] == "https://cdn/v.mp4"
    assert create["caption"] == "a caption"
    assert create["cover_url"] == "https://cdn/cover.jpg"
    # publish call references the container
    publish = next(p for (u, p) in calls["post"] if u.endswith("/media_publish"))
    assert publish["creation_id"] == "CONTAINER_1"
