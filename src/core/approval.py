"""Two-way Telegram approval — the receiving half of notifier.py's inline
Approve/Reject buttons.

notify_manual_reel_ready(post_row_id=...) sends a Reel with an inline
keyboard (callback_data "approve_<row_id>" / "reject_<row_id>") and records
a "pending" decision. This module polls Telegram's getUpdates for the
resulting callback_query, records the human's tap, and answers the callback
so the button stops spinning.

Deliberately a separate poll step rather than a blocking wait inside
pipeline.py: the scheduled pipeline runs as a short-lived GitHub Actions job
and cannot sit blocked for a human to tap a button hours later. Call
poll_once() from a periodic workflow (or by hand) to pick up decisions as
they arrive; check_decision()/get_decision() read what's been recorded so
far.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
APPROVALS_PATH = DATA_DIR / "approvals.json"

# Callback ids are namespaced so different id-spaces never collide:
#   reel posts   -> "approve_<post_row_id>"        (bare digits, legacy)
#   optimizer    -> "approve_opt-<version_id>"     (opt- prefix)
# The regex captures the full id token; poll_once records every decision into
# the shared store keyed by that token, so whichever workflow polls first does
# NOT strand the other's callbacks (Telegram acks updates globally per bot).
_CALLBACK_RE = re.compile(r"^(approve|reject)_(.+)$")
_OPT_PREFIX = "opt-"


def _load() -> dict:
    try:
        return json.loads(APPROVALS_PATH.read_text())
    except (FileNotFoundError, ValueError):
        return {"offset": None, "decisions": {}}


def _save(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(json.dumps(state, indent=2))


def approve_reject_buttons(post_row_id: int) -> list:
    """Inline keyboard rows for notifier.py's send_video_with_buttons."""
    return [[
        {"text": "✅ Approve", "callback_data": f"approve_{post_row_id}"},
        {"text": "❌ Reject", "callback_data": f"reject_{post_row_id}"},
    ]]


def optimizer_buttons(version_id: int) -> list:
    """Inline keyboard for an optimizer prompt-promotion proposal. Namespaced
    (`opt-<vid>`) so it can never be mistaken for a reel `post_row_id`."""
    return [[
        {"text": "✅ Approve", "callback_data": f"approve_{_OPT_PREFIX}{version_id}"},
        {"text": "❌ Reject", "callback_data": f"reject_{_OPT_PREFIX}{version_id}"},
    ]]


def record_pending_optimizer(version_id: int) -> None:
    """Mark an optimizer challenger as awaiting a human decision (idempotent)."""
    state = _load()
    state.setdefault("decisions", {})
    key = f"{_OPT_PREFIX}{version_id}"
    if key not in state["decisions"]:
        state["decisions"][key] = {"status": "pending", "decided_at": None}
    _save(state)


def get_optimizer_decisions() -> list[dict]:
    """Return decided-but-not-yet-applied optimizer decisions from the shared
    store: [{"version_id": int, "status": "approved"|"rejected"}]. Reads the
    persisted store rather than a fresh poll, so a decision recorded by the
    reel workflow's poll is still seen here."""
    state = _load()
    out = []
    for key, entry in state.get("decisions", {}).items():
        if not key.startswith(_OPT_PREFIX):
            continue
        if entry.get("status") not in ("approved", "rejected"):
            continue
        if entry.get("applied"):
            continue
        try:
            vid = int(key[len(_OPT_PREFIX):])
        except ValueError:
            continue
        out.append({"version_id": vid, "status": entry["status"]})
    return out


def get_optimizer_decision_status(version_id: int) -> str | None:
    """"pending" | "approved" | "rejected" | None (never surfaced) for a challenger."""
    state = _load()
    entry = state.get("decisions", {}).get(f"{_OPT_PREFIX}{version_id}")
    return entry["status"] if entry else None


def mark_optimizer_applied(version_id: int) -> None:
    """Flag an optimizer decision as applied so it is not re-applied on the next run."""
    state = _load()
    key = f"{_OPT_PREFIX}{version_id}"
    entry = state.get("decisions", {}).get(key)
    if entry:
        entry["applied"] = True
        _save(state)


def record_pending(post_row_id: int) -> None:
    """Mark a post as awaiting a human decision. Idempotent — does not
    overwrite an existing (possibly already-decided) entry."""
    state = _load()
    state.setdefault("decisions", {})
    key = str(post_row_id)
    if key not in state["decisions"]:
        state["decisions"][key] = {"status": "pending", "decided_at": None}
    _save(state)


def annotate_pending_payload(
    post_row_id: int,
    *,
    reel_path: str | None = None,
    caption: str | None = None,
    mood: str | None = None,
) -> None:
    """Attach reel-publish context to a pending decision so the
    approval_daemon's auto-poster can find it without re-rendering anything.

    Must be called AFTER record_pending() (creates the entry if missing) and
    BEFORE the Telegram message is sent (so a click recorded before this
    annotation still waits for it on the next loop iteration).

    Idempotent: existing fields are preserved; only the keys you pass are
    written. Missing keys left untouched so a partial call doesn't wipe data.
    """
    state = _load()
    state.setdefault("decisions", {})
    key = str(post_row_id)
    entry = state["decisions"].setdefault(
        key, {"status": "pending", "decided_at": None}
    )
    if reel_path is not None:
        entry["reel_path"] = reel_path
    if caption is not None:
        entry["caption"] = caption
    if mood is not None:
        entry["mood"] = mood
    _save(state)


def get_decision(post_row_id: int) -> str | None:
    """"approved" | "rejected" | "pending" | None (never asked)."""
    state = _load()
    entry = state.get("decisions", {}).get(str(post_row_id))
    return entry["status"] if entry else None


def poll_once(cfg, *, timeout: int = 0) -> list[dict]:
    """Fetch new Telegram updates once, record any approve_/reject_ callback
    decisions, and answer those callbacks. Returns the list of decisions
    recorded this call: [{"post_row_id": int, "status": "approved"|"rejected"}].

    Safe to call repeatedly/on a schedule — already-processed updates are
    skipped via the persisted offset, and re-processing the same callback
    just re-answers it (harmless)."""
    from src.core.notifier import TelegramBackend

    if not (getattr(cfg, "TELEGRAM_BOT_TOKEN", None) and getattr(cfg, "TELEGRAM_CHAT_ID", None)):
        return []

    backend = TelegramBackend(cfg.TELEGRAM_BOT_TOKEN, cfg.TELEGRAM_CHAT_ID)
    state = _load()
    updates = backend.get_updates(offset=state.get("offset"), timeout=timeout)

    decided = []
    max_update_id = state.get("offset", 0) or 0
    for update in updates:
        max_update_id = max(max_update_id, update.get("update_id", 0) + 1)
        callback = update.get("callback_query")
        if not callback:
            continue
        data = callback.get("data", "")
        match = _CALLBACK_RE.match(data)
        if not match:
            continue
        action, row_id = match.group(1), match.group(2)
        status = "approved" if action == "approve" else "rejected"

        state.setdefault("decisions", {})
        # Preserve any prior "applied" flag when re-recording the same callback.
        prev = state["decisions"].get(row_id, {})
        entry = {
            "status": status,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        if prev.get("applied"):
            entry["applied"] = True
        state["decisions"][row_id] = entry
        # Only bare-digit ids are reel post_row_ids — return those for the reel
        # consumer. Namespaced (opt-) decisions are read via get_optimizer_decisions().
        if row_id.isdigit():
            decided.append({"post_row_id": int(row_id), "status": status})

        backend.answer_callback_query(
            callback.get("id", ""),
            text=f"{'Approved ✅' if status == 'approved' else 'Rejected ❌'}",
        )

    state["offset"] = max_update_id
    _save(state)
    return decided


if __name__ == "__main__":
    import argparse
    from config import Config

    parser = argparse.ArgumentParser()
    parser.add_argument("--poll", action="store_true",
                        help="Poll Telegram once for new approve/reject decisions.")
    parser.add_argument("--check", type=int, metavar="ROW_ID",
                        help="Print the recorded decision for a post row id.")
    args = parser.parse_args()

    cfg = Config()
    if args.poll:
        decided = poll_once(cfg)
        print(json.dumps(decided, indent=2))
    elif args.check is not None:
        print(get_decision(args.check))
    else:
        parser.print_help()
