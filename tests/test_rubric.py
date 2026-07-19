"""The rubric IS the judge (spec: code judges, never a judge agent)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.rubric import score_story, score_concept


def _story(hook, reframe, cta):
    return {"beat_hook": hook, "beat_reframe": reframe, "beat_cta": cta}


def test_concrete_hook_beats_abstract():
    concrete = _story("He ate stale bread on a marble floor for 3 days.",
                      "One sentence. Another short one. Then a turn.",
                      "Send this to your most stubborn friend.")
    abstract = _story("Success is really about your mindset and growth.",
                      "One sentence. Another short one. Then a turn.",
                      "Send this to your most stubborn friend.")
    assert score_story(concrete) > score_story(abstract)


def test_specific_send_cta_beats_generic():
    a = _story("He owned one cup and threw it away.", "Short. Sharp. Turn.",
               "Send this to the friend who guards their stuff.")
    b = _story("He owned one cup and threw it away.", "Short. Sharp. Turn.",
               "Share this post.")
    assert score_story(a) > score_story(b)


def test_short_sentences_beat_run_ons():
    punchy = _story("Rome's richest man slept on dirt.",
                    "He did it monthly. Friends laughed. He trained. Fear lost.",
                    "Send this to someone scared of losing it all.")
    runon = _story("Rome's richest man slept on dirt.",
                   "He did it monthly and his friends laughed at him because they "
                   "did not understand that he was training so that fear would "
                   "eventually lose its grip on him entirely over time.",
                   "Send this to someone scared of losing it all.")
    assert score_story(punchy) > score_story(runon)


def test_never_raises_on_garbage():
    assert score_story({}) == 0.0
    assert score_story({"beat_hook": None}) == 0.0
    assert score_concept("", "") >= 0.0


def test_statement_concept_beats_question():
    assert score_concept("Discipline is a lie you tell daily.", "First line.\nBody") > \
           score_concept("Is discipline a lie you tell daily?", "First line.\nBody")
