import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.core.approval as approval


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(approval, "DATA_DIR", tmp_path)
    monkeypatch.setattr(approval, "APPROVALS_PATH", tmp_path / "approvals.json")


def test_approve_reject_buttons_shape():
    buttons = approval.approve_reject_buttons(42)
    assert buttons == [[
        {"text": "✅ Approve", "callback_data": "approve_42"},
        {"text": "❌ Reject", "callback_data": "reject_42"},
    ]]


def test_get_decision_none_when_never_asked(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert approval.get_decision(1) is None


def test_record_pending_then_get_decision_is_pending(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    approval.record_pending(5)
    assert approval.get_decision(5) == "pending"


def test_record_pending_is_idempotent_does_not_clobber_existing_decision(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    approval.record_pending(5)
    # Simulate a decision having already arrived before record_pending is
    # (redundantly) called again.
    state = approval._load()
    state["decisions"]["5"]["status"] = "approved"
    approval._save(state)

    approval.record_pending(5)

    assert approval.get_decision(5) == "approved"


class _FakeCfg:
    TELEGRAM_BOT_TOKEN = "token"
    TELEGRAM_CHAT_ID = "chat"


def test_poll_once_returns_empty_when_telegram_not_configured(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    class _Unconfigured:
        pass

    assert approval.poll_once(_Unconfigured()) == []


def test_poll_once_records_approve_decision_and_answers_callback(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    approval.record_pending(9)

    fake_backend = Mock()
    fake_backend.get_updates.return_value = [
        {"update_id": 100, "callback_query": {"id": "cbq1", "data": "approve_9"}},
    ]
    monkeypatch.setattr("src.core.notifier.TelegramBackend", lambda *a, **k: fake_backend)

    decided = approval.poll_once(_FakeCfg())

    assert decided == [{"post_row_id": 9, "status": "approved"}]
    assert approval.get_decision(9) == "approved"
    fake_backend.answer_callback_query.assert_called_once_with("cbq1", text="Approved ✅")


def test_poll_once_records_reject_decision(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    approval.record_pending(3)

    fake_backend = Mock()
    fake_backend.get_updates.return_value = [
        {"update_id": 1, "callback_query": {"id": "cbq2", "data": "reject_3"}},
    ]
    monkeypatch.setattr("src.core.notifier.TelegramBackend", lambda *a, **k: fake_backend)

    decided = approval.poll_once(_FakeCfg())

    assert decided == [{"post_row_id": 3, "status": "rejected"}]
    assert approval.get_decision(3) == "rejected"


def test_poll_once_ignores_unrelated_callback_data(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    fake_backend = Mock()
    fake_backend.get_updates.return_value = [
        {"update_id": 1, "callback_query": {"id": "cbq3", "data": "some_other_button"}},
    ]
    monkeypatch.setattr("src.core.notifier.TelegramBackend", lambda *a, **k: fake_backend)

    decided = approval.poll_once(_FakeCfg())

    assert decided == []
    fake_backend.answer_callback_query.assert_not_called()


def test_poll_once_advances_offset_so_updates_are_not_reprocessed(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    fake_backend = Mock()
    fake_backend.get_updates.return_value = [
        {"update_id": 55, "callback_query": {"id": "cbq4", "data": "approve_1"}},
    ]
    monkeypatch.setattr("src.core.notifier.TelegramBackend", lambda *a, **k: fake_backend)

    approval.poll_once(_FakeCfg())

    state = approval._load()
    assert state["offset"] == 56

    # A second poll must request updates strictly after the last one seen.
    approval.poll_once(_FakeCfg())
    _, kwargs = fake_backend.get_updates.call_args
    assert kwargs["offset"] == 56


def test_poll_once_skips_updates_without_callback_query(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    fake_backend = Mock()
    fake_backend.get_updates.return_value = [
        {"update_id": 1, "message": {"text": "hi"}},
    ]
    monkeypatch.setattr("src.core.notifier.TelegramBackend", lambda *a, **k: fake_backend)

    decided = approval.poll_once(_FakeCfg())

    assert decided == []
