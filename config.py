"""
Config — loads all env vars with validation.
Copy .env.example → .env and fill in your keys.
"""

import os
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
    PIXABAY_API_KEY: str = ""        # Optional — royalty-free music downloads

    def __post_init__(self):
        self.ANTHROPIC_API_KEY     = self._get("ANTHROPIC_API_KEY")
        self.FAL_API_KEY           = self._get("FAL_API_KEY")
        self.META_ACCESS_TOKEN     = self._get("META_ACCESS_TOKEN")
        self.IG_ACCOUNT_ID           = self._get("IG_ACCOUNT_ID")
        self.META_APP_ID             = self._get_opt("META_APP_ID")
        self.META_APP_SECRET         = self._get_opt("META_APP_SECRET")
        self.CLOUDINARY_CLOUD_NAME   = self._get("CLOUDINARY_CLOUD_NAME")
        self.CLOUDINARY_API_KEY    = self._get("CLOUDINARY_API_KEY")
        self.CLOUDINARY_API_SECRET = self._get("CLOUDINARY_API_SECRET")
        self.PIXABAY_API_KEY         = self._get_opt("PIXABAY_API_KEY")

    def _get(self, key: str) -> str:
        val = os.getenv(key, "")
        if not val:
            raise RuntimeError(
                f"Missing required environment variable: {key}. "
                f"Copy .env.example → .env and fill in your keys."
            )
        return val

    def _get_opt(self, key: str) -> str:
        return os.getenv(key, "")
