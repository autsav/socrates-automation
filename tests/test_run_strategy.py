"""Tests for Pipeline._run_strategy() — trend-led IG content orchestrator."""
from unittest.mock import MagicMock

from pipeline import Pipeline


def _make_pipeline(studio=None, excel=None):
    p = Pipeline.__new__(Pipeline)
    p.studio = studio or MagicMock()
    p.excel_reader = excel or MagicMock()
    p.args = MagicMock(strategy=True)
    return p


def test_run_strategy_happy_path():
    studio = MagicMock()
    studio.trend_scout.run.return_value = {
        "headline": "Stoic doomscrolling", "keywords": ["marcus"], "angle": "morning pages"}
    studio.social_strategist.run.return_value = {
        "hook": "You will not finish this.",
        "bridge": None,
        "quote": "Suffering is imagination.", "cta": "Save.",
        "caption": "Seneca on spirals.",
        "hashtags": ["#a", "#b", "#c"],
        "mood": "stark", "attribution": "Seneca",
        "audience": "doomscrollers", "row_number": 1,
    }
    studio.music_director.pick.return_value = {"track_id": "jam-1"}
    studio.prompt_architect.run.return_value = "FLUX prompt"
    excel = MagicMock()
    p = _make_pipeline(studio=studio, excel=excel)
    p._match_quote = MagicMock(return_value={"row_number": 1, "text": "q",
                                              "attribution": "Seneca", "mood": "stark"})
    p._render_via_content = MagicMock(return_value="/tmp/reel.mp4")
    out = p._run_strategy()
    assert out == "/tmp/reel.mp4"
    assert studio.trend_scout.run.called
    assert studio.social_strategist.run.called
    assert studio.music_director.pick.called
    assert studio.prompt_architect.run.called


def test_run_strategy_falls_back_when_trend_empty():
    studio = MagicMock()
    studio.trend_scout.run.return_value = None
    p = _make_pipeline(studio=studio)
    p._fallback_to_studio = MagicMock(return_value="/tmp/studio.mp4")
    p._render_via_content = MagicMock()
    out = p._run_strategy()
    assert out == "/tmp/studio.mp4"
    assert studio.social_strategist.run.call_count == 0


def test_run_strategy_falls_back_when_no_quote_match():
    studio = MagicMock()
    studio.trend_scout.run.return_value = {"headline": "x", "keywords": ["y"], "angle": "z"}
    p = _make_pipeline(studio=studio)
    p._match_quote = MagicMock(return_value=None)
    p._fallback_to_studio = MagicMock(return_value="/tmp/studio.mp4")
    out = p._run_strategy()
    assert out == "/tmp/studio.mp4"


def test_run_strategy_skips_music_on_failure():
    from studio.social_strategist import StrategyInput
    studio = MagicMock()
    studio.trend_scout.run.return_value = {"headline": "x", "keywords": ["y"], "angle": "z"}
    creative = {
        "hook": "You will not finish this.",
        "bridge": None, "quote": "q", "cta": "c", "caption": "cap",
        "hashtags": ["#a", "#b", "#c"], "mood": "stark",
        "attribution": "a", "audience": "z", "row_number": 1,
    }
    studio.social_strategist.run.return_value = creative
    studio.music_director.pick.side_effect = RuntimeError("jamendo down")
    studio.prompt_architect.run.return_value = "FLUX prompt"
    p = _make_pipeline(studio=studio)
    p._match_quote = MagicMock(return_value={"row_number": 1, "text": "q",
                                              "attribution": "x", "mood": "stark"})
    p._render_via_content = MagicMock(return_value="/tmp/reel.mp4")
    out = p._run_strategy()
    assert out == "/tmp/reel.mp4"  # didn't crash
    args, _ = p._render_via_content.call_args
    assert args[0]["music_track_id"] is None


def test_run_strategy_falls_back_on_opus_failure():
    from studio.social_strategist import StrategyInput
    from studio.client import StudioError
    studio = MagicMock()
    studio.trend_scout.run.return_value = {"headline": "x", "keywords": ["y"], "angle": "z"}
    studio.social_strategist.run.side_effect = StudioError("opus dead")
    p = _make_pipeline(studio=studio)
    p._match_quote = MagicMock(return_value={"row_number": 1, "text": "q",
                                              "attribution": "x", "mood": "stark"})
    p._fallback_to_studio = MagicMock(return_value="/tmp/studio.mp4")
    out = p._run_strategy()
    assert out == "/tmp/studio.mp4"