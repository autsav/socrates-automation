"""Story Writer agent — trend-first / debate-bait / weird-history reels.

One agent, three modes. Beats map 1:1 onto the existing Hook/Bridge/Quote/CTA
scene machinery:
  beat_hook    -> Hook scene    (<=15 words, a STATEMENT — questions cost
                                 0.5s-retention; recipe #5)
  beat_reframe -> Bridge scene  (<=45 words — the real issue / escalation)
  quote        -> Quote scene   (the twist: Socrates/Stoics said it first)
  beat_cta     -> CTA scene     (weird mode: always a SEND-framed CTA)
"""
import json

from studio.types import _obj
from src.optimizer import prompt_store

_PREFIX = (
    "You write scroll-stopping 30-second reels for a viral Stoic-philosophy "
    "Instagram account. Your specialty: stories people feel COMPELLED to send "
    "to a friend. Contrarian about culture and behavior — never about named "
    "living individuals. No politics, religion, tragedy, or medical/financial "
    "advice."
)

_ROLE_DEFAULT = (
    "Mode: {mode}\n"
    "Material:\n{material}\n"
    "Available quotes (choose the one that lands as the TWIST — the payoff the "
    "story was secretly building to; set quote_row to its row_number):\n{pool}\n\n"
    "Write the reel as four beats:\n"
    "- beat_hook: <=15 words. A STATEMENT, not a question (statements hold "
    "3-second retention; questions don't). 'No way this is real' energy.\n"
    "- beat_reframe: <=45 words. Escalate the story / name the real issue. "
    "For weird mode: use ONLY the facts given in the material — never invent "
    "or exaggerate historical claims; if the material is flagged hypothetical, "
    "keep it clearly framed as imagination ('Imagine...', 'Suppose...').\n"
    "- quote_row: the chosen quote's row_number (integer).\n"
    "- beat_cta: one line. For weird mode this MUST be a send-CTA telling the "
    "viewer to send the reel to a specific kind of friend. For debate mode it "
    "MUST be a binary agree/disagree ask.\n"
    "- topic_query: 2-4 words for stock-footage search matching the story's "
    "VISUAL world (e.g. 'ancient greek ruins', 'crowded city night').\n"
    "- caption_first_line: <=8 words, curiosity gap, no hashtags.\n"
    "- trend_tag: one hashtag (no #) matching the topic, or empty string.\n"
    "Total spoken words across beats <=90 (a ~30s reel). Output JSON only."
)

STORY_SCHEMA = _obj({
    "beat_hook": {"type": "string"},
    "beat_reframe": {"type": "string"},
    "quote_row": {"type": "integer"},
    "beat_cta": {"type": "string"},
    "topic_query": {"type": "string"},
    "caption_first_line": {"type": "string"},
    "trend_tag": {"type": "string"},
}, ["beat_hook", "beat_reframe", "quote_row", "beat_cta", "topic_query",
    "caption_first_line"])


def validate_story(d: dict) -> tuple[bool, str]:
    """Hard limits the prompt promises — enforced deterministically."""
    try:
        hook = (d.get("beat_hook") or "").strip()
        reframe = (d.get("beat_reframe") or "").strip()
        cta = (d.get("beat_cta") or "").strip()
        if not hook or not reframe or not cta:
            return False, "empty beat"
        if len(hook.split()) > 15:
            return False, f"hook too long ({len(hook.split())} words)"
        if hook.rstrip().endswith("?"):
            return False, "hook must be a statement, not a question"
        if len(reframe.split()) > 45:
            return False, f"reframe too long ({len(reframe.split())} words)"
        total = len(hook.split()) + len(reframe.split()) + len(cta.split())
        if total > 90:
            return False, f"total spoken words {total} > 90"
        if not isinstance(d.get("quote_row"), int):
            return False, "quote_row must be an integer"
        return True, "ok"
    except (TypeError, AttributeError) as e:
        return False, f"malformed: {e}"


def write_story(client, mode: str, material: dict, pool: list) -> dict | None:
    """Generate story beats. Returns validated dict or None (never raises)."""
    try:
        role_tmpl = prompt_store.get("prompt.story_writer.role", _ROLE_DEFAULT)
        role = role_tmpl.format(
            mode=mode,
            material=json.dumps(material, ensure_ascii=False, indent=2),
            pool=json.dumps([{"row_number": p["row_number"], "quote": p["quote"]}
                             for p in pool[:20]], ensure_ascii=False, indent=2),
        )
        d = client.call("story_writer", _PREFIX, role,
                        "Write the four beats now.", STORY_SCHEMA)
        ok, reason = validate_story(d or {})
        if not ok:
            print(f"  [story_writer] rejected ({reason})")
            return None
        return d
    except Exception as e:  # noqa: BLE001 - never crash a reel
        print(f"  [story_writer] unavailable ({e})")
        return None
