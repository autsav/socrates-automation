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

from studio import playbooks
from src.optimizer import prompt_store

log = logging.getLogger(__name__)

# Modes for the controversy engine
Mode = Literal["roast", "verdict", "debate"]

_SYSTEM_PROMPT = (
    "You are a provocative philosophy writer for a confrontational Instagram "
    "account that turns Socratic/Stoic quotes into reels people screenshot and "
    "send. Audience: 2am doomscrollers who feel called out.\n\n"
    "RETENTION PSYCHOLOGY (apply to every beat):\n"
    "- Open a curiosity GAP in the hook and never close it until the quote lands. "
    "The viewer must NEED the next sentence.\n"
    "- Pattern-interrupt the assumed: assert something that sounds WRONG, then "
    "prove it. Agreement is scroll-past; contradiction is watch-through.\n"
    "- Negation beats affirmation: 'You are NOT who you think you are' outpulls "
    "'Be your best self'. Lead with what's false, not what's true.\n"
    "- Specificity = retention: 'the app you reopened 3 times before lunch' beats "
    "'phone addiction'. A concrete number or 2am image every ~8 words.\n"
    "- Identity threat sells shares: the viewer forwards it to say 'this is so "
    "you' about a friend. End on a line that hands them those words.\n"
    "- Falsify-friendly: make a claim concrete enough one side can rage. Vague = "
    "no comments.\n\n"
    "RULES:\n"
    "- NEVER hateful, discriminatory, or protected-group targeting.\n"
    "- NEVER real tragedies, violence, named living individuals, or sensitive "
    "current events. (A trend's CULTURE is fair game; the trend's VICTIMS are not.)\n"
    "- DO make them feel personally attacked. Screenshot-bait, not hate-bait.\n"
    "- Modern language only. No 'thou shalt'. Reference their life: 9-to-5, "
    "scrolling, dating apps, burnout, hustle culture, ghosting, self-care-as-avoidance.\n"
    "- Hook <=12 words, a STATEMENT (questions cost ~0.5s retention). Punch hard.\n"
    "- The quote stays verbatim. The INTERPRETATION is the provocation.\n"
    "- Output JSON only, no markdown.\n"
    + playbooks.STORY_CRAFT  # shared craft canon, same as story_writer
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

_MODE_PLAYBOOKS = {
    "roast": (
        "ROAST STRUCTURE (retention-optimized):\n"
        "1. ACCUSE (hook): name the habit as a verdict on the viewer, not a joke. "
        "'Your 9-to-5 is a slow death you call a career.'\n"
        "2. INDICT (2-3 sentences): the specific nightly cost — what they lose "
        "tonight, this week, this decade. Concrete, not 'productivity'.\n"
        "3. CONVICT via the quote: Socrates already tried and found them guilty. "
        "The quote is the verdict, not a bumper sticker.\n"
        "4. SENTENCE (CTA): one line that makes them argue the punishment is too harsh.\n"
        "Polarization lever: blame, not advice. Never 'try this'. Always 'you already lost'."
    ),
    "verdict": (
        "VERDICT STRUCTURE (newsjack, retention-optimized):\n"
        "1. TREND-AS-EVIDENCE (hook): state what everyone is doing with the trend "
        "as if it's already a verdict. Use the trend's own specific noun/number.\n"
        "2. CROSS-EXAMINE: the one question about the trend nobody's asking. "
        "Socrates would ask it; you state it.\n"
        "3. THE VERDICT (quote): drop the quote as the judge's ruling. Take a SIDE "
        "- 'wisdom applies to everything' is banned, it reads as spam.\n"
        "4. SENTENCE (CTA): agree/disagree with the ruling — force a binary.\n"
        "Polarization lever: take the UNPOPULAR side of the trend. 50/50 split is "
        "the goal; safe consensus gets no comments."
    ),
    "debate": (
        "DEBATE STRUCTURE (audience-split, retention-optimized):\n"
        "1. THE CLAIM (hook): a binary, falsifiable statement. 'Comfort is just "
        "stuck with better branding.' Half will already rage.\n"
        "2. THE STAKE: what they lose if they're on the wrong side — tonight, not "
        "in theory.\n"
        "3. THE EXHIBIT (quote): the ancient precedent that already settled this "
        "centuries ago. The quote is the closing argument.\n"
        "4. THE SPLIT (CTA): force agree OR disagree in one word. No 'thoughts?'.\n"
        "Polarization lever: make the claim about an IDENTITY (the grinder, the "
        "self-care girlie, the optimist), not a topic. People defend identities."
    ),
}

# Per-mode user-prompt template. {body} carries the quote/target/trend block,
# {mode} the mode name. The playbook above is the load-bearing retention lever.
_MODE_PROMPTS = {
    m: (
        f"MODE: {m.upper()}\n"
        f"{{playbook}}\n\n"
        "{body}\n"
        "Generate the {mode} now."
    )
    for m in ("roast", "verdict", "debate")
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
    body = {
        "roast":  f"Quote: {quote}\nTarget habit: {target or 'pick one'}",
        "verdict":f"A trend is live right now: {trend or 'pick a relevant current trend'}\n"
                  f"Quote (his verdict): {quote}",
        "debate": f"Quote: {quote}\nTopic: {target or 'pick one that splits 50/50'}",
    }[mode]
    user = _MODE_PROMPTS[mode].format(
        playbook=_MODE_PLAYBOOKS[mode], body=body, mode=mode,
    )

    try:
        # Route the system prompt through prompt_store so the nightly optimizer
        # (prompt_critic + loop.run_once) can A/B it against real sends-per-reach,
        # the same machinery that already improves story_writer. The hardcoded
        # default seeds v1 on first access.
        sys_prompt = prompt_store.get("prompt.controversy.system", _SYSTEM_PROMPT)
        result = client.call(
            "copywriter",  # use copywriter role for creative writing
            sys_prompt,
            f"You are generating {mode} content.",
            user,
            schema,
        )
        # Tighten the controversy-path hook to 11 words (the studio story path
        # keeps 15 — its hooks land softer over a longer scene). A 15-word hook
        # at a frame-0 hard-pop is too much text to read in ~1.6s.
        hook = (result or {}).get("hook", "") if isinstance(result, dict) else ""
        if hook and len(hook.split()) > 11:
            result["hook"] = " ".join(hook.split()[:11])
        return result
    except Exception as e:
        log.warning(f"[controversy] generation failed ({e})")
        return None


def pick_mode(slot: int = 0, trend_available: bool = False) -> Mode:
    """Pick a mode for this post. Rotates to keep variety.

    - No trend: roast/debate alternate on the evergreen target pool.
    - Trend present: every trend slot uses the trend; the ANGLE rotates
      (verdict / roast-of-trend / debate-of-trend) rather than dropping the
      trend 2 of 3 slots. Roasting the *habit a trend reveals* is a fresh angle
      the old slot-only logic never produced.
    """
    if not trend_available:
        return "roast" if slot % 2 == 0 else "debate"
    return ["verdict", "roast", "debate"][slot % 3]


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