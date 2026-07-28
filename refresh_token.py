"""
Token Refresher — Meta access tokens expire after 60 days.
Run this monthly (or add to GitHub Actions schedule).
Outputs new token — update your GitHub secret manually.

Usage: python refresh_token.py
"""

from src.utils.logger import get_logger
logger = get_logger(__name__)

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def refresh_meta_token():
    """Exchange current long-lived token for a new 60-day one."""
    current_token = os.getenv("META_ACCESS_TOKEN")
    app_id = input("Enter your Meta App ID: ").strip()
    app_secret = input("Enter your Meta App Secret: ").strip()

    url = "https://graph.facebook.com/oauth/access_token"
    params = {
        "grant_type":        "fb_exchange_token",
        "client_id":         app_id,
        "client_secret":     app_secret,
        "fb_exchange_token": current_token,
    }

    response = requests.get(url, params=params)
    data = response.json()

    if "access_token" in data:
        logger.info("\n✅ New token (valid 60 days):")
        logger.info(data["access_token"])
        logger.info("\n→ Update META_ACCESS_TOKEN in GitHub Secrets")
        logger.info("→ Update META_ACCESS_TOKEN in your .env file")
    else:
        logger.info(f"\n❌ Error: {data}")


if __name__ == "__main__":
    refresh_meta_token()
