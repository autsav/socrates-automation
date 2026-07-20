"""The 6-phase viral formula, enforced by code (spec 1+2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.story_writer import (
    validate_formula, EXEMPLAR_WEIRD, EXEMPLAR_DEBATE, _ROLE_DEFAULT)


def _script(hook, reframe, cta="Send this to the friend who needs it most."):
    return {"beat_hook": hook, "beat_reframe": reframe, "quote_row": 1,
            "beat_cta": cta, "topic_query": "man storm",
            "caption_first_line": "Read this twice."}


GOOD_REFRAME = (
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
    "ever carried.")


def test_happy_path_passes():
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        GOOD_REFRAME))
    assert ok, r


def test_hook_must_address_viewer():
    ok, r = validate_formula(_script(
        "A rich merchant lost everything in a storm.", GOOD_REFRAME))
    assert not ok and "viewer" in r


def test_hook_must_not_resolve():
    ok, r = validate_formula(_script(
        "Here's how you stop losing: the answer is Stoicism.", GOOD_REFRAME))
    assert not ok


def test_stakes_need_second_person_early():
    third_person = GOOD_REFRAME.replace("You know that thing you replay at 2am. "
                                        "The loss you never talk about. ", "")
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        third_person))
    assert not ok and "second person" in r


def test_no_early_resolution_vocab():
    spoiled = GOOD_REFRAME.replace("One storm took",
                                   "The lesson is simple. One storm took")
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        spoiled))
    assert not ok and "resolution" in r


def test_cliffhanger_marker_required():
    flat = GOOD_REFRAME.replace("And nobody expected what he did next. ", "") \
                       .replace("Then he stopped leaving. ", "")
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        flat))
    assert not ok and "cliffhanger" in r


def test_exemplars_pass_their_own_formula():
    for ex in (EXEMPLAR_WEIRD, EXEMPLAR_DEBATE):
        ok, r = validate_formula(ex)
        assert ok, r


def test_prompt_embeds_formula_and_exemplars():
    t = _ROLE_DEFAULT.lower()
    assert "open loop" in t and "cliffhanger" in t
    assert EXEMPLAR_WEIRD["beat_hook"] in _ROLE_DEFAULT
    assert EXEMPLAR_DEBATE["beat_hook"] in _ROLE_DEFAULT
    assert '"lesson"' in t or "the word 'lesson' is banned" in t or "banned" in t


def test_quote_leak_rejected():
    from studio.story_writer import write_story

    calls = []

    class LeakClient:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            leak = ("You count it at night. Your savings. Your stuff. "
                    "Now meet a man on a boat. A storm hit hard. "
                    "And nobody expected what he did next. He smiled at the sand. "
                    "He walked inland owning nothing but his mind. He said he who "
                    "is not satisfied with a little is satisfied with nothing at all. "
                    * 3)[:900]
            return {"beat_hook": "You'd lose everything and you know exactly what first.",
                    "beat_reframe": leak,
                    "quote_row": 1,
                    "beat_cta": "Send this to the friend who would start over smiling.",
                    "topic_query": "man beach storm",
                    "caption_first_line": "He lost the boat. Kept everything."}

    out = write_story(LeakClient(), "weird", {"hook_fact": "x"},
                      [{"row_number": 1, "quote": "He who is not satisfied with a little, is satisfied with nothing."}])
    # Both drafts + retry all leak -> rejected entirely.
    assert out is None and len(calls) == 3


def test_quote_row_out_of_pool_rejected():
    from studio.story_writer import write_story

    calls = []

    class OutOfPoolClient:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            return {"beat_hook": "You'd lose everything and you know exactly what first.",
                    "beat_reframe": GOOD_REFRAME,
                    "quote_row": 7,  # not in the offered pool (only row 3 below)
                    "beat_cta": "Send this to the friend who would start over smiling.",
                    "topic_query": "man beach storm",
                    "caption_first_line": "He lost the boat. Kept everything."}

    out = write_story(OutOfPoolClient(), "weird", {"hook_fact": "x"},
                      [{"row_number": 3, "quote": "Some other quote entirely."}])
    # Both drafts + retry all use an out-of-pool row -> rejected entirely.
    assert out is None and len(calls) == 3


def test_hook_accepts_contraction_with_glued_punctuation():
    ok, r = validate_formula(_script(
        "Comfort is quietly killing you.", GOOD_REFRAME))
    assert ok, r


def test_stakes_accepts_contraction_first_word():
    stakes_variant = GOOD_REFRAME.replace(
        "You know that thing you replay at 2am. The loss you never talk about. ",
        "Yourself first, they said, and you believed it. ")
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        stakes_variant))
    assert ok, r


def test_hook_without_second_person_still_fails():
    ok, r = validate_formula(_script(
        "Losing everything overnight destroys a young man's plans.", GOOD_REFRAME))
    assert not ok and "viewer" in r
