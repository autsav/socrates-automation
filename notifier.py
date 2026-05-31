"""
Notifier — pluggable post-publish notification system.

Backends (all optional, gracefully degrades):
  - Telegram: instant mobile notification
  - Email: SMTP-based
  - Slack: webhook-based
  - JSONL: always-on local log fallback

Usage: After posting a Reel, call notify_post_published() to remind
the user to manually add a trending sound via the Instagram app.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_notification(payload: dict):
    """Append notification to JSONL log (always works, zero deps)."""
    path = LOG_DIR / "notifications.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")


# ── Telegram Backend ─────────────────────────────────────────────────────────

class TelegramBackend:
    """Send notifications via Telegram Bot API."""

    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, message: str) -> bool:
        import requests
        try:
            resp = requests.post(
                self.api_url,
                json={"chat_id": self.chat_id, "text": message},
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"  [notify] Telegram failed: {e}")
            return False

    def send_video(self, video_path: Path, caption: str = "") -> bool:
        """Send MP4 video file via Telegram sendVideo API (max 50MB)."""
        import requests
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendVideo"
            with open(video_path, "rb") as f:
                resp = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption, "supports_streaming": True},
                    files={"video": (video_path.name, f, "video/mp4")},
                    timeout=120,
                )
            resp.raise_for_status()
            print(f"  [notify] Sent video via Telegram: {video_path.name} ({video_path.stat().st_size / 1024:.0f} KB)")
            return True
        except Exception as e:
            print(f"  [notify] Telegram video failed: {e}")
            return False


# ── Slack Backend ────────────────────────────────────────────────────────────

class SlackBackend:
    """Send notifications via Slack Incoming Webhook."""

    name = "slack"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: str) -> bool:
        import requests
        try:
            resp = requests.post(
                self.webhook_url,
                json={"text": message},
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"  [notify] Slack failed: {e}")
            return False


# ── JSONL Fallback Backend ───────────────────────────────────────────────────

class JsonlBackend:
    """Write notifications to local JSONL file (always available)."""

    name = "jsonl"

    def __init__(self, log_path: Path = LOG_DIR / "notifications.jsonl"):
        self.log_path = log_path

    def send(self, message: str) -> bool:
        _log_notification({
            "backend": "jsonl",
            "timestamp": datetime.now().isoformat(),
            "message": message,
        })
        return True


# ── Notifier Orchestrator ────────────────────────────────────────────────────

class Notifier:
    """
    Send post-publish notifications via configured backends.
    All backends are optional; at minimum JSONL logger always works.
    """

    def __init__(self, cfg):
        self.backends = []

        # Telegram (preferred for mobile instant notification)
        if getattr(cfg, "TELEGRAM_BOT_TOKEN", None) and getattr(cfg, "TELEGRAM_CHAT_ID", None):
            self.backends.append(TelegramBackend(cfg.TELEGRAM_BOT_TOKEN, cfg.TELEGRAM_CHAT_ID))

        # Slack
        if getattr(cfg, "SLACK_WEBHOOK_URL", None):
            self.backends.append(SlackBackend(cfg.SLACK_WEBHOOK_URL))

        # JSONL fallback — always present
        self.backends.append(JsonlBackend())

    def _build_message(
        self,
        post_id: str,
        caption_preview: str,
        mood: str,
        trending_suggestion: str = "",
    ) -> str:
        """Build a rich notification message."""
        lines = [
            "🎬*New Socrates Reel Posted!*",
            "",
            f"*Mood:* {mood}",
            f"*Preview:* {caption_preview[:120]}{'...' if len(caption_preview) > 120 else ''}",
            f"*Link:* https://www.instagram.com/p/{post_id}/",
            "",
            "💡 *ACTION NEEDED:*",
            "Open Instagram, go to your profile, edit this Reel, then tap Add Music.",
        ]

        if trending_suggestion:
            lines.append(f"🎵 *Trending sound suggestion:* {trending_suggestion}")

        lines.extend([
            "",
            "_(This is the only way to attach real trending audio. The API cannot do it automatically.)_",
        ])

        return "\n".join(lines)

    def notify_post_published(
        self,
        post_id: str,
        caption_preview: str,
        mood: str,
        trending_suggestion: str = "",
    ):
        """
        Send notification after a Reel is posted.
        Non-blocking: backend failures are logged but don't raise.
        """
        message = self._build_message(post_id, caption_preview, mood, trending_suggestion)

        # Always log to JSONL first
        _log_notification({
            "event": "post_published",
            "timestamp": datetime.now().isoformat(),
            "post_id": post_id,
            "mood": mood,
            "caption_preview": caption_preview,
            "trending_suggestion": trending_suggestion,
            "message": message,
        })

        sent_any = False
        for backend in self.backends:
            try:
                ok = backend.send(message)
                if ok:
                    print(f"  [notify] Sent via {backend.name}")
                    sent_any = True
            except Exception as e:
                print(f"  [notify] Backend {backend.name} failed: {e}")

        if not sent_any:
            print("  [notify] ⚠️  No external backend succeeded — check logs/notifications.jsonl")

    def notify_manual_reel_ready(
        self,
        reel_path,
        cover_path,
        caption: str,
        mood: str,
        trending_suggestion: str = "",
    ):
        """
        MANUAL MODE: Send the generated Reel video file to the user via Telegram.
        User downloads it and manually posts to Instagram with trending music.
        """
        # Build caption message
        lines = [
            "🎬 Your Socrates Reel is ready!",
            "",
            f"Mood: {mood}",
            f"File: {reel_path.name}",
            "",
            "✍️ CAPTION (copy & paste into Instagram):",
            "-" * 30,
            caption,
            "-" * 30,
            "",
            "🎵 TRENDING SOUND to add:",
        ]
        lines.append(trending_suggestion)
        lines.extend([
            "",
            "📌 STEPS:",
            "1. Download the video above to your gallery",
            "2. Open Instagram → Reels → Upload from gallery",
            "3. Tap 'Add Music' and search the trending sound",
            "4. Paste the caption above",
            "5. Post!",
        ])
        message = "\n".join(lines)

        # Log first
        _log_notification({
            "event": "manual_reel_ready",
            "timestamp": datetime.now().isoformat(),
            "reel_path": str(reel_path),
            "mood": mood,
            "caption_preview": caption[:120],
            "trending_suggestion": trending_suggestion,
            "message": message,
        })

        # Send video + caption via Telegram (only Telegram supports video files)
        sent_video = False
        for backend in self.backends:
            if backend.name == "telegram" and hasattr(backend, "send_video"):
                try:
                    ok = backend.send_video(reel_path, caption="🎬 Your Reel is ready! Download this video and upload to Instagram Reels.")
                    if ok:
                        print(f"  [notify] Sent Reel video via {backend.name}")
                        sent_video = True
                        # Send follow-up text message with caption
                        backend.send(message)
                except Exception as e:
                    print(f"  [notify] Video send via {backend.name} failed: {e}")

        if not sent_video:
            print("  [notify] ⚠️  Could not send video — check logs/notifications.jsonl and GitHub artifacts")


# ── CLI helper ───────────────────────────────────────────────────────────────

def notify_latest(cfg):
    """Send notification for the most recently logged post (workflow helper)."""
    log_path = LOG_DIR / "posts.jsonl"
    if not log_path.exists():
        print("[notify] No posts.jsonl found")
        return

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        if not lines:
            print("[notify] No posts in log")
            return
        latest = json.loads(lines[-1])
    except Exception as e:
        print(f"[notify] Failed to read posts log: {e}")
        return

    notifier = Notifier(cfg)
    notifier.notify_post_published(
        post_id=latest.get("post_id", ""),
        caption_preview=latest.get("caption_preview", ""),
        mood=latest.get("mood", ""),
    )


if __name__ == "__main__":
    import argparse
    from config import Config

    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true", help="Notify for the most recent post in posts.jsonl")
    args = parser.parse_args()

    cfg = Config()
    if args.latest:
        notify_latest(cfg)
    else:
        print("Usage: python notifier.py --latest")
