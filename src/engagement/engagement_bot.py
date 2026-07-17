"""Post-publish engagement bot — runs after a post goes live to maximize
early comment velocity (the #1 algorithmic signal for Reels reach).

Flow:
1. Wait 2 minutes after posting (let comments accumulate)
2. Fetch comments from Instagram Graph API
3. Generate AI replies using auto_reply engine (Claude-powered)
4. Post replies via Graph API
5. Repeat every 5 minutes for 30 minutes (6 rounds)

This creates the "first-hour engagement spike" that tells Instagram's
algorithm the content is hot, boosting it to more feeds.
"""
import time
import logging
import requests
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v18.0"

# Engagement window: start 2 min after post, run for 30 min
INITIAL_DELAY_SEC = 120     # 2 minutes
ENGAGEMENT_WINDOW_SEC = 1800  # 30 minutes
POLL_INTERVAL_SEC = 300       # 5 minutes between rounds


def fetch_comments(media_id: str, access_token: str) -> list[dict]:
    """Fetch recent comments on a post via Instagram Graph API.

    Returns [{id, text, username, timestamp}] or [] on error.
    """
    try:
        response = requests.get(
            f"{GRAPH_URL}/{media_id}/comments",
            params={
                "fields": "id,text,username,timestamp",
                "access_token": access_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {
                "id": c.get("id", ""),
                "text": c.get("text", ""),
                "username": c.get("username", ""),
                "timestamp": c.get("timestamp", ""),
            }
            for c in data.get("data", [])
        ]
    except Exception as e:
        log.warning(f"[engagement] Failed to fetch comments: {e}")
        return []


def post_reply(comment_id: str, reply_text: str, access_token: str) -> bool:
    """Reply to a comment via Instagram Graph API."""
    try:
        response = requests.post(
            f"{GRAPH_URL}/{comment_id}/replies",
            params={
                "message": reply_text,
                "access_token": access_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        return True
    except Exception as e:
        log.warning(f"[engagement] Failed to post reply: {e}")
        return False


def run_engagement_bot(
    media_id: str,
    access_token: str,
    anthropic_api_key: str,
    post_quote: str = "",
    max_rounds: int = 6,
    delay_sec: int = INITIAL_DELAY_SEC,
    interval_sec: int = POLL_INTERVAL_SEC,
) -> dict:
    """Run the engagement bot for a single post.

    Args:
        media_id: Instagram media ID of the published post
        access_token: Meta Graph API access token
        anthropic_api_key: Claude API key for reply generation
        post_quote: The quote text (for context-aware replies)
        max_rounds: Number of polling rounds (6 = 30 min total)
        delay_sec: Initial delay before first round
        interval_sec: Seconds between rounds

    Returns:
        {replied: int, skipped: int, errors: int}
    """
    from src.engagement.auto_reply import AutoReplyEngine

    engine = AutoReplyEngine(api_key=anthropic_api_key)
    stats = {"replied": 0, "skipped": 0, "errors": 0}

    log.info(f"[engagement] Bot starting in {delay_sec}s for post {media_id}")
    time.sleep(delay_sec)

    for round_num in range(1, max_rounds + 1):
        log.info(f"[engagement] Round {round_num}/{max_rounds}")

        comments = fetch_comments(media_id, access_token)
        if not comments:
            log.info("[engagement] No comments yet — waiting")
            time.sleep(interval_sec)
            continue

        log.info(f"[engagement] Found {len(comments)} comments")

        for comment in comments:
            comment_id = comment["id"]
            comment_text = comment["text"]

            # Skip already-replied comments
            if engine.has_replied(comment_id):
                stats["skipped"] += 1
                continue

            # Generate a reply
            reply = engine.reply_and_track(
                comment_text=comment_text,
                post_quote=post_quote,
                comment_id=comment_id,
            )

            if not reply:
                stats["skipped"] += 1
                continue

            # Post the reply
            if post_reply(comment_id, reply, access_token):
                stats["replied"] += 1
                log.info(f"[engagement] Replied to '{comment_text[:30]}...' → '{reply[:30]}...'")
            else:
                stats["errors"] += 1

        if round_num < max_rounds:
            time.sleep(interval_sec)

    log.info(f"[engagement] Done: {stats['replied']} replied, "
             f"{stats['skipped']} skipped, {stats['errors']} errors")
    return stats


def run_engagement_bot_async(
    media_id: str,
    access_token: str,
    anthropic_api_key: str,
    post_quote: str = "",
):
    """Start the engagement bot in a background thread (non-blocking)."""
    import threading
    thread = threading.Thread(
        target=run_engagement_bot,
        args=(media_id, access_token, anthropic_api_key, post_quote),
        daemon=True,
    )
    thread.start()
    return thread