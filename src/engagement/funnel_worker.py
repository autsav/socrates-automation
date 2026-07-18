"""Funnel worker — turns trigger comments into bio-link visits.

Hourly sweep: for recent published posts that registered a comment-trigger
keyword (posts.trigger_keyword, set by pipeline._extract_trigger_keyword),
fetch comments via the Graph API, match the keyword (word-boundary,
case-insensitive), and post a short on-brand public reply steering to the
link in bio. Dedup via the same replied-log the auto-reply engine uses, so a
comment is never answered twice by either system.

Never-crash contract: every external call is best-effort — one bad post or
comment skips and the sweep continues. The sweep itself never raises.

Run:  python -m src.engagement.funnel_worker
Cron: .github/workflows/funnel.yml (hourly).
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.engagement.engagement_bot import fetch_comments, post_reply
from src.engagement.auto_reply import REPLIED_LOG_PATH

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"
FUNNEL_LOG_PATH = Path(__file__).parent.parent.parent / "data" / "funnel_log.json"

# Public replies steering to the bio. Rotated per reply. NEVER promise a DM.
REPLY_TEMPLATES = [
    "It's waiting for you — link in bio 🔗",
    "Sent ✨ grab it from the link in bio.",
    "All yours — it's in the bio 🔗",
    "Right here for you: link in bio ✨",
]


def _matches(keyword: str, text: str) -> bool:
    """Word-boundary, case-insensitive keyword match — 'RESET' matches
    'reset 🙏' but not 'presets'."""
    if not keyword or not text:
        return False
    return re.search(rf"\b{re.escape(keyword)}\b", text, re.I) is not None


def _load_replied() -> dict:
    try:
        return json.loads(REPLIED_LOG_PATH.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _save_replied(log: dict) -> None:
    REPLIED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPLIED_LOG_PATH.write_text(json.dumps(log, indent=2))


def _recent_trigger_posts(lookback_posts: int, db_path=DB_PATH) -> list[dict]:
    """Most recent published posts (real IG id) that registered a trigger keyword."""
    try:
        con = sqlite3.connect(str(db_path))
        rows = con.execute(
            "SELECT id, post_id, trigger_keyword FROM posts "
            "WHERE post_id IS NOT NULL AND post_id NOT LIKE 'PENDING_MANUAL%' "
            "AND dry_run = 0 AND trigger_keyword IS NOT NULL "
            "ORDER BY id DESC LIMIT ?", (lookback_posts,)
        ).fetchall()
        con.close()
        return [{"row_id": r[0], "post_id": r[1], "keyword": r[2]} for r in rows]
    except Exception as e:
        print(f"[funnel] DB read failed ({e}) — empty sweep")
        return []


def _append_tally(tally: dict) -> None:
    try:
        try:
            log = json.loads(FUNNEL_LOG_PATH.read_text())
        except (FileNotFoundError, ValueError):
            log = []
        log.append({**tally, "at": datetime.now(timezone.utc).isoformat()})
        FUNNEL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        FUNNEL_LOG_PATH.write_text(json.dumps(log, indent=2))
    except Exception as e:
        print(f"[funnel] tally write failed ({e})")


def run_funnel_sweep(cfg, *, lookback_posts: int = 10, db_path=DB_PATH,
                     fetch=fetch_comments, reply=post_reply) -> dict:
    """One sweep over recent trigger posts. Returns the tally dict."""
    tally = {"posts_checked": 0, "comments_matched": 0, "replies_sent": 0}
    token = getattr(cfg, "META_ACCESS_TOKEN", None)
    if not token:
        print("[funnel] META_ACCESS_TOKEN missing — nothing to do")
        _append_tally(tally)
        return tally

    replied = _load_replied()
    reply_i = 0
    for post in _recent_trigger_posts(lookback_posts, db_path):
        tally["posts_checked"] += 1
        try:
            comments = fetch(post["post_id"], token) or []
        except Exception as e:
            print(f"[funnel] fetch failed for {post['post_id']} ({e}) — skipping post")
            continue
        for c in comments:
            cid, text = str(c.get("id", "")), c.get("text", "")
            if not cid or cid in replied:
                continue
            if not _matches(post["keyword"], text):
                continue
            tally["comments_matched"] += 1
            msg = REPLY_TEMPLATES[reply_i % len(REPLY_TEMPLATES)]
            reply_i += 1
            try:
                if reply(cid, msg, token):
                    replied[cid] = {"reply": msg, "funnel": True,
                                    "at": datetime.now(timezone.utc).isoformat()}
                    tally["replies_sent"] += 1
                    _save_replied(replied)
            except Exception as e:
                print(f"[funnel] reply failed for comment {cid} ({e}) — continuing")
    _append_tally(tally)
    print(f"[funnel] sweep: {tally}")
    return tally


if __name__ == "__main__":
    from config import Config
    run_funnel_sweep(Config())
