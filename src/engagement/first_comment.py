"""Auto first-comment — the engagement question lives in the comments, not the
caption (recipe #20: a debate question as the post's first comment outperforms
one buried in the caption, and comments are the algorithm's argument signal).

Best-effort: never fails the post.
"""
from __future__ import annotations

from src.utils.logger import get_logger
logger = get_logger(__name__)

import requests

from src.core.instagram_poster import _graph


def post_comment(media_id: str, text: str, access_token: str) -> bool:
    """POST /{media_id}/comments. True on success; never raises."""
    if not (media_id and text and access_token):
        return False
    try:
        r = requests.post(
            f"{_graph(access_token)}/{media_id}/comments",
            params={"message": text, "access_token": access_token},
            timeout=20,
        )
        return r.status_code == 200
    except Exception as e:  # noqa: BLE001
        logger.info(f"  [first-comment] failed ({e})")
        return False


def first_comment_text(quote_data: dict) -> str:
    """Pick the engagement question: story CTA binary ask when it's a debate,
    else the audience's controversy question pool."""
    arc = quote_data.get("arc", "")
    bridge_cta = (quote_data.get("cta") or "").strip()
    if arc == "story" and bridge_cta.rstrip(".").lower().endswith(("comments", "argue", "pick a side")):
        return bridge_cta
    try:
        from src.content.debate_topics import pick_debate
        return pick_debate(quote_data.get("row_number"))["binary_cta"]
    except Exception:  # noqa: BLE001
        return "Agree or disagree? Tell me in one sentence."
