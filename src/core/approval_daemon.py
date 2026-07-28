"""Telegram approval daemon — drains Approve/Reject taps and auto-posts approved reels.

Background process that closes the loop between Telegram's inline-keyboard taps
and the actual Instagram publish. Two responsibilities, one process:

  1. POLL  — call `approval.poll_once()` every couple of seconds so every
     ✅/❌ tap is recorded into `data/approvals.json` promptly (not whenever
     a human happens to invoke `python -m src.core.approval --poll`).
  2. POST  — when a reel decision flips to `approved`, look up the pending
     post row in `data/pipeline.db`, retrieve its reel_path + caption (stored
     alongside the decision by `notify_manual_reel_ready`), and publish via
     `post_reel_to_instagram`. Mark `applied=True` so we never re-post.

Reel-tap callback ids and optimizer-tap callback ids already live in the same
`data/approvals.json` store (approval.py:33-95 namespaces them — `approve_<row>`
vs `approve_opt-<vid>`), so the same poll loop drains both. We only auto-post
digit-only ids (reels); optimizer decisions are surfaced via
`approval.get_optimizer_decisions()` for `optimize.py --apply-decisions`.

Usage:
    # foreground, see logs live:
    .venv/bin/python -m src.core.approval_daemon

    # background, write logs to a file:
    nohup .venv/bin/python -m src.core.approval_daemon \\
        >> logs/approval_daemon.log 2>&1 &

Stops cleanly on SIGINT/SIGTERM. Exits 0 if the optional Telegram creds are
absent (so it can be launched on machines that don't post to IG without
spamming the log).
"""
from __future__ import annotations

from src.utils.logger import get_logger
logger = get_logger(__name__)

import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.core.approval import (
    APPROVALS_PATH,
    _load as _load_approvals,
    _save as _save_approvals,
    poll_once,
)

# Polling cadence — Telegram long-poll timeout=0 is fine, so we sleep between
# calls instead of holding one connection open for minutes. 2s gives near-
# instant UX without hammering the Bot API rate limit (≈30 req/sec global).
POLL_INTERVAL_SEC = 2.0

# Reel-tap ids are bare digits (approval.py:176 `if row_id.isdigit()`).
# Anything namespaced (opt-…) is the optimizer's and not our concern here.


def _post_approved_reel(row_id: int, entry: dict, cfg) -> bool:
    """Publish one approved reel to Instagram.

    `entry` is the record from `data/approvals.json["decisions"][row_id]`,
    augmented at notify time with `reel_path`, `caption`, and `mood` (see
    `notify_manual_reel_ready` caller — those fields are saved next to the
    pending decision by the patch below). Returns True if posted, False if
    anything went wrong (caller will leave `applied=False` so a future poll
    retries — but only once, since on success we flip `applied`).
    """
    from src.core.instagram_poster import post_reel_to_instagram

    reel_path = entry.get("reel_path")
    caption = entry.get("caption") or ""
    if not reel_path or not Path(reel_path).exists():
        logger.info(f"  [poster] row {row_id}: reel missing on disk ({reel_path!r}), skipping")
        return False

    access_token = getattr(cfg, "META_ACCESS_TOKEN", None)
    ig_account_id = getattr(cfg, "IG_ACCOUNT_ID", None)
    if not (access_token and ig_account_id):
        logger.info(f"  [poster] row {row_id}: missing META creds, skipping")
        return False

    try:
        post_id = post_reel_to_instagram(
            video_path=reel_path,
            caption=caption,
            ig_account_id=ig_account_id,
            access_token=access_token,
            cloudinary_config={
                "cloud_name": cfg.CLOUDINARY_CLOUD_NAME,
                "api_key": cfg.CLOUDINARY_API_KEY,
                "api_secret": cfg.CLOUDINARY_API_SECRET,
            },
        )
        logger.info(f"  [poster] row {row_id}: posted → {post_id}")
        # Update the posts table with the real IG id so analytics can find it.
        try:
            from src.core.data_store import mark_posted
            # image_path is unused for reels; pass empty string rather than
            # None to match mark_posted's str-typed signature.
            mark_posted(row_id, post_id, "", reel_path)
        except Exception as e:
            logger.info(f"  [poster] row {row_id}: mark_posted failed (non-fatal): {e}")
        return True
    except Exception as e:
        logger.info(f"  [poster] row {row_id}: post_reel_to_instagram failed: {e}")
        return False


def _drain_pending_posts(cfg) -> int:
    """Walk every approved-but-not-yet-applied reel decision; post any that
    are ready. Returns the count of successful posts this call.

    A decision is "ready" when:
      * key is digit-only (a reel post_row_id, not an optimizer opt-<vid>)
      * status == "approved"
      * applied is not True
      * reel_path is present (set by notify_manual_reel_ready → approval.py patch)
    """
    state = _load_approvals()
    decisions = state.get("decisions", {})
    posted = 0
    for key, entry in decisions.items():
        if not key.isdigit():
            continue  # opt-<…> or future namespaces — ignore
        if entry.get("status") != "approved":
            continue
        if entry.get("applied"):
            continue
        if not entry.get("reel_path"):
            # Legacy row from before we patched notify_manual_reel_ready to
            # stash the path here — can't auto-post without it.
            logger.info(f"  [poster] row {key}: approved but no reel_path stored; "
                  f"marking applied to avoid infinite retry")
            entry["applied"] = True
            entry["applied_at"] = datetime.now(timezone.utc).isoformat()
            entry["apply_reason"] = "no_reel_path"
            _save_approvals(state)
            continue
        row_id = int(key)
        if _post_approved_reel(row_id, entry, cfg):
            entry["applied"] = True
            entry["applied_at"] = datetime.now(timezone.utc).isoformat()
            posted += 1
            _save_approvals(state)
        else:
            # Don't flip applied; leave for next loop / human inspection.
            pass
    return posted


_running = True


def _stop(*_):
    global _running
    _running = False
    logger.info("\n[daemon] stop signal received, exiting after current cycle…")


def main() -> int:
    # Imported here so `python -m src.core.approval_daemon --help` works
    # even if config import has side effects.
    from config import Config

    cfg = Config()
    if not (getattr(cfg, "TELEGRAM_BOT_TOKEN", None) and getattr(cfg, "TELEGRAM_CHAT_ID", None)):
        logger.info("[daemon] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set; nothing to do")
        return 0

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info(f"[daemon] started at {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"[daemon] poll interval = {POLL_INTERVAL_SEC}s; approvals store = {APPROVALS_PATH}")

    while _running:
        try:
            new = poll_once(cfg, timeout=0)
            if new:
                logger.info(f"[daemon] poll → {len(new)} new reel decision(s): {new}")
            posted = _drain_pending_posts(cfg)
            if posted:
                logger.info(f"[daemon] auto-posted {posted} reel(s)")
        except Exception as e:
            # Never let the daemon die on a single bad poll.
            logger.info(f"[daemon] poll cycle error (continuing): {e}")
        # Sleep in small chunks so SIGTERM is responsive even mid-sleep.
        slept = 0.0
        while _running and slept < POLL_INTERVAL_SEC:
            time.sleep(0.25)
            slept += 0.25

    logger.info("[daemon] stopped cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
