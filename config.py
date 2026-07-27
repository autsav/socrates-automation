"""
Config — loads all env vars with validation.
Copy .env.example → .env and fill in your keys.
"""

import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


@dataclass
class Config:
    ANTHROPIC_API_KEY: str = ""       # Claude API — console.anthropic.com
    FAL_API_KEY: str = ""            # Fal.ai FLUX — fal.ai/dashboard/keys
    META_ACCESS_TOKEN: str = ""      # Meta long-lived access token
    IG_ACCOUNT_ID: str = ""          # Instagram Business Account ID
    META_APP_ID: str = ""            # Meta App ID (for token refresh)
    META_APP_SECRET: str = ""        # Meta App Secret (for token refresh)
    CLOUDINARY_CLOUD_NAME: str = ""  # Cloudinary — free image hosting
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    JAMENDO_CLIENT_ID: str = ""      # Optional — Jamendo royalty-free music
    GNEWS_API_KEY: str = ""           # Optional — GNews headlines for Trend Scout

    # ── Voiceover (optional) ────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""         # OpenAI TTS — text-to-speech narration
    ELEVENLABS_API_KEY: str = ""     # ElevenLabs — human-quality TTS narration

    # ── Stock footage (optional, replaces AI art) ────────────────────────────
    PEXELS_API_KEY: str = ""         # Pexels — free stock video + photos

    # ── Notification backends (all optional) ──────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""     # @BotFather on Telegram
    TELEGRAM_CHAT_ID: str = ""       # @userinfobot on Telegram
    SLACK_WEBHOOK_URL: str = ""      # Slack Incoming Webhook URL

    def __post_init__(self):
        self.ANTHROPIC_API_KEY     = self._get("ANTHROPIC_API_KEY")
        self.FAL_API_KEY           = self._get("FAL_API_KEY")
        self.META_ACCESS_TOKEN     = self._get_opt("META_ACCESS_TOKEN")
        self.IG_ACCOUNT_ID           = self._get("IG_ACCOUNT_ID")
        self.META_APP_ID             = self._get_opt("META_APP_ID")
        self.META_APP_SECRET         = self._get_opt("META_APP_SECRET")
        self.CLOUDINARY_CLOUD_NAME   = self._get("CLOUDINARY_CLOUD_NAME")
        self.CLOUDINARY_API_KEY    = self._get("CLOUDINARY_API_KEY")
        self.CLOUDINARY_API_SECRET = self._get("CLOUDINARY_API_SECRET")
        self.JAMENDO_CLIENT_ID       = self._get_opt("JAMENDO_CLIENT_ID")
        self.GNEWS_API_KEY           = self._get_opt("GNEWS_API_KEY")
        self.OPENAI_API_KEY          = self._get_opt("OPENAI_API_KEY")
        self.ELEVENLABS_API_KEY       = self._get_opt("ELEVENLABS_API_KEY")
        self.PEXELS_API_KEY           = self._get_opt("PEXELS_API_KEY")
        self.TELEGRAM_BOT_TOKEN      = self._get_opt("TELEGRAM_BOT_TOKEN")
        self.TELEGRAM_CHAT_ID        = self._get_opt("TELEGRAM_CHAT_ID")
        self.SLACK_WEBHOOK_URL       = self._get_opt("SLACK_WEBHOOK_URL")

        self._validate_meta_token_relationship()

    def _validate_meta_token_relationship(self):
        has_token = bool(self.META_ACCESS_TOKEN)
        has_app = bool(self.META_APP_ID) and bool(self.META_APP_SECRET)
        if has_app and not has_token:
            raise RuntimeError(
                "META_APP_ID+META_APP_SECRET set without META_ACCESS_TOKEN. "
                "Need a starting long-lived token — auto-refresh requires it."
            )
        if has_token and not has_app:
            warnings.warn(
                "META_ACCESS_TOKEN set without META_APP_ID/SECRET — auto-refresh "
                "disabled; token will expire after ~60 days.",
                stacklevel=2,
            )
        if has_token and has_app and os.getenv("META_DEBUG_TOKEN_VALIDATE") == "1":
            try:
                import requests
                r = requests.get(
                    "https://graph.facebook.com/v18.0/debug_token",
                    params={
                        "input_token": self.META_ACCESS_TOKEN,
                        "access_token": f"{self.META_APP_ID}|{self.META_APP_SECRET}",
                    },
                    timeout=5,
                )
                r.raise_for_status()
            except Exception as e:
                warnings.warn(f"Meta /debug_token check failed: {e} — proceeding anyway", stacklevel=2)

    def _get(self, key: str) -> str:
        val = os.getenv(key, "")
        if not val:
            if os.getenv("GITHUB_ACTIONS"):
                raise RuntimeError(
                    f"Missing required GitHub secret: {key}.\n"
                    f"  → Go to repo Settings → Secrets and variables → Actions → New repository secret\n"
                    f"  → Add {key} with your API key.\n"
                    f"  → Required secrets: ANTHROPIC_API_KEY, FAL_API_KEY, META_ACCESS_TOKEN, "
                    f"IG_ACCOUNT_ID, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET"
                )
            raise RuntimeError(
                f"Missing required environment variable: {key}. "
                f"Copy .env.example → .env and fill in your keys."
            )
        return val

    def _get_opt(self, key: str) -> str:
        return os.getenv(key, "")
