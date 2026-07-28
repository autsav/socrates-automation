"""
Auto-Reply Engine — Claude-powered contextual replies to Instagram comments.

Generates engaging, non-generic replies ("Great post!" is explicitly banned)
that encourage further conversation, and tracks which comments have already
been replied to so the same comment is never answered twice.

Usage:
    from src.engagement.auto_reply import AutoReplyEngine

    engine = AutoReplyEngine(api_key=cfg.ANTHROPIC_API_KEY)
    reply = engine.generate_reply(
        comment_text="This hit different, I needed this today",
        post_quote="The unexamined life is not worth living.",
        comment_id="17895...",
    )
    engine.mark_replied("17895...", reply)
"""

from __future__ import annotations

from src.utils.logger import get_logger
logger = get_logger(__name__)

import json
import random
from pathlib import Path

import httpx

REPLIED_LOG_PATH = Path(__file__).parent.parent.parent / "data" / "replied_comments.json"

_SYSTEM_PROMPT = (
    "You reply to Instagram comments on a Stoic/philosophy quote account. "
    "Write ONE short reply (max 2 sentences, under 150 characters) to the "
    "given comment, in the voice of a thoughtful, slightly provocative "
    "friend — not a brand account. Rules:\n"
    "- Never say generic things like 'Great post!', 'So true!', 'Love this!', "
    "'Thanks for sharing', or any other empty acknowledgement.\n"
    "- Reference something specific in the comment or the quote.\n"
    "- End with a question or a challenge that invites the person to reply "
    "again, when it fits naturally — don't force one onto every reply.\n"
    "- No hashtags, no emoji spam (at most one emoji), no corporate tone.\n"
    "Reply with ONLY the reply text. No quotation marks, no preamble."
)

# Used when no API key is configured, or the API call fails — still avoids
# generic filler, just less tailored than a Claude-generated reply.
_FALLBACK_REPLIES = [
    "Which part of that actually changed something for you — the quote, or admitting it out loud?",
    "Say more — what did it stir up?",
    "That's the part most people scroll past without noticing. What are you doing with it?",
    "Curious what happens next for you after reading that.",
    "Fair pushback. What would you say instead?",
]


class AutoReplyEngine:
    """Generates and tracks contextual replies to Instagram comments."""

    def __init__(self, api_key: str = "", log_path: str | Path = REPLIED_LOG_PATH):
        self.api_key = api_key
        self.log_path = Path(log_path)
        self._replied = self._load_log()

    # ── Tracking ─────────────────────────────────────────────────────────

    def _load_log(self) -> dict:
        if self.log_path.exists():
            try:
                return json.loads(self.log_path.read_text())
            except Exception:
                pass
        return {}

    def _save_log(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(json.dumps(self._replied, indent=2))

    def has_replied(self, comment_id: str) -> bool:
        return comment_id in self._replied

    def mark_replied(self, comment_id: str, reply_text: str) -> None:
        self._replied[comment_id] = {"reply": reply_text}
        self._save_log()

    # ── Reply generation ─────────────────────────────────────────────────

    def _call_claude(self, comment_text: str, post_quote: str) -> str | None:
        if not self.api_key:
            return None
        user = f"Quote the comment is on: {post_quote}\nComment: {comment_text}"
        try:
            transport = httpx.HTTPTransport(local_address="0.0.0.0")
            with httpx.Client(transport=transport) as client:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 100,
                        "system": _SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user}],
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                text = resp.json()["content"][0]["text"].strip().strip('"')
                return text or None
        except Exception as e:
            logger.info(f"  [auto-reply] Claude call failed ({e}) — using fallback")
            return None

    def generate_reply(
        self,
        comment_text: str,
        post_quote: str = "",
        comment_id: str = "",
        seed: int = 0,
    ) -> str:
        """
        Generate an engaging, non-generic reply to a comment.
        Skips generation (returns "") if comment_id has already been replied to.
        """
        if comment_id and self.has_replied(comment_id):
            return ""

        reply = self._call_claude(comment_text, post_quote)
        if not reply:
            if seed:
                random.seed(seed)
            reply = random.choice(_FALLBACK_REPLIES)

        return reply

    def reply_and_track(
        self,
        comment_text: str,
        post_quote: str = "",
        comment_id: str = "",
        seed: int = 0,
    ) -> str:
        """Generate a reply and record it in the replied-comments log."""
        reply = self.generate_reply(comment_text, post_quote, comment_id, seed=seed)
        if reply and comment_id:
            self.mark_replied(comment_id, reply)
        return reply

    def batch_reply(self, comments: list[dict], post_quote: str = "") -> list[dict]:
        """
        Reply to a batch of comments: [{"id": ..., "text": ...}, ...].
        Skips any comment already replied to. Returns
        [{"id": ..., "text": ..., "reply": ...}, ...] for the ones answered.
        """
        results = []
        for i, comment in enumerate(comments):
            comment_id = comment.get("id", "")
            if comment_id and self.has_replied(comment_id):
                continue
            reply = self.reply_and_track(
                comment_text=comment.get("text", ""),
                post_quote=post_quote,
                comment_id=comment_id,
                seed=i,
            )
            results.append({**comment, "reply": reply})
        return results


# ── Convenience export ────────────────────────────────────────────────────

def generate_reply(comment_text: str, post_quote: str = "", api_key: str = "") -> str:
    """One-shot reply generation (no tracking)."""
    return AutoReplyEngine(api_key=api_key).generate_reply(comment_text, post_quote)
