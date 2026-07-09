import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from src.core.notifier import TelegramBackend


class _FakeResponse:
    def __init__(self, json_data=None, ok=True, status_code=200, text=""):
        self._json = json_data or {}
        self.ok = ok
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._json


def _backend():
    return TelegramBackend("fake-token", "fake-chat-id")


def test_send_with_buttons_posts_inline_keyboard(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse({"result": {"message_id": 42}})

    monkeypatch.setattr(requests, "post", fake_post)
    backend = _backend()
    buttons = [[{"text": "✅ Approve", "callback_data": "approve_1"}]]

    message_id = backend.send_with_buttons("hello", buttons)

    assert message_id == 42
    assert captured["url"].endswith("/sendMessage")
    assert captured["json"]["reply_markup"]["inline_keyboard"] == buttons


def test_send_with_buttons_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(requests, "post",
                        lambda *a, **k: _FakeResponse(ok=False, status_code=400, text="bad request"))
    backend = _backend()

    assert backend.send_with_buttons("hello", [[]]) is None


def test_send_video_with_buttons_posts_multipart_with_reply_markup(monkeypatch, tmp_path):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"fake video bytes")
    captured = {}

    def fake_post(url, data=None, files=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["data"] = data
        captured["files"] = files
        return _FakeResponse({"result": {"message_id": 7}})

    monkeypatch.setattr(requests, "post", fake_post)
    backend = _backend()
    buttons = [[{"text": "✅ Approve", "callback_data": "approve_9"},
               {"text": "❌ Reject", "callback_data": "reject_9"}]]

    message_id = backend.send_video_with_buttons(video, "caption", buttons)

    assert message_id == 7
    assert captured["url"].endswith("/sendVideo")
    import json
    assert json.loads(captured["data"]["reply_markup"]) == {"inline_keyboard": buttons}


def test_send_video_with_buttons_missing_file_returns_none(tmp_path):
    backend = _backend()
    assert backend.send_video_with_buttons(tmp_path / "missing.mp4", "c", [[]]) is None


def test_get_updates_returns_result_list(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"result": [{"update_id": 1}, {"update_id": 2}]})

    monkeypatch.setattr(requests, "get", fake_get)
    backend = _backend()

    updates = backend.get_updates(offset=5, timeout=0)

    assert updates == [{"update_id": 1}, {"update_id": 2}]
    assert captured["url"].endswith("/getUpdates")
    assert captured["params"]["offset"] == 5


def test_get_updates_returns_empty_list_on_failure(monkeypatch):
    def fake_get(*a, **k):
        raise ConnectionError("network down")

    monkeypatch.setattr(requests, "get", fake_get)
    backend = _backend()

    assert backend.get_updates() == []


def test_answer_callback_query_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(ok=True)

    monkeypatch.setattr(requests, "post", fake_post)
    backend = _backend()

    ok = backend.answer_callback_query("cbq123", text="Approved")

    assert ok is True
    assert captured["url"].endswith("/answerCallbackQuery")
    assert captured["json"] == {"callback_query_id": "cbq123", "text": "Approved"}
