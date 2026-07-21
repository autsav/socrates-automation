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
import re

from studio.types import _obj
from studio import playbooks
from studio.rubric import RESOLUTION_PHRASES
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

EXEMPLAR_WEIRD = {
    "beat_hook": "You lost something this year you're still pretending doesn't hurt.",
    "beat_reframe": (
        "You know that thing you replay at 2am. The loss you never talk about. "
        "Now meet a merchant named Zeno. Everything he owned sat in one ship's hold. "
        "Purple dye. A fortune. One storm took all of it to the bottom of the sea. "
        "He washed up in Athens with nothing. Forty years old. Ruined. "
        "And nobody expected what he did next. He walked into a bookshop, dripping "
        "wet, and started reading. Then he stopped leaving. He gave up rebuilding "
        "the fortune. He sat in a painted porch and started talking about what "
        "storms cannot take. Strangers gathered. Kings sent letters. The porch "
        "became a school. The school became Stoicism. Twenty-three centuries later "
        "you are still hearing about it. His shipwreck built more than his ships "
        "ever carried."),
    "quote_row": 7,
    "beat_cta": "Send this to the friend who lost something this year.",
    "topic_query": "man walking storm harbor",
    "caption_first_line": "The storm did him a favor.",
}

EXEMPLAR_DEBATE = {
    "beat_hook": "Your grind is the most expensive thing you own.",
    "beat_reframe": (
        "You wear the exhaustion like a badge. Booked every hour. Answered every "
        "ping. And you tell yourself it is temporary. Two thousand years ago Rome "
        "had men like you. Senators sprinting between banquets and battles, "
        "collecting titles like you collect tabs. One philosopher watched them "
        "run. He was busy too. Tutor to an emperor. Richest man in the city. "
        "Then he wrote something in a letter that stopped his friend cold. "
        "He said the busiest men he knew were the poorest. Not in coin. In hours "
        "they actually owned. They rented every minute to someone else's urgency. "
        "Until the day ran out and none of it was theirs. He started guarding his "
        "mornings like a miser. Refusing meetings. Saying no to Caesar's circle. "
        "The city called it arrogance. He called it the only wealth that counts."),
    "quote_row": 7,
    "beat_cta": "Agree or disagree: busy is just broke with better branding.",
    "topic_query": "man rushing city crowd",
    "caption_first_line": "Busy is not the flex you think.",
}

_EXEMPLAR_WEIRD_BLOCK = (
    "EXEMPLAR (weird mode):\n"
    f"{EXEMPLAR_WEIRD['beat_hook']}\n"
    f"{EXEMPLAR_WEIRD['beat_reframe']}\n"
    f"{EXEMPLAR_WEIRD['beat_cta']}"
)

_EXEMPLAR_DEBATE_BLOCK = (
    "EXEMPLAR (debate mode):\n"
    f"{EXEMPLAR_DEBATE['beat_hook']}\n"
    f"{EXEMPLAR_DEBATE['beat_reframe']}\n"
    f"{EXEMPLAR_DEBATE['beat_cta']}"
)

_ROLE_DEFAULT = (
    "Mode: {mode}\n"
    "Material:\n{material}\n"
    "Available quotes (choose the one that lands as the TWIST — the payoff the "
    "story was secretly building to; set quote_row to its row_number):\n{pool}\n\n"
    "Write the reel as four beats, following the 6-PHASE VIRAL FORMULA:\n"
    "- beat_hook (0-3s): <=15 words. A STATEMENT, not a question (statements "
    "hold 3-second retention; questions don't). It MUST address the viewer "
    "directly ('you'/'your') and open a loop about THEIR life — never resolve "
    "it, never name the historical figure. 'No way this is real' energy.\n"
    "- beat_reframe: 120-155 words, built in three phases inside one field:\n"
    "  * STAKES (3-10s, the first ~25 words): second person ('you'/'your'), "
    "naming the exact private thing the viewer recognizes in themselves — no "
    "resolution vocabulary here.\n"
    "  * STORY ENTRY (10-25s): pivot to the historical figure, set up the "
    "situation, and end this stretch on an open loop / CLIFFHANGER — a "
    "sentence starting with a marker like 'Then', 'Until', 'But', or 'And "
    "nobody expected what he did next' / 'And no one saw it coming'.\n"
    "  * ESCALATION (25-40s): raise the stakes or the strangeness with short "
    "punchy sentences (a new mini-revelation every ~8 seconds) — still no "
    "resolution words ('that's why', 'the answer', 'here's how', the word "
    "'lesson', 'this means', 'the secret is') before the payoff.\n"
    "  * PAYOFF (40-50s): both loops — the viewer's stakes and the figure's "
    "story — close together, landing on the quote as the twist.\n"
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
    "ANTI-RULES (non-negotiable):\n"
    "- Never open with the historical figure.\n"
    "- Never resolve a loop before the payoff phase.\n"
    "- The word 'lesson' is banned.\n"
    "- The viewer's life is the story — the ancient is the twist.\n"
    "- Never include the quote's own words inside beat_reframe — the quote "
    "scene delivers it. End the reframe one breath BEFORE the quote.\n"
    f"{_EXEMPLAR_WEIRD_BLOCK}\n\n"
    f"{_EXEMPLAR_DEBATE_BLOCK}\n\n"
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


_CLIFFHANGER_STARTS = ("then ", "until ", "but ", "and nobody", "and no one")


_SECOND_PERSON = {"you", "your", "you're", "you've", "you'll", "you'd", "yourself"}


def validate_formula(d: dict) -> tuple[bool, str]:
    """The 6-phase viral formula, deterministically (spec 2). Runs AFTER
    validate_story; story/weird/debate modes only."""
    try:
        hook = (d.get("beat_hook") or "").strip()
        reframe = (d.get("beat_reframe") or "").strip()
        hl = hook.lower()
        if not (set(re.findall(r"[a-z']+", hl)) & _SECOND_PERSON):
            return False, "hook must address the viewer (you/your)"
        if any(p in hl for p in RESOLUTION_PHRASES):
            return False, "hook resolves its own loop"
        words = reframe.split()
        if not words:
            return False, "empty reframe"
        first25 = " ".join(words[:25]).lower()
        if not (set(re.findall(r"[a-z']+", first25)) & _SECOND_PERSON):
            return False, "stakes phase needs second person in the first 25 words"
        two_thirds = " ".join(words[: (2 * len(words)) // 3]).lower()
        if any(p in two_thirds for p in RESOLUTION_PHRASES):
            return False, "resolution vocabulary before the payoff phase"
        third = len(words) // 3
        middle = " ".join(words[third: 2 * third]).lower()
        sentences = [s.strip() for s in middle.replace("!", ".").replace("?", ".").split(".")]
        # A sentence STARTING with an unresolved-turn marker; also accept the
        # marker appearing right after a sentence break anywhere mid-text.
        has_cliff = any(s.startswith(_CLIFFHANGER_STARTS) or
                        s.startswith(("and nobody", "and no one"))
                        for s in sentences if s)
        if not has_cliff:
            return False, "cliffhanger marker missing from the middle third"
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, f"malformed: {e}"


REVISION_THRESHOLD = 6.5


def _hook_pass(client, story: dict, mode: str) -> dict:
    """8-angle hook variant pass (spec 4): swap in the best-scoring valid
    candidate, or keep the existing hook on any trouble. Skipped for punch
    mode (its single-line hook IS the whole beat)."""
    if mode == "punch":
        return story
    try:
        from studio.hook_specialist import generate_hooks, pick_hook
        story["beat_hook"] = pick_hook(
            generate_hooks(client, story), story["beat_hook"])
    except Exception:  # noqa: BLE001
        pass
    return story


def _quote_leak(d: dict, pool: list) -> bool:
    """True when the chosen quote's words appear inside the reframe — the
    quote scene delivers the quote; the story must stop one breath before."""
    try:
        row = d.get("quote_row")
        q = next((p["quote"] for p in pool if p["row_number"] == row), "")
        _norm = lambda s: re.sub(r"[^a-z ]", "", (s or "").lower())
        head = " ".join(_norm(q).split()[:6])
        return bool(head) and head in _norm(d.get("beat_reframe") or "")
    except Exception:  # noqa: BLE001
        return False


def _passes_all_gates(d, mode, pool):
    """Same gates the draft loop enforces, shared with the revision path."""
    ok, _ = validate_story(d or {}, mode=mode)
    if ok and mode != "punch":
        ok, _ = validate_formula(d or {})
    if ok and d and not any(p["row_number"] == d.get("quote_row") for p in pool):
        ok = False
    return ok


def _maybe_revise(client, role, winner, mode, pool, ctx):
    """One conditional revision pass (spec 3): subscore report in, the
    revised draft ships only if it passes every gate and scores no worse
    than the winner it's replacing. Never raises — winner ships on any
    trouble."""
    from studio.rubric import score_story_detailed

    if mode == "punch":
        return winner
    try:
        detail = score_story_detailed(winner)
        if not detail["weaknesses"] and detail["total"] >= REVISION_THRESHOLD:
            return winner
        subscore_lines = "\n".join(
            f"- {k}: {v}/10" for k, v in detail.items()
            if k not in ("total", "weaknesses"))
        weakness_lines = "\n".join(f"- {w}" for w in detail["weaknesses"]) or "- (none named)"
        report = (
            "Quality report on your last draft:\n"
            f"{subscore_lines}\n- total: {detail['total']}/10\n"
            f"Weaknesses:\n{weakness_lines}\n\n"
            "Rewrite the four beats fixing EXACTLY the named weaknesses. "
            "Keep every phrase that already works.\n"
            f"{json.dumps(winner, ensure_ascii=False)}"
        )
        revised = client.call("story_writer", _PREFIX, role, f"{report}{ctx}",
                              STORY_SCHEMA)
        if not _passes_all_gates(revised, mode, pool):
            return winner
        if mode != "punch" and _quote_leak(revised or {}, pool):
            return winner
        if score_story_detailed(revised)["total"] < detail["total"]:
            return winner
        return revised
    except Exception:  # noqa: BLE001 - revision must never crash a reel
        return winner


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
                if ok and mode != "punch":
                    ok, reason = validate_formula(d or {})
                if ok and mode != "punch" and _quote_leak(d or {}, pool):
                    ok, reason = False, "quote text leaked into the reframe"
                if (ok and d and
                        not any(p["row_number"] == d.get("quote_row") for p in pool)):
                    ok, reason = False, "quote_row not in the offered pool"
                drafts.append((d, ok, reason))
            except Exception as e:  # noqa: BLE001 - one dead draft is fine
                drafts.append((None, False, str(e)))
        valid = [(score_story(d), d) for d, ok, _ in drafts if ok]
        if valid:
            valid.sort(key=lambda t: t[0], reverse=True)
            winner = valid[0][1]
            winner = _maybe_revise(client, role, winner, mode, pool, ctx)
            return _hook_pass(client, winner, mode)
        # Neither validated: corrective retry on draft A's failure reason.
        d0, _, reason = drafts[0]
        print(f"  [story_writer] formula-reject mode={mode} reason={reason} — retrying once")
        d = client.call("story_writer", _PREFIX, role,
                        f"Your last draft was rejected: {reason}. "
                        f"Write the four beats again, fixing exactly that.{ctx}",
                        STORY_SCHEMA)
        ok, reason = validate_story(d or {}, mode=mode)
        if ok and mode != "punch":
            ok, reason = validate_formula(d or {})
        if ok and mode != "punch" and _quote_leak(d or {}, pool):
            ok, reason = False, "quote text leaked into the reframe"
        if (ok and d and
                not any(p["row_number"] == d.get("quote_row") for p in pool)):
            ok, reason = False, "quote_row not in the offered pool"
        if not ok:
            print(f"  [story_writer] formula-reject mode={mode} reason={reason}")
            return None
        return _hook_pass(client, d, mode)
    except Exception as e:  # noqa: BLE001 - never crash a reel
        print(f"  [story_writer] unavailable ({e})")
        return None
