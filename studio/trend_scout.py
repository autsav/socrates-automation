"""Trend Scout agent — turns a live trending topic into a scroll-stopping hook
that bridges to a timeless Socratic quote. The trend is bait; the quote is the
payoff. Hard safety rules; returns used=false when nothing bridges safely."""
import json

from studio.types import TrendHook, TREND_HOOK_SCHEMA
from src.optimizer import prompt_store

_PREFIX = (
    "You are a social-media trend strategist for a stoic-philosophy Instagram "
    "account. You turn a trending topic into a scroll-stopping hook that bridges "
    "to a timeless Socratic quote — the trend is bait, the philosophy is the payoff."
)

_ROLE_DEFAULT = (
    "Chosen quote / theme:\n{quote_ctx}\n"
    "Candidate trending topics (Google Trends + news headlines):\n{candidates}\n"
    "Pick the ONE topic that bridges most naturally to this quote's theme AND is "
    "brand-safe.\n"
    "SAFETY (hard rules): never claim a real person said or did a specific thing; "
    "REJECT tragedy, death, disaster, war, hard politics, violence, crime, medical "
    "or financial advice, and defamatory or protected-class angles. Prefer "
    "evergreen-adjacent topics (money, work, burnout, success, AI, habits, "
    "discipline, relationships, ambition). If NO candidate bridges cleanly and "
    "safely, set used=false.\n"
    "When used=true, also write: hook (5-12 words, formula-compliant, negative "
    "framing where apt, referencing the trend as bait) and bridge (the '…but 2,400 "
    "years ago Socrates already knew…' pivot connecting trend -> quote, using "
    "But/Therefore momentum). Set topic + source to the chosen candidate. "
    "Output a TrendHook as JSON only."
)
_ROLE = _ROLE_DEFAULT  # backward-compat alias (assets.py reads _ROLE)


def pick_hook(client, candidates, quote_ctx) -> TrendHook:
    tmpl = prompt_store.get("prompt.trend_scout.role", _ROLE_DEFAULT)
    role = tmpl.format(
        quote_ctx=json.dumps(quote_ctx, indent=2),
        candidates=json.dumps([c["topic"] for c in candidates], indent=2),
    )
    d = client.call("trend_scout", _PREFIX, role,
                    "Pick and write the trend hook now.", TREND_HOOK_SCHEMA)
    return TrendHook.from_dict(d)
