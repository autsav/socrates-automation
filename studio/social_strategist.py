"""social_strategist — full-stack Instagram content creator.
Single Opus call produces hook, bridge (optional), quote, CTA, caption,
hashtags, mood, attribution, audience, row_number for the --strategy
flag path. See docs/superpowers/specs/2026-07-28-social-strategist-design.md.
"""
import re
from dataclasses import dataclass

from studio.prompts.strategist_system import SYSTEM_PROMPT, SHARED_PREFIX
from studio.types import QuoteData, QUOTE_DATA_SCHEMA

_PREFIX = "STRAT"  # log prefix used by client.call
_ROLE = "social_strategist"
_HOOK_WORD_MAX = 12
_HASHTAG_MIN = 3
_HASHTAG_MAX = 5

_ENGAGEMENT_BAIT = (
    "like if you agree", "comment below", "share if you",
    "smash that like", "double tap", "follow for more",
)


class StrategyValidationError(Exception):
    """Raised when social_strategist output violates platform rules."""


@dataclass
class StrategyInput:
    trend: dict          # {headline, keywords, angle}
    quote_row: dict      # {text, attribution, row_number, mood}
    audience: str = ""   # from settings.STRATEGY_AUDIENCE


def _validate(creative: dict) -> None:
    hook_words = len(creative["hook"].split())
    if hook_words > _HOOK_WORD_MAX:
        raise StrategyValidationError(
            f"hook too long: {hook_words} words (max {_HOOK_WORD_MAX})")
    n_tags = len(creative["hashtags"])
    if not (_HASHTAG_MIN <= n_tags <= _HASHTAG_MAX):
        raise StrategyValidationError(
            f"hashtag count {n_tags} out of range [{_HASHTAG_MIN}, {_HASHTAG_MAX}]")
    bridge = creative.get("bridge")
    if bridge is not None and len(bridge) > 280:
        raise StrategyValidationError("bridge too long (>280 chars)")


def _linter(caption: str) -> None:
    lc = caption.lower()
    for phrase in _ENGAGEMENT_BAIT:
        if phrase in lc:
            raise StrategyValidationError(f"engagement-bait phrase rejected: {phrase!r}")


def _build_user_msg(trend: dict, quote_row: dict, audience: str) -> str:
    keywords = ", ".join(trend.get("keywords", []))
    return (
        "TREND:\n"
        f"Headline: {trend.get('headline', '')}\n"
        f"Keywords: {keywords}\n"
        f"Angle: {trend.get('angle', '')}\n\n"
        "QUOTE:\n"
        f"Text: {quote_row.get('text', '')}\n"
        f"Attribution: {quote_row.get('attribution', '')}\n"
        f"Source mood: {quote_row.get('mood', '')}\n\n"
        f"AUDIENCE: {audience}\n\n"
        "Output QuoteData JSON. Platform: Instagram (2026)."
    )