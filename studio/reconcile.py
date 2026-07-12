"""Backfill real Instagram post_id for manually published proposals.

Manual posts are logged with status='proposed' and no post_id. This pulls the
account's recent media via the Graph API and matches each pending proposal by a
caption marker (the chosen hook), so analytics can later fetch metrics for them.
"""
import json
import logging
from datetime import datetime

import requests
from src.core import data_store
GRAPH_URL = "https://graph.instagram.com/v22.0"
log = logging.getLogger(__name__)


def reconcile_token(row_id: int) -> str:
    """Stable, unique, edit-surviving caption marker: '#sq' + base36(row_id)."""
    n = int(row_id)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "#sq0"
    s = ""
    while n > 0:
        n, r = divmod(n, 36)
        s = digits[r] + s
    return "#sq" + s


def fetch_recent_media(token, ig_id, *, getter=requests.get):
    resp = getter(f"{GRAPH_URL}/{ig_id}/media",
                  params={"fields": "id,caption,timestamp", "access_token": token},
                  timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])


def match(proposal, media):
    """Return the post_id whose caption contains the proposal's caption_marker."""
    marker = (proposal.get("caption_marker") or "").strip()
    if not marker:
        return None
    for m in media:
        if marker in (m.get("caption") or ""):
            return m["id"]
    return None


def _marker_for(pending_row):
    try:
        decision = json.loads(pending_row.get("decision_json") or "{}")
    except (ValueError, TypeError):
        return ""
    return decision.get("visual_direction", {}).get("caption_marker", "")


def _parse_ts(s):
    """Parse an IG/ISO timestamp; return datetime or None (best-effort)."""
    if not s:
        return None
    txt = str(s).strip().replace("Z", "+0000")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(txt, fmt)
        except ValueError:
            continue
    return None


def _match_by_time(created_at, media, claimed, window_hours: float = 6.0):
    """Nearest unclaimed media within window_hours of created_at; else None."""
    base = _parse_ts(created_at)
    if base is None:
        return None
    best_id, best_delta = None, None
    for m in media:
        mid = m.get("id")
        if mid in claimed:
            continue
        mt = _parse_ts(m.get("timestamp"))
        if mt is None:
            continue
        # compare naive-safely: use timestamps
        try:
            delta = abs((mt - base).total_seconds())
        except (TypeError, ValueError):
            continue
        if delta <= window_hours * 3600 and (best_delta is None or delta < best_delta):
            best_id, best_delta = mid, delta
    return best_id


def reconcile_pending(token, ig_id, *, getter=requests.get):
    pending = data_store.get_pending_proposals()
    if not pending:
        return 0
    media = fetch_recent_media(token, ig_id, getter=getter)
    claimed = set()
    backfilled = 0
    for p in pending:
        post_id = match({"caption_marker": _marker_for(p)}, media)
        if post_id is None:
            post_id = _match_by_time(p.get("created_at"), media, claimed)
        if post_id:
            claimed.add(post_id)
            data_store.mark_proposal_posted(p["id"], post_id)
            backfilled += 1
    log.info("[reconcile] backfilled %d post(s)", backfilled)
    return backfilled


if __name__ == "__main__":
    from config import Config
    cfg = Config()
    data_store.init_db()
    print(f"Reconciled {reconcile_pending(cfg.META_ACCESS_TOKEN, cfg.IG_ACCOUNT_ID)} post(s).")
