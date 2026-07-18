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

LOG_DIR = Path(__file__).parent.parent.parent / "logs"

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
        video_path = Path(video_path)  # coerce string → Path
        if not video_path.exists():
            print(f"  [notify] Video file not found: {video_path}")
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendVideo"
            with open(video_path, "rb") as f:
                resp = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption, "supports_streaming": True},
                    files={"video": (video_path.name, f, "video/mp4")},
                    timeout=120,
                )
            if not resp.ok:
                print(f"  [notify] Telegram API error {resp.status_code}: {resp.text[:200]}")
                return False
            print(f"  [notify] Sent video via Telegram: {video_path.name} ({video_path.stat().st_size / 1024:.0f} KB)")
            return True
        except Exception as e:
            print(f"  [notify] Telegram video send failed: {e}")
            return False

    def send_photo(self, photo_path: Path, caption: str = "") -> bool:
        """Send image file via Telegram sendPhoto API."""
        import requests
        photo_path = Path(photo_path)
        if not photo_path.exists():
            print(f"  [notify] Photo file not found: {photo_path}")
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            with open(photo_path, "rb") as f:
                resp = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption},
                    files={"photo": (photo_path.name, f, "image/jpeg")},
                    timeout=60,
                )
            if not resp.ok:
                print(f"  [notify] Telegram API error {resp.status_code}: {resp.text[:200]}")
                return False
            print(f"  [notify] Sent photo via Telegram: {photo_path.name}")
            return True
        except Exception as e:
            print(f"  [notify] Telegram photo send failed: {e}")
            return False

    def send_with_buttons(self, message: str, buttons: list) -> int | None:
        """Send a text message with an inline keyboard. `buttons` is a list
        of rows, each row a list of {"text": ..., "callback_data": ...} (or
        {"text": ..., "url": ...}) dicts. Returns the sent message_id, or
        None on failure."""
        import requests
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": self.chat_id, "text": message,
                     "reply_markup": {"inline_keyboard": buttons}},
                timeout=15,
            )
            if not resp.ok:
                print(f"  [notify] Telegram API error {resp.status_code}: {resp.text[:200]}")
                return None
            return resp.json().get("result", {}).get("message_id")
        except Exception as e:
            print(f"  [notify] Telegram send_with_buttons failed: {e}")
            return None

    def send_video_with_buttons(self, video_path: Path, caption: str,
                                buttons: list) -> int | None:
        """Send a video with an inline keyboard attached (see
        send_with_buttons for the `buttons` shape). Returns the sent
        message_id, or None on failure."""
        import json as _json
        import requests
        video_path = Path(video_path)
        if not video_path.exists():
            print(f"  [notify] Video file not found: {video_path}")
            return None
        try:
            with open(video_path, "rb") as f:
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendVideo",
                    data={"chat_id": self.chat_id, "caption": caption,
                         "supports_streaming": True,
                         "reply_markup": _json.dumps({"inline_keyboard": buttons})},
                    files={"video": (video_path.name, f, "video/mp4")},
                    timeout=120,
                )
            if not resp.ok:
                print(f"  [notify] Telegram API error {resp.status_code}: {resp.text[:200]}")
                return None
            return resp.json().get("result", {}).get("message_id")
        except Exception as e:
            print(f"  [notify] Telegram send_video_with_buttons failed: {e}")
            return None

    def get_updates(self, offset: int | None = None, timeout: int = 0) -> list:
        """Long-poll Telegram's getUpdates for new updates (messages, button
        presses). `offset` should be one past the highest update_id already
        processed, to avoid reprocessing. Returns [] on any failure —
        callers should treat that as "no new updates" and retry later."""
        import requests
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{self.bot_token}/getUpdates",
                params=params, timeout=timeout + 15,
            )
            if not resp.ok:
                print(f"  [notify] getUpdates failed: {resp.status_code} {resp.text[:200]}")
                return []
            return resp.json().get("result", [])
        except Exception as e:
            print(f"  [notify] getUpdates failed: {e}")
            return []

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> bool:
        """Acknowledge a button press so Telegram stops showing its spinner."""
        import requests
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
                timeout=10,
            )
            return resp.ok
        except Exception as e:
            print(f"  [notify] answerCallbackQuery failed: {e}")
            return False

    def send_document(self, doc_path: Path, caption: str = "") -> bool:
        """Send document file via Telegram sendDocument API."""
        import requests
        doc_path = Path(doc_path)
        if not doc_path.exists():
            print(f"  [notify] Document file not found: {doc_path}")
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
            with open(doc_path, "rb") as f:
                resp = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption},
                    files={"document": (doc_path.name, f, "image/jpeg")},
                    timeout=60,
                )
            if not resp.ok:
                print(f"  [notify] Telegram API error {resp.status_code}: {resp.text[:200]}")
                return False
            print(f"  [notify] Sent document via Telegram: {doc_path.name}")
            return True
        except Exception as e:
            print(f"  [notify] Telegram document send failed: {e}")
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

    def send_document(self, doc_path, caption: str = "") -> bool:
        """Send a document to any backend that supports it (Telegram)."""
        sent = False
        for backend in self.backends:
            if hasattr(backend, "send_document"):
                sent = backend.send_document(doc_path, caption=caption) or sent
        return sent

    def send_message_with_buttons(self, message: str, buttons: list) -> bool:
        """Send a text message with an inline keyboard to any backend that supports
        it (Telegram). Used by the optimizer to surface prompt proposals with
        Approve/Reject buttons. Returns True if at least one backend sent it."""
        sent = False
        for backend in self.backends:
            if hasattr(backend, "send_with_buttons"):
                mid = backend.send_with_buttons(message, buttons)
                sent = sent or (mid is not None)
        return sent

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
        post_row_id: int | None = None,
    ):
        """
        MANUAL MODE: Send the generated Reel video file to the user via Telegram.
        User downloads it and manually posts to Instagram with trending music.

        When post_row_id is given, the video is sent with inline Approve/
        Reject buttons (two-way: src.core.approval.poll_once() picks up the
        resulting tap) instead of a plain video message.
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
            "",
            "🤖 AFTER POSTING: Run the engagement bot to auto-reply to comments:",
            "   python -m src.engagement.trigger_bot <YOUR_POST_ID>",
            "   (Find the post_id in Instagram → your post → ... → Copy Link)",
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
            if backend.name != "telegram":
                continue
            try:
                if post_row_id is not None and hasattr(backend, "send_video_with_buttons"):
                    from src.core.approval import (
                        approve_reject_buttons,
                        record_pending,
                        annotate_pending_payload,
                    )
                    ok = backend.send_video_with_buttons(
                        reel_path,
                        caption="🎬 Your Reel is ready! Approve to confirm you'll post it, "
                                "or reject to skip this proposal.",
                        buttons=approve_reject_buttons(post_row_id),
                    )
                    if ok:
                        record_pending(post_row_id)
                        # Persist reel+caption+mood so approval_daemon's
                        # auto-poster can find them when the human taps ✅.
                        annotate_pending_payload(
                            post_row_id,
                            reel_path=str(reel_path),
                            caption=caption,
                            mood=mood,
                        )
                elif hasattr(backend, "send_video"):
                    ok = backend.send_video(reel_path, caption="🎬 Your Reel is ready! Download this video and upload to Instagram Reels.")
                else:
                    ok = False
                if ok:
                    print(f"  [notify] Sent Reel video via {backend.name}")
                    sent_video = True
                    # Send follow-up text message with caption
                    backend.send(message)
            except Exception as e:
                print(f"  [notify] Video send via {backend.name} failed: {e}")

        if not sent_video:
            print("  [notify] ⚠️  Could not send video — check logs/notifications.jsonl and GitHub artifacts")

    def notify_story_teaser(
        self,
        quote: str,
        post_time_str: str = "",
        reel_path=None,
    ) -> None:
        """
        Point 29: Story Teaser notification.
        Send a "going live in 15 min" alert + teaser text to Telegram
        so the user can post a Story countdown sticker before the Reel drops.
        """
        lines = [
            "🕐 STORY TEASER — post this NOW (15 min before Reel):",
            "",
            "Text for Story slide:",
            "─" * 28,
            f"⚡ Something drops at {post_time_str or 'soon'}.",
            "",
            f"Hint: \"{quote[:60]}{'...' if len(quote) > 60 else ''}\"",
            "",
            "Watch for it. You'll want to save it.",
            "─" * 28,
            "",
            "📌 Add a countdown sticker in Stories pointing to post time.",
            "Use the 'Quiz' sticker: 'Ready to be challenged? Y/N'",
        ]
        message = "\n".join(lines)

        _log_notification({
            "event": "story_teaser",
            "timestamp": datetime.now().isoformat(),
            "quote_preview": quote[:80],
            "post_time": post_time_str,
        })

        for backend in self.backends:
            try:
                backend.send(message)
                break
            except Exception as e:
                print(f"  [notify] Story teaser send failed via {backend.name}: {e}")

        print(f"  [notify] Story teaser dispatched")

    def notify_twitter_thread(
        self,
        quote: str,
        hook_text: str,
        cta_text: str = "",
        philosopher: str = "Socrates",
        post_url: str = "",
    ) -> None:
        """
        Point 30: Cross-Platform Twitter/X Thread.
        Generates an 8-tweet thread from the Reel content and sends to Telegram
        for manual posting. Hook tweet + context + quote breakdown + CTA.
        """
        tweets: list[str] = []

        # Tweet 1: Hook (bold claim — max engagement)
        tweets.append(f"{hook_text}\n\n🧵 Thread:")

        # Tweet 2: Quote
        tweets.append(f'"{quote}"\n— {philosopher}')

        # Tweet 3-6: Breakdown
        context_lines = [
            f"This was written over 2,000 years ago.\n\nIt's still more relevant than anything posted today.",
            f"Most people scroll past this.\n\nThe ones who stop — they're different.\n\nWhich are you?",
            f"Ancient wisdom survives because it describes something permanent about human nature.\n\nThis is one of those things.",
            f"The question isn't whether {philosopher} was right.\n\nThe question is: what are you going to do about it?",
        ]
        tweets.extend(context_lines)

        # Tweet 7: Save bait
        tweets.append(
            "Save this thread.\n\n"
            "Read it again when you're about to quit, procrastinate, or play small.\n\n"
            "It works."
        )

        # Tweet 8: CTA
        cta = cta_text or f"Follow for daily {philosopher}-style challenges.\n\nYour comfort zone won't like it."
        if post_url:
            cta += f"\n\n🎬 Watch the full Reel: {post_url}"
        tweets.append(cta)

        # Format for Telegram
        lines = ["🐦 TWITTER/X THREAD — post manually:", ""]
        for i, tweet in enumerate(tweets, 1):
            lines.append(f"[{i}/{len(tweets)}]")
            lines.append(tweet)
            lines.append("")

        message = "\n".join(lines)

        _log_notification({
            "event": "twitter_thread",
            "timestamp": datetime.now().isoformat(),
            "tweet_count": len(tweets),
            "hook": hook_text,
        })

        for backend in self.backends:
            try:
                backend.send(message)
                break
            except Exception as e:
                print(f"  [notify] Twitter thread send failed via {backend.name}: {e}")

        print(f"  [notify] Twitter thread ({len(tweets)} tweets) dispatched")

    def notify_seed_comments(
        self,
        post_url: str,
        quote: str,
        audience: str = "stuck",
        post_id: str = "",
    ) -> None:
        """
        Point 33: Comment Seeding Protocol.
        Sends 3 controversy-position seed comments to Telegram immediately
        after posting. User posts these manually in the first 5 minutes to
        trigger the algorithm's engagement window.
        """
        try:
            from src.engagement.comment_bait import CommentBait
            bait = CommentBait(audience=audience)
        except ImportError:
            bait = None

        seed_comments: list[str] = []
        styles = ["confrontational", "direct", "supportive"]

        if bait:
            for style in styles:
                try:
                    seed_comments.append(bait.generate_question(style=style, quote=quote))
                except Exception:
                    pass

        if not seed_comments:
            seed_comments = [
                "This hit different. 🔥",
                "Needed this today. Share if you agree.",
                "Drop a ❤️ if you've felt this.",
            ]

        lines = [
            "💬 COMMENT SEEDING — post these in the FIRST 5 MINUTES:",
            f"Post: {post_url or post_id}",
            "",
        ]
        for i, comment in enumerate(seed_comments[:3], 1):
            lines.append(f"{i}. {comment}")

        lines.extend([
            "",
            "⚡ Post all 3 within 5 minutes of going live.",
            "Rotate between them. Reply to yourself to keep thread alive.",
        ])
        message = "\n".join(lines)

        _log_notification({
            "event": "seed_comments",
            "timestamp": datetime.now().isoformat(),
            "post_id": post_id,
            "post_url": post_url,
            "seed_comments": seed_comments,
        })

        for backend in self.backends:
            try:
                backend.send(message)
                break  # send once (Telegram or first available)
            except Exception as e:
                print(f"  [notify] Seed comment send failed via {backend.name}: {e}")

        print(f"  [notify] Seed comments dispatched ({len(seed_comments)} comments)")

    def notify_bio_link_rotation(
        self,
        current_link: str = "",
        options: list[str] | None = None,
    ) -> None:
        """
        Point 38: Bio Link Optimisation.
        Sends a prompt to rotate the bio link and track performance.
        Rotate between: latest Reel | newsletter | wallpaper pack | source text.
        """
        default_options = [
            "Latest Reel (most reach → algorithm boost)",
            "Wallpaper pack (saves → algorithmic signal)",
            "Newsletter signup (email list building)",
            "Source philosophy text (authority building)",
        ]
        opts = options or default_options
        lines = [
            "🔗 BIO LINK ROTATION — update your link now:",
            "",
            "Options (rotate weekly, track clicks):",
        ]
        for i, opt in enumerate(opts, 1):
            marker = "→" if i == 1 else " "
            lines.append(f"{marker} {i}. {opt}")

        if current_link:
            lines.extend(["", f"Current: {current_link}"])

        lines.extend([
            "",
            "Tip: Use Linktree or Beacons to track which option gets most clicks.",
            "Update every Sunday. Track for 30 days before switching.",
        ])
        message = "\n".join(lines)

        _log_notification({"event": "bio_link_rotation", "timestamp": datetime.now().isoformat()})
        for backend in self.backends:
            try:
                backend.send(message)
                break
            except Exception:
                pass

    def notify_highlight_category(
        self,
        category: str,
        story_preview: str = "",
    ) -> None:
        """
        Point 39: Highlight Strategy.
        Notifies user to organise Story into the correct Highlight category.
        Categories: Wisdom | Action | Mindset | Questions
        """
        categories = {
            "wisdom": "WISDOM — eternal quotes that stop people mid-scroll",
            "action": "ACTION — get-up-and-do-it content",
            "mindset": "MINDSET — shift in how you see yourself",
            "questions": "QUESTIONS — engagement-first content that forces comments",
        }
        cat_key = category.lower()
        cat_label = categories.get(cat_key, category)

        lines = [
            f"📌 HIGHLIGHT: Add this Story to → {cat_label}",
            "",
        ]
        if story_preview:
            lines.extend([f"Story preview: {story_preview[:80]}", ""])
        lines.extend([
            "Steps: Story → More → Highlight → Select or Create",
            f"Cover: Use the Σ symbol on {category.upper()} background",
        ])
        message = "\n".join(lines)

        _log_notification({
            "event": "highlight_category",
            "timestamp": datetime.now().isoformat(),
            "category": category,
        })
        for backend in self.backends:
            try:
                backend.send(message)
                break
            except Exception:
                pass

    def notify_telegram_channel_post(
        self,
        quote: str,
        attribution: str = "— Socrates",
        instagram_url: str = "",
        image_path=None,
    ) -> None:
        """
        Point 54: Telegram Channel Expansion.
        Auto-post high-res image + quote text to Telegram channel
        with link back to Instagram.
        """
        lines = [
            f'"{quote}"',
            f"{attribution}",
            "",
        ]
        if instagram_url:
            lines.append(f"📱 Full Reel: {instagram_url}")
        lines.extend(["", "@stoic.start"])
        message = "\n".join(lines)

        _log_notification({
            "event": "telegram_channel_post",
            "timestamp": datetime.now().isoformat(),
            "quote_preview": quote[:60],
        })

        for backend in self.backends:
            if backend.name == "telegram":
                try:
                    if image_path and hasattr(backend, "send_photo"):
                        backend.send_photo(image_path, caption=message)
                    else:
                        backend.send(message)
                    break
                except Exception as e:
                    print(f"  [notify] Telegram channel post failed: {e}")

    def notify_wallpapers_ready(
        self,
        wallpaper_paths: dict,
        quote_preview: str = "",
    ):
        """
        Send wallpaper series (square + vertical) to Telegram for manual posting.
        These are save-bait content designed for high saves/shares.
        """
        if not wallpaper_paths:
            return

        lines = [
            "🖼️ BONUS: Wallpaper Series Ready!",
            "",
            f"Quote: {quote_preview}...",
            "",
            "These are optimized for saves & shares:",
            "  • Square → Feed post or Pinterest",
            "  • Vertical → Story or lock screen",
            "",
            "📌 Use them as:",
            "  1. Carousel post (first image = quote, rest = wallpapers)",
            "  2. Story series with 'swipe up to save' sticker",
            "  3. DM to loyal followers as exclusive content",
            "",
        ]
        message = "\n".join(lines)

        _log_notification({
            "event": "wallpapers_ready",
            "timestamp": datetime.now().isoformat(),
            "wallpaper_count": len(wallpaper_paths),
            "paths": {k: str(v) for k, v in wallpaper_paths.items()},
            "quote_preview": quote_preview,
            "message": message,
        })

        # Send text message
        sent_any = False
        for backend in self.backends:
            try:
                ok = backend.send(message)
                if ok:
                    sent_any = True
            except Exception:
                pass

        # Send wallpaper images
        for fmt, path in wallpaper_paths.items():
            for backend in self.backends:
                if backend.name == "telegram" and hasattr(backend, "send_photo"):
                    try:
                        backend.send_photo(path, caption=f"Wallpaper ({fmt})")
                        sent_any = True
                    except Exception as e:
                        print(f"  [notify] Wallpaper send failed: {e}")
                elif backend.name == "telegram" and hasattr(backend, "send_document"):
                    try:
                        backend.send_document(path, caption=f"Wallpaper ({fmt})")
                        sent_any = True
                    except Exception as e:
                        print(f"  [notify] Wallpaper send failed: {e}")

        if not sent_any:
            print("  [notify] ⚠️  No wallpaper notification backend succeeded")


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
