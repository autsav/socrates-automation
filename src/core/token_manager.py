"""
Token Manager — automatically refresh Meta access tokens before expiry.
Uses Meta's fb_exchange_token endpoint to extend token life.
"""

import requests
from datetime import datetime, timedelta, timezone

META_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"
REFRESH_THRESHOLD_DAYS = 7


def _is_token_expiring_soon(expires_at: datetime | None) -> bool:
    """Return True if token expires within REFRESH_THRESHOLD_DAYS."""
    if expires_at is None:
        return True
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        # Naive datetime from DB — assume UTC for comparison
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at - now < timedelta(days=REFRESH_THRESHOLD_DAYS)


def refresh_if_needed(
    current_token: str,
    app_id: str,
    app_secret: str,
    expires_at: datetime | None = None,
) -> str:
    """
    Check token expiry. If < 7 days remaining, refresh using Meta endpoint.
    Returns valid token (new or current).
    """
    if not app_id or not app_secret:
        print("  [token] No app_id/secret configured — skipping refresh")
        return current_token

    if not _is_token_expiring_soon(expires_at):
        print("  [token] Token is fresh, no refresh needed")
        return current_token

    print("  [token] Token expiring soon — refreshing...")
    try:
        response = requests.post(
            META_TOKEN_URL,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": current_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        new_token = data.get("access_token")
        if not new_token:
            print(f"  [token] Refresh response missing access_token: {data}")
            return current_token
        print("  [token] Token refreshed successfully")
        return new_token
    except requests.RequestException as e:
        print(f"  [token] Refresh failed: {e}")
        return current_token


def get_valid_token_with_fallback(cfg) -> str:
    """
    Check data_store token_state for a fresh token, else use env fallback.
    Refresh if needed and store result back to data_store.
    """
    try:
        from src.core.data_store import get_token, save_token
        state = get_token("meta")
        if state:
            expires_at = None
            if state.get("expires_at"):
                try:
                    expires_at = datetime.strptime(state["expires_at"], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            token = refresh_if_needed(state["token"], cfg.META_APP_ID, cfg.META_APP_SECRET, expires_at)
            if token != state["token"]:
                save_token("meta", token, datetime.now(timezone.utc) + timedelta(days=60))
            elif expires_at is None:
                # Persist an estimate so a NULL-expiry token stops being re-checked every run.
                save_token("meta", token, datetime.now(timezone.utc) + timedelta(days=60))
            return token
    except Exception as e:
        print(f"  [token] data_store check failed: {e}")

    return cfg.META_ACCESS_TOKEN
