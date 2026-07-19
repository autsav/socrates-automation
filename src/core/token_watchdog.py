"""Meta-token watchdog — the net under the A4 security scrub.

Because CI scrubs token_state before every commit (public repo, correct), every
run uses the STATIC GitHub-secret token, which dies silently at 60 days — that
outage killed auto-posting on 2026-07-17. This module:

  1. check_token_age(token)  — tracks the secret's first-seen date by
     fingerprint (sha256 prefix; the token itself is never stored) in a small
     committed JSON, and warns when the token is within WARN_DAYS of the 60-day
     Meta lifetime.
  2. probe_token(token, ig_id) — live GET /me validity check; returns
     (alive, message) so callers can page Telegram the moment Meta rejects it.

Run from CI:  python -m src.core.token_watchdog   (exit 0 always; alerts via
Telegram when configured, prints otherwise — never blocks posting).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

STATE_PATH = Path(__file__).parent.parent.parent / "data" / "token_meta.json"
TOKEN_LIFETIME_DAYS = 60
WARN_DAYS = 10          # start warning when <= this many days remain
GRAPH = "https://graph.instagram.com/v22.0"


def _fingerprint(token: str) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()[:12]


def check_token_age(token: str) -> dict:
    """Track first-seen date for this token fingerprint; warn near end of life."""
    now = datetime.now(timezone.utc)
    fp = _fingerprint(token)
    try:
        state = json.loads(STATE_PATH.read_text())
    except (FileNotFoundError, ValueError):
        state = {}
    if state.get("fingerprint") != fp:
        state = {"fingerprint": fp, "first_seen": now.isoformat()}
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2))
    first_seen = datetime.fromisoformat(state["first_seen"])
    if first_seen.tzinfo is None:
        first_seen = first_seen.replace(tzinfo=timezone.utc)
    age_days = (now - first_seen).days
    remaining = TOKEN_LIFETIME_DAYS - age_days
    warn = remaining <= WARN_DAYS
    message = (f"⚠️ Meta token is ~{age_days} days old — about {max(remaining,0)} days "
               f"before Instagram posting DIES. Generate a fresh token "
               f"(developers.facebook.com → Instagram → API setup) and update the "
               f"META_ACCESS_TOKEN GitHub secret.") if warn else \
              (f"Meta token age ~{age_days}d ({max(remaining,0)}d headroom)")
    return {"age_days": age_days, "remaining_days": remaining, "warn": warn,
            "message": message, "fingerprint": fp}


def probe_token(token: str, ig_account_id: str) -> tuple[bool, str]:
    """Live validity probe (side-effect free). Returns (alive, message)."""
    try:
        r = requests.get(f"{GRAPH}/me", params={"fields": "id",
                                                "access_token": token}, timeout=15)
        if r.status_code == 200:
            return True, "token alive"
        err = (r.json() or {}).get("error", {})
        return False, (f"🛑 Meta token REJECTED (code {err.get('code')}): "
                       f"{err.get('message', 'unknown')} — Instagram posting is DOWN "
                       f"until META_ACCESS_TOKEN is replaced.")
    except Exception as e:  # network etc. — not proof of death
        return True, f"probe inconclusive ({e})"


def main() -> int:
    from config import Config
    cfg = Config()
    token = cfg.META_ACCESS_TOKEN
    if not token:
        print("[watchdog] no META_ACCESS_TOKEN configured")
        return 0
    age = check_token_age(token)
    alive, probe_msg = probe_token(token, cfg.IG_ACCOUNT_ID)
    print(f"[watchdog] {age['message']}")
    print(f"[watchdog] probe: {probe_msg}")
    alert = None
    if not alive:
        alert = probe_msg
    elif age["warn"]:
        alert = age["message"]
    if alert:
        try:
            from src.core.notifier import Notifier
            Notifier(cfg).send(alert)
            print("[watchdog] alert sent to Telegram")
        except Exception as e:
            print(f"[watchdog] alert send failed ({e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
