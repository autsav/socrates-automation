"""Content Strategist agent — turns the PerformanceBrief into a per-post CreativeBrief."""
import json

from studio.types import CreativeBrief, CREATIVE_BRIEF_SCHEMA

_PREFIX = (
    "You are the creative team for a stoic-philosophy Instagram account whose "
    "goal is scroll-stopping growth. Shared performance context for today:\n{perf}"
)
_ROLE = (
    "You are the Content Strategist. Slot today: {slot} "
    "(0=morning, 1=afternoon, 2=evening). "
    "Recently posted (avoid repetition): {recent}. "
    "Available quotes (pick the single best fit for the angle you choose, by "
    "row_number; if none fits, set quote to {{\"need_new\": true, "
    "\"theme\": \"...\"}}):\n{pool}\n"
    "Choose audience, theme, format, emotional angle, and the quote. Pull "
    "must_include / must_avoid from what is winning/dying. Output a CreativeBrief "
    "as JSON only."
)


def shared_prefix(perf):
    return _PREFIX.format(perf=json.dumps(perf.to_dict(), indent=2))


def build_prompt(perf, slot, recent_posts, pool):
    role = _ROLE.format(
        slot=slot,
        recent=json.dumps([p.get("quote", "")[:50] for p in recent_posts]),
        pool=json.dumps([{"row_number": p["row_number"], "quote": p["quote"],
                          "audience": p.get("audience", "")} for p in pool], indent=2),
    )
    return shared_prefix(perf), role


def parse_response(d):
    return CreativeBrief.from_dict(d)


def make_brief(client, perf, slot, recent_posts, pool):
    prefix, role = build_prompt(perf, slot, recent_posts, pool)
    data = client.call("strategist", prefix, role,
                       "Produce the CreativeBrief now.", CREATIVE_BRIEF_SCHEMA)
    return parse_response(data)
