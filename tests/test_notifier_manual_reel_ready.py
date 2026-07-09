import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.core.approval as approval
from src.core.notifier import Notifier


class _FakeCfg:
    TELEGRAM_BOT_TOKEN = "token"
    TELEGRAM_CHAT_ID = "chat"
    SLACK_WEBHOOK_URL = None


def _isolate_approvals(monkeypatch, tmp_path):
    monkeypatch.setattr(approval, "DATA_DIR", tmp_path)
    monkeypatch.setattr(approval, "APPROVALS_PATH", tmp_path / "approvals.json")


def test_notify_manual_reel_ready_with_post_row_id_sends_buttons_and_records_pending(
    monkeypatch, tmp_path,
):
    _isolate_approvals(monkeypatch, tmp_path)
    notifier = Notifier(_FakeCfg())
    telegram_backend = notifier.backends[0]
    assert telegram_backend.name == "telegram"

    monkeypatch.setattr(telegram_backend, "send_video_with_buttons",
                        Mock(return_value=123))
    monkeypatch.setattr(telegram_backend, "send", Mock(return_value=True))

    reel_path = tmp_path / "reel.mp4"
    reel_path.write_bytes(b"fake")

    notifier.notify_manual_reel_ready(
        reel_path=reel_path,
        cover_path=tmp_path / "cover.jpg",
        caption="Some caption",
        mood="dark_philosophical",
        trending_suggestion="trending track",
        post_row_id=17,
    )

    telegram_backend.send_video_with_buttons.assert_called_once()
    call_args = telegram_backend.send_video_with_buttons.call_args
    assert call_args.args[0] == reel_path
    assert call_args.kwargs["buttons"] == approval.approve_reject_buttons(17)
    assert approval.get_decision(17) == "pending"


def test_notify_manual_reel_ready_without_post_row_id_uses_plain_send_video(
    monkeypatch, tmp_path,
):
    notifier = Notifier(_FakeCfg())
    telegram_backend = notifier.backends[0]

    monkeypatch.setattr(telegram_backend, "send_video_with_buttons", Mock())
    monkeypatch.setattr(telegram_backend, "send_video", Mock(return_value=True))
    monkeypatch.setattr(telegram_backend, "send", Mock(return_value=True))

    reel_path = tmp_path / "reel.mp4"
    reel_path.write_bytes(b"fake")

    notifier.notify_manual_reel_ready(
        reel_path=reel_path,
        cover_path=tmp_path / "cover.jpg",
        caption="Some caption",
        mood="dark_philosophical",
        trending_suggestion="trending track",
    )

    telegram_backend.send_video.assert_called_once()
    telegram_backend.send_video_with_buttons.assert_not_called()
