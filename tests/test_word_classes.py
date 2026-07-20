"""Per-word animation classes (spec 2) — pure, prioritized, never raises."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.word_classes import classify_words


def _words(text):
    return [{"w": w, "start": i * 0.3, "end": i * 0.3 + 0.25}
            for i, w in enumerate(text.split())]


def test_classes_assigned():
    out = classify_words(_words("He owned 300 ships. Nobody understood him."))
    by_word = {w["w"]: w["cls"] for w in out}
    assert by_word["300"] == "num"
    assert by_word["Nobody"] == "neg"
    assert by_word["ships."] == "end"          # sentence-terminal
    assert by_word["understood"] in ("stress", "plain")
    assert by_word["him."] == "end"


def test_priority_num_beats_end():
    out = classify_words(_words("He lost 40."))
    assert {w["w"]: w["cls"] for w in out}["40."] == "num"


def test_power_words_tagged():
    out = classify_words(_words("The fear was real"))
    assert {w["w"]: w["cls"] for w in out}["fear"] == "power"


def test_stress_is_longest_word_per_sentence():
    out = classify_words(_words("He rehearsed poverty monthly"))
    assert {w["w"]: w["cls"] for w in out}["rehearsed"] == "stress"


def test_curly_apostrophe_negation():
    out = classify_words(_words("Why don’t you understand"))
    assert {w["w"]: w["cls"] for w in out}["don’t"] == "neg"


def test_garbage_never_raises():
    assert classify_words([]) == []
    out = classify_words([{"w": None, "start": 0, "end": 1}])
    assert out[0]["cls"] == "plain"
