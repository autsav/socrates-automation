"""Backfill real Instagram post_id for manually published proposals.

Manual posts are logged with status='proposed' and no post_id. This pulls the
account's recent media via the Graph API and matches each pending proposal by a
caption marker (the chosen hook), so analytics can later fetch metrics for them.
"""
import json
import logging

import requests
from src.core import data_store
GRAPH_URL = "https://graph.instagram.com/v22.0"
log = logging.getLogger(__name__)


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


def reconcile_pending(token, ig_id, *, getter=requests.get):
    pending = data_store.get_pending_proposals()
    if not pending:
        return 0
    media = fetch_recent_media(token, ig_id, getter=getter)
    backfilled = 0
    for p in pending:
        post_id = match({"caption_marker": _marker_for(p)}, media)
        if post_id:
            data_store.mark_proposal_posted(p["id"], post_id)
            backfilled += 1
    log.info("[reconcile] backfilled %d post(s)", backfilled)
    return backfilled


if __name__ == "__main__":
    from config import Config
    cfg = Config()
    data_store.init_db()
    print(f"Reconciled {reconcile_pending(cfg.META_ACCESS_TOKEN, cfg.IG_ACCOUNT_ID)} post(s).")
