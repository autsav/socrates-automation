"""Controversy Engine — transforms safe philosophical quotes into bold, provocative
modern interpretations that spark debate and drive engagement.

Instead of "The unexamined life is not worth living" (safe, heard a thousand times),
the engine produces: "Socrates would call your 9-to-5 a slow death — and you'd thank him for it."

Three modes:
- ROAST: Socrates roasts a modern habit (comedy + philosophy)
- VERDICT: What would Socrates say about [current trend]? (timely + provocative)
- DEBATE: A bold claim that splits the audience (agree/disagree engagement bait)

Uses Claude to generate the interpretations, with safety guardrails.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

log = logging.getLogger(__name__)

# Modes for the controversy engine
Mode = Literal["roast", "verdict", "debate"]

_SYSTEM_PROMPT = (
    "You are a provocative philosophy content writer for an Instagram account. "
    "You take Socratic/stoic quotes and make them RELEVANT and CONFRONTATIONAL "
    "for a modern audience scrolling Instagram at 2am.\n\n"
    "RULES:\n"
    "- NEVER be hateful, discriminatory, or target protected groups\n"
    "- NEVER reference real tragedies, violence, or sensitive current events\n"
    "- DO be uncomfortable. Make people feel called out. Make them screenshot it.\n"
    "- DO use modern language (no 'thou shalt' or archaic phrasing)\n"
    "- DO reference modern life: phones, scrolling, 9-to-5, dating apps, "
    "social media, hustle culture, burnout, procrastination, comfort zones\n"
    "- Keep hooks under 12 words. Punch hard. No padding.\n"
    "- The quote stays as-is. The INTERPRETATION is what's provocative.\n"
    "- Output JSON only, no markdown.\n"
)

_ROAST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hook": {"type": "string", "description": "Under 12 words. Confrontational scroll-stopper."},
        "roast": {"type": "string", "description": "1-3 sentences. Socrates roasts a modern habit using the quote's wisdom. Provocative but not cruel."},
        "caption": {"type": "string", "description": "Full caption: roast + modern application + the quote + CTA. Under 200 words."},
        "cta": {"type": "string", "description": "Engagement trigger. Under 15 words."},
        "hashtags": {"type": "array", "items": {"type": "string"}, "description": "3-5 non-generic hashtags."},
        "target_habit": {"type": "string", "description": "The modern habit being roasted (e.g., 'doomscrolling', 'hustle culture')."},
    },
    "required": ["hook", "roast", "caption", "cta", "hashtags", "target_habit"],
}

_VERDICT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hook": {"type": "string", "description": "Under 12 words. References the trend as bait."},
        "verdict": {"type": "string", "description": "1-3 sentences. What Socrates would say about this trend. Provocative, not safe."},
        "caption": {"type": "string", "description": "Full caption: trend context + Socratic verdict + the quote + CTA. Under 200 words."},
        "cta": {"type": "string", "description": "Agree or disagree prompt. Under 15 words."},
        "hashtags": {"type": "array", "items": {"type": "string"}, "description": "3-5 non-generic hashtags."},
        "trend_topic": {"type": "string", "description": "The trend being judged."},
    },
    "required": ["hook", "verdict", "caption", "cta", "hashtags", "trend_topic"],
}

_DEBATE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hook": {"type": "string", "description": "Under 12 words. A bold claim that splits the audience."},
        "take": {"type": "string", "description": "1-2 sentences. The controversial take, defended by the quote."},
        "caption": {"type": "string", "description": "Full caption: bold claim + reasoning + the quote + agree/disagree CTA. Under 200 words."},
        "cta": {"type": "string", "description": "Agree or disagree prompt. Under 15 words."},
        "hashtags": {"type": "array", "items": {"type": "string"}, "description": "3-5 non-generic hashtags."},
        "debate_topic": {"type": "string", "description": "What the debate is about."},
    },
    "required": ["hook", "take", "caption", "cta", "hashtags", "debate_topic"],
}

_SCHEMAS = {"roast": _ROAST_SCHEMA, "verdict": _VERDICT_SCHEMA, "debate": _DEBATE_SCHEMA}

_MODE_PROMPTS = {
    "roast": (
        "MODE: ROAST\n"
        "Take this quote and roast a specific modern habit with it. "
        "Make it funny but cutting. The reader should feel PERSONALLY attacked.\n"
        "Quote: {quote}\n"
        "Target habit (if specified): {target}\n"
        "Generate the roast now."
    ),
    "verdict": (
        "MODE: VERDICT\n"
        "A trend is happening right now: {trend}\n"
        "What would Socrates say about it? Use this quote as his verdict:\n"
        "Quote: {quote}\n"
        "Make it provocative — not a safe 'wisdom applies to everything' take. "
        "Take a SIDE. Make people disagree.\n"
        "Generate the verdict now."
    ),
    "debate": (
        "MODE: DEBATE\n"
        "Use this quote to make a bold claim that will split your audience "
        "into two camps. Something where 50% will agree and 50% will rage.\n"
        "Quote: {quote}\n"
        "Topic (if specified): {target}\n"
        "Generate the debate take now."
    ),
}


def generate_controversy(
    client,
    quote: str,
    mode: Mode = "roast",
    target: str = "",
    trend: str = "",
) -> dict | None:
    """Generate a provocative interpretation of a quote.

    Args:
        client: StudioClient instance
        quote: The philosophical quote text
        mode: 'roast', 'verdict', or 'debate'
        target: Modern habit to roast (for roast mode) or debate topic (for debate mode)
        trend: Current trend topic (for verdict mode)

    Returns:
        dict with hook, caption, cta, hashtags, and mode-specific fields,
        or None on failure.
    """
    schema = _SCHEMAS[mode]
    prompt_template = _MODE_PROMPTS[mode]
    user = prompt_template.format(quote=quote, target=target or "pick one", trend=trend or "pick a relevant current trend")

    try:
        result = client.call(
            "copywriter",  # use copywriter role for creative writing
            _SYSTEM_PROMPT,
            f"You are generating {mode} content.",
            user,
            schema,
        )
        return result
    except Exception as e:
        log.warning(f"[controversy] generation failed ({e})")
        return None


def pick_mode(slot: int = 0, trend_available: bool = False) -> Mode:
    """Pick a mode for this post. Rotates to keep variety.

    - verdict mode is only used when a trend is available
    - roast and debate alternate for the other slots
    """
    if trend_available and slot % 3 == 0:
        return "verdict"
    if slot % 2 == 0:
        return "roast"
    return "debate"


# Modern habits that Socrates would roast (for when no target is specified)
DEFAULT_TARGETS = [
    "doomscrolling for hours",
    "the hustle culture grind",
    "calling it 'self-care' to avoid doing work",
    "ghosting people instead of being honest",
    "reading self-help books and changing nothing",
    "the 9-to-5 comfort trap",
    "dating apps and infinite choice paralysis",
    "productivity apps as procrastination",
    "calling burnout a badge of honor",
    "reposting motivational quotes and doing nothing",
    "the illusion of staying 'informed' via social media",
    "comfort zones disguised as 'stability'",
    "consuming content instead of creating anything",
    "the fear of being a beginner",
    "mistaking busy for productive",
]