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
