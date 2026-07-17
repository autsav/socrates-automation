"""Tests for the approval_daemon — covers the auto-post path so future
refactors don't silently break the Telegram-tap → IG-publish loop."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.core.approval as approval
import src.core.approval_daemon as daemon


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(approval, "DATA_DIR", tmp_path)
    monkeypatch.setattr(approval, "APPROVALS_PATH", tmp_path / "approvals.json")


class _FakeCfg:
    """Minimal stand-in: only the attributes approval_daemon._post_approved_reel reads."""

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_drain_pending_posts_posts_approved_reel_with_stashed_payload(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    # Arrange: pretend the bot already notified + human tapped ✅, but never
    # marked applied. reel_path/caption/mood are stashed in the decision.
    approval.record_pending(42)
    approval.annotate_pending_payload(
        42,
        reel_path=str(tmp_path / "fake_reel.mp4"),
        caption="A line about discipline.",
        mood="stark_minimal",
    )
    # Human tapped ✅
    state = approval._load()
    state["decisions"]["42"]["status"] = "approved"
    approval._save(state)

    # Need a real file at reel_path for Path(reel_path).exists()
    (tmp_path / "fake_reel.mp4").write_bytes(b"\x00" * 16)

    cfg = _FakeCfg(
        META_ACCESS_TOKEN="fake_token",
        IG_ACCOUNT_ID="fake_acct",
        CLOUDINARY_CLOUD_NAME="fake_cn",
        CLOUDINARY_API_KEY="fake_key",
        CLOUDINARY_API_SECRET="fake_secret",
    )

    posted_id = "IG_999"
    with patch("src.core.instagram_poster.post_reel_to_instagram", return_value=posted_id) as mock_post, \
         patch("src.core.data_store.mark_posted") as mock_mark:
        count = daemon._drain_pending_posts(cfg)

    assert count == 1
    mock_post.assert_called_once()
    kwargs = mock_post.call_args.kwargs
    assert kwargs["video_path"] == str(tmp_path / "fake_reel.mp4")
    assert kwargs["caption"] == "A line about discipline."
    mock_mark.assert_called_once()
    # Decision must be marked applied so the next loop tick doesn't repost.
    final = approval._load()["decisions"]["42"]
    assert final["applied"] is True
    assert final["applied_at"]


def test_drain_pending_posts_skips_rejected(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    approval.record_pending(7)
    state = approval._load()
    state["decisions"]["7"]["status"] = "rejected"
    approval._save(state)
    cfg = _FakeCfg(
        META_ACCESS_TOKEN="x", IG_ACCOUNT_ID="y",
        CLOUDINARY_CLOUD_NAME="c", CLOUDINARY_API_KEY="k", CLOUDINARY_API_SECRET="s",
    )
    with patch("src.core.instagram_poster.post_reel_to_instagram") as mock_post:
        count = daemon._drain_pending_posts(cfg)
    assert count == 0
    mock_post.assert_not_called()


def test_drain_pending_posts_skips_applied(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    approval.record_pending(7)
    state = approval._load()
    state["decisions"]["7"].update({"status": "approved", "applied": True, "applied_at": "t0"})
    approval._save(state)
    cfg = _FakeCfg(
        META_ACCESS_TOKEN="x", IG_ACCOUNT_ID="y",
        CLOUDINARY_CLOUD_NAME="c", CLOUDINARY_API_KEY="k", CLOUDINARY_API_SECRET="s",
    )
    with patch("src.core.instagram_poster.post_reel_to_instagram") as mock_post:
        count = daemon._drain_pending_posts(cfg)
    assert count == 0
    mock_post.assert_not_called()


def test_drain_pending_posts_skips_optimizer_ids(monkeypatch, tmp_path):
    """Optimizer decisions live in the same store but use namespaced keys."""
    _isolate(monkeypatch, tmp_path)
    approval.record_pending_optimizer(99)  # writes key "opt-99"
    # Pretend the human approved it (a real optimizer challenger; we shouldn't post).
    state = approval._load()
    state["decisions"]["opt-99"]["status"] = "approved"
    approval._save(state)
    cfg = _FakeCfg(
        META_ACCESS_TOKEN="x", IG_ACCOUNT_ID="y",
        CLOUDINARY_CLOUD_NAME="c", CLOUDINARY_API_KEY="k", CLOUDINARY_API_SECRET="s",
    )
    with patch("src.core.instagram_poster.post_reel_to_instagram") as mock_post:
        count = daemon._drain_pending_posts(cfg)
    assert count == 0
    mock_post.assert_not_called()


def test_drain_pending_posts_retries_on_failure(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    approval.record_pending(42)
    approval.annotate_pending_payload(
        42, reel_path=str(tmp_path / "fake_reel.mp4"), caption="c", mood="m"
    )
    state = approval._load()
    state["decisions"]["42"]["status"] = "approved"
    approval._save(state)
    (tmp_path / "fake_reel.mp4").write_bytes(b"")
    cfg = _FakeCfg(
        META_ACCESS_TOKEN="x", IG_ACCOUNT_ID="y",
        CLOUDINARY_CLOUD_NAME="c", CLOUDINARY_API_KEY="k", CLOUDINARY_API_SECRET="s",
    )
    # First call raises (e.g. Cloudinary down); second tick should retry.
    with patch("src.core.instagram_poster.post_reel_to_instagram", side_effect=RuntimeError("boom")) as mock_post:
        count1 = daemon._drain_pending_posts(cfg)
        count2 = daemon._drain_pending_posts(cfg)
    assert count1 == 0
    assert count2 == 0
    assert mock_post.call_count == 2  # both ticks tried
    # Decision must NOT be marked applied (so loop will retry).
    assert approval._load()["decisions"]["42"].get("applied") is None


def test_drain_pending_posts_marks_applied_legacy_no_reel_path(monkeypatch, tmp_path):
    """A row approved before the notifier patch wrote the reel_path has to
    be marked applied (else it retried forever), but with a marker so audit
    can spot it."""
    _isolate(monkeypatch, tmp_path)
    approval.record_pending(99)
    state = approval._load()
    state["decisions"]["99"]["status"] = "approved"
    approval._save(state)
    cfg = _FakeCfg(
        META_ACCESS_TOKEN="x", IG_ACCOUNT_ID="y",
        CLOUDINARY_CLOUD_NAME="c", CLOUDINARY_API_KEY="k", CLOUDINARY_API_SECRET="s",
    )
    with patch("src.core.instagram_poster.post_reel_to_instagram") as mock_post:
        count = daemon._drain_pending_posts(cfg)
    assert count == 0
    mock_post.assert_not_called()
    final = approval._load()["decisions"]["99"]
    assert final["applied"] is True
    assert final["apply_reason"] == "no_reel_path"


def test_post_approved_reel_returns_false_when_meta_creds_missing(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    (tmp_path / "x.mp4").write_bytes(b"")
    # META creds intentionally missing
    cfg = _FakeCfg(
        META_ACCESS_TOKEN=None, IG_ACCOUNT_ID=None,
        CLOUDINARY_CLOUD_NAME="c", CLOUDINARY_API_KEY="k", CLOUDINARY_API_SECRET="s",
    )
    entry = {
        "reel_path": str(tmp_path / "x.mp4"),
        "caption": "c",
    }
    assert daemon._post_approved_reel(1, entry, cfg) is False


def test_post_approved_reel_returns_false_when_reel_missing(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    cfg = _FakeCfg(
        META_ACCESS_TOKEN="t", IG_ACCOUNT_ID="a",
        CLOUDINARY_CLOUD_NAME="c", CLOUDINARY_API_KEY="k", CLOUDINARY_API_SECRET="s",
    )
    entry = {"reel_path": "/nope/does/not/exist.mp4", "caption": "c"}
    assert daemon._post_approved_reel(2, entry, cfg) is False
