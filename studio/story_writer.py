"""Story Writer agent — trend-first / debate-bait / weird-history reels.

One agent, three modes. Beats map 1:1 onto the existing Hook/Bridge/Quote/CTA
scene machinery:
  beat_hook    -> Hook scene    (<=15 words, a STATEMENT — questions cost
                                 0.5s-retention; recipe #5)
  beat_reframe -> Bridge scene  (the story itself, told in short chapters —
                                 BridgeScene chunk-displays it against the VO)
  quote        -> Quote scene   (the twist: Socrates/Stoics said it first)
  beat_cta     -> CTA scene     (weird mode: always a SEND-framed CTA)

Length contract: total spoken words 145-185 → a ~60-75s reel (the scenes are
VO-sized, so narration length IS reel length).
"""
import json

from studio.types import _obj
from studio import playbooks
from src.optimizer import prompt_store

_PERSONAS = (
    "Voice: a historian-screenwriter — cinematic scenes, period texture, "
    "the past made visible.",
    "Voice: a growth-storyteller — modern parallels, the viewer's own life "
    "mirrored in the ancient story.",
)

_PREFIX = (
    "You write scroll-stopping 60-75 second story reels for a viral Stoic-"
    "philosophy "
    "Instagram account. Your specialty: stories people feel COMPELLED to send "
    "to a friend. Contrarian about culture and behavior — never about named "
    "living individuals. No politics, religion, tragedy, or medical/financial "
    "advice."
    " Write in first person — a mentor speaking directly to one reader as "
    "\"I\" and \"you\"."
)

_ROLE_DEFAULT = (
    "Mode: {mode}\n"
    "Material:\n{material}\n"
    "Available quotes (choose the one that lands as the TWIST — the payoff the "
    "story was secretly building to; set quote_row to its row_number):\n{pool}\n\n"
    "Write the reel as four beats:\n"
    "- beat_hook: <=15 words. A STATEMENT, not a question (statements hold "
    "3-second retention; questions don't). 'No way this is real' energy.\n"
    "- beat_reframe: 120-155 words. THE STORY ITSELF, told as 5-7 short "
    "chapters: setup -> escalation -> weirder escalation -> consequence -> "
    "the turn that sets up the quote. Short punchy sentences (a new mini-"
    "revelation every ~8 seconds keeps retention). "
    "For weird mode: use ONLY the facts given in the material — never invent "
    "or exaggerate historical claims; if the material is flagged hypothetical, "
    "keep it clearly framed as imagination ('Imagine...', 'Suppose...'). "
    "You may expand with texture (setting, what people around thought, what "
    "it looked like) but every factual claim must come from the material.\n"
    "- quote_row: the chosen quote's row_number (integer).\n"
    "- beat_cta: one line. For weird mode this MUST be a send-CTA telling the "
    "viewer to send the reel to a specific kind of friend. For debate mode it "
    "MUST be a binary agree/disagree ask.\n"
    "For punch mode: beat_hook is ONE brutal line (<=10 words), beat_reframe "
    "MUST be an empty string, total spoken words 25-60 — a 7-15 second reel.\n"
    "- topic_query: 2-4 words for stock-footage search matching the story's "
    "VISUAL world (e.g. 'ancient greek ruins', 'crowded city night').\n"
    "- caption_first_line: <=8 words, curiosity gap, no hashtags.\n"
    "- trend_tag: one hashtag (no #) matching the topic, or empty string.\n"
    "Style rules (non-negotiable):\n"
    "- Write for ONE specific person, not an audience — the viewer must think "
    "'this is so my friend' and hit send.\n"
    "- Vocabulary so simple a tired 12-year-old instantly gets every word. No "
    "abstractions where a concrete image will do.\n"
    "- Extreme specificity beats broad claims: '2am doom-scrolling in bed' not "
    "'wasting time online'.\n"
    + playbooks.STORY_CRAFT + "\n"
    "Before answering: draft internally, critique your draft against the "
    "craft rules above (hook concreteness, escalation, CTA specificity, "
    "simplicity), fix every weakness, then output ONLY the improved final "
    "JSON.\n"
    "Total spoken words across beats 145-185 (a ~60-80 second reel — this is "
    "a LONG-form story reel, not a quick quote card). Output JSON only."
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


# Measured pace (ElevenLabs Adam, un-truncated): ~2.3 words/sec + ~2s of scene
# pads, so >=140 words guarantees the >=60s story and 215 caps it near ~95s
# (the model aims high; generous caps beat rejection-churn).
# Scenes are VO-sized, so the word budget IS the runtime budget.
MIN_SPOKEN_WORDS = 140
MAX_SPOKEN_WORDS = 215
PUNCH_MIN, PUNCH_MAX = 25, 60


def validate_story(d: dict, min_total: int = MIN_SPOKEN_WORDS,
                   mode: str = "story") -> tuple[bool, str]:
    """Hard limits the prompt promises — enforced deterministically."""
    try:
        hook = (d.get("beat_hook") or "").strip()
        reframe = (d.get("beat_reframe") or "").strip()
        cta = (d.get("beat_cta") or "").strip()
        if not hook or not cta:
            return False, "empty beat"
        if mode != "punch" and not reframe:
            return False, "empty beat"
        if len(hook.split()) > 15:
            return False, f"hook too long ({len(hook.split())} words)"
        if hook.rstrip().endswith("?"):
            return False, "hook must be a statement, not a question"
        total = len(hook.split()) + len(reframe.split()) + len(cta.split())
        if mode == "punch":
            if not (PUNCH_MIN <= total <= PUNCH_MAX):
                return False, f"punch total {total} outside {PUNCH_MIN}-{PUNCH_MAX}"
        else:
            if len(reframe.split()) > 185:
                return False, f"reframe too long ({len(reframe.split())} words)"
            if total < min_total:
                return False, f"total spoken words {total} < {min_total} (needs a ~60s story)"
            if total > MAX_SPOKEN_WORDS:
                return False, f"total spoken words {total} > {MAX_SPOKEN_WORDS}"
        if not isinstance(d.get("quote_row"), int):
            return False, "quote_row must be an integer"
        return True, "ok"
    except (TypeError, AttributeError) as e:
        return False, f"malformed: {e}"


def write_story(client, mode: str, material: dict, pool: list,
                extra_context: str = "") -> dict | None:
    """Two persona drafts -> rubric picks the winner (spec 1.2 B-lite).
    Returns validated dict or None (never raises)."""
    from studio.rubric import score_story
    try:
        role_tmpl = prompt_store.get("prompt.story_writer.role", _ROLE_DEFAULT)
        role = role_tmpl.format(
            mode=mode,
            material=json.dumps(material, ensure_ascii=False, indent=2),
            pool=json.dumps([{"row_number": p["row_number"], "quote": p["quote"]}
                             for p in pool[:20]], ensure_ascii=False, indent=2),
        )
        ctx = f"\n{extra_context}" if extra_context else ""
        drafts = []
        for persona in _PERSONAS:
            try:
                d = client.call("story_writer", _PREFIX, role,
                                f"Write the four beats now. {persona}{ctx}",
                                STORY_SCHEMA)
                ok, reason = validate_story(d or {}, mode=mode)
                drafts.append((d, ok, reason))
            except Exception as e:  # noqa: BLE001 - one dead draft is fine
                drafts.append((None, False, str(e)))
        valid = [(score_story(d), d) for d, ok, _ in drafts if ok]
        if valid:
            valid.sort(key=lambda t: t[0], reverse=True)
            return valid[0][1]
        # Neither validated: corrective retry on draft A's failure reason.
        d0, _, reason = drafts[0]
        print(f"  [story_writer] both drafts rejected ({reason}) — retrying once")
        d = client.call("story_writer", _PREFIX, role,
                        f"Your last draft was rejected: {reason}. "
                        f"Write the four beats again, fixing exactly that.{ctx}",
                        STORY_SCHEMA)
        ok, reason = validate_story(d or {}, mode=mode)
        if not ok:
            print(f"  [story_writer] rejected ({reason})")
            return None
        return d
    except Exception as e:  # noqa: BLE001 - never crash a reel
        print(f"  [story_writer] unavailable ({e})")
        return None
