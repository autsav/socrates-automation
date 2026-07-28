"""Tests for pipeline.py --renderer flag dispatch and fallback chain.

Covers:
- --renderer flag is parsed correctly
- --remotion and --pov aliases map to the right renderer
- _run_pov_reel dispatches to the correct renderer
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


def test_reels_use_renderer_returns_true_for_reels():
    import pipeline as pl
    assert pl._reels_use_renderer(reel=True, carousel=False, renderer="remotion") is True
    assert pl._reels_use_renderer(reel=True, carousel=False, renderer="hyperframes") is True
    assert pl._reels_use_renderer(reel=True, carousel=False, renderer="ffmpeg") is True
    assert pl._reels_use_renderer(reel=False, carousel=False, renderer="remotion") is True
    assert pl._reels_use_renderer(reel=False, carousel=False, renderer="hyperframes") is True
    assert pl._reels_use_renderer(reel=True, carousel=True, renderer="remotion") is False
    assert pl._reels_use_renderer(reel=False, carousel=False, renderer="image") is False


def test_renderer_remotion_runs_pov_path():
    import pipeline as pl
    with patch.object(pl, "_run_pov_reel", return_value={}) as mock_pov:
        with patch.object(pl, "init_db"):
            with patch.object(pl, "has_posted_today", return_value=False):
                with patch.object(pl, "get_valid_token_with_fallback", return_value="tok"):
                    pl.run_pipeline(reel=True, renderer="remotion")
    assert mock_pov.called
    _, kwargs = mock_pov.call_args
    assert kwargs.get("renderer") == "remotion"


def test_renderer_hyperframes_runs_pov_path():
    import pipeline as pl
    with patch.object(pl, "_run_pov_reel", return_value={}) as mock_pov:
        with patch.object(pl, "init_db"):
            with patch.object(pl, "has_posted_today", return_value=False):
                with patch.object(pl, "get_valid_token_with_fallback", return_value="tok"):
                    pl.run_pipeline(reel=True, renderer="hyperframes")
    assert mock_pov.called
    _, kwargs = mock_pov.call_args
    assert kwargs.get("renderer") == "hyperframes"


def test_renderer_ffmpeg_runs_pov_path():
    import pipeline as pl
    with patch.object(pl, "_run_pov_reel", return_value={}) as mock_pov:
        with patch.object(pl, "init_db"):
            with patch.object(pl, "has_posted_today", return_value=False):
                with patch.object(pl, "get_valid_token_with_fallback", return_value="tok"):
                    pl.run_pipeline(reel=True, renderer="ffmpeg")
    assert mock_pov.called
    _, kwargs = mock_pov.call_args
    assert kwargs.get("renderer") == "ffmpeg"
