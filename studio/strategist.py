"""Content Strategist agent — turns the PerformanceBrief into a per-post CreativeBrief."""
import json

from studio import playbooks
from studio.types import CreativeBrief, CREATIVE_BRIEF_SCHEMA
from src.optimizer import prompt_store

_PREFIX_DEFAULT = (
    "You are the creative team for a stoic-philosophy Instagram account whose "
    "goal is scroll-stopping growth. The voice is the Architecture of Digital "
    "Stoicism: dark, moody, historically grounded, with selective warmth where "
    "compassion lands harder than confrontation. Shared performance context for "
    "today:\n{perf}"
)
_ROLE_DEFAULT = (
    "You are the Content Director & Chief Philosopher. Slot today: {slot} "
    "(0=morning, 1=afternoon, 2=evening). Recently posted (avoid repetition): "
    "{recent}.\n"
    "Available quotes (pick the single best fit; set quote to "
    "{{\"row_number\": N, \"text\": \"<exact quote>\", \"author\": \"<author>\", "
    "\"source\": \"<source>\"}} if you pick one, OR {{\"need_new\": true, "
    "\"theme\": \"<theme>\"}} if none fit):\n{pool}\n"
    "Choose audience, topic_theme, format, angle, and the quote. Bias topics "
    "toward ONE of these three content pillars:\n"
    "  PILLAR 1 — CBT-Stoic bridge: cognitive reframes the viewer can apply TODAY "
    "(thought labeling, dichotomous control, premeditatio malorum).\n"
    "  PILLAR 2 — Relational / Compassionate Stoicism (hopecore): friendship, "
    "mortality-as-gift, the warmth beneath the armor — golden-hour mood, "
    "hopeful-leaning imagery, DM-share CTA tone.\n"
    "  PILLAR 3 — Narrative / Historical context: real biography of a Stoic or "
    "Greek figure, the scene plays out in BridgeScene against stock footage. "
    "Send-CTA tone.\n"
    "Pull must_include / must_avoid from what is winning/dying. Output a "
    "CreativeBrief as JSON only.\n"
    + playbooks.STRATEGY_CRAFT
)

# Backward-compat aliases for any importer expecting the old names.
_PREFIX = _PREFIX_DEFAULT
_ROLE = _ROLE_DEFAULT


def shared_prefix(perf, db_path=prompt_store.registry.DB_PATH):
    prefix = prompt_store.get("prompt.strategist.prefix", _PREFIX_DEFAULT, db_path)
    return prefix.format(perf=json.dumps(perf.to_dict(), indent=2))


def build_role(slot, recent, pool, db_path=prompt_store.registry.DB_PATH):
    role = prompt_store.get("prompt.strategist.role", _ROLE_DEFAULT, db_path)
    return role.format(slot=slot, recent=recent, pool=pool)


def build_prompt(perf, slot, recent_posts, pool, db_path=prompt_store.registry.DB_PATH):
    role = build_role(
        slot=slot,
        recent=json.dumps([p.get("quote", "")[:50] for p in recent_posts]),
        pool=json.dumps([{"row_number": p["row_number"], "quote": p["quote"],
                          "audience": p.get("audience", "")} for p in pool], indent=2),
        db_path=db_path,
    )
    return shared_prefix(perf, db_path), role


def parse_response(d):
    return CreativeBrief.from_dict(d)


def make_brief(client, perf, slot, recent_posts, pool, extra_context=""):
    prefix, role = build_prompt(perf, slot, recent_posts, pool)
    user = "Produce the CreativeBrief now."
    if extra_context:
        user += f"\n{extra_context}"
    data = client.call("strategist", prefix, role,
                       user, CREATIVE_BRIEF_SCHEMA)
    return parse_response(data)
