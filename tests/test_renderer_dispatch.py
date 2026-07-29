"""Tests for pipeline.py --renderer flag dispatch and POV caller.

Per Task 11 follow-up (fix-R1): the old monolithic _run_pov_reel (397 lines,
renderer-aware) was split into two layers:

1. ``_run_pov_reel(quote_data_path, output_dir)`` — render-only orchestrator
   (MPT → HF → composite, silent final.mp4).
2. ``_pov_reel_flow(cfg, quote_data, mood, slot, timestamp, dry_run, manual,
   access_token)`` — caller-level reel-flow that owns VO, music, audio-mix,
   post-to-Instagram / Telegram-manual / dry_run, mark_posted.

The caller at ``run_pipeline`` no longer passes ``renderer=`` to a single
function — instead it computes ``pov = _reels_use_renderer(reel, carousel,
renderer)`` and dispatches to ``_pov_reel_flow``. The renderer is chosen up
here and reflected by the orchestrator's MPT+HF path (same renderer name
controls which engine composites in MPT/HF).

These tests verify the **dispatch** (any non-image renderer takes the POV
path) and the **caller wiring** (renderer flag flows through to
``_pov_reel_flow`` is invoked). The new orchestrator's body is covered in
``tests/test_run_pov_reel.py`` and ``tests/test_mix_audio_track.py``.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_reels_use_renderer_returns_true_for_reels():
    import pipeline as pl
    assert pl._reels_use_renderer(reel=True, carousel=False, renderer="hyperframes") is True
    assert pl._reels_use_renderer(reel=True, carousel=False, renderer="ffmpeg") is True
    assert pl._reels_use_renderer(reel=False, carousel=False, renderer="hyperframes") is True
    assert pl._reels_use_renderer(reel=True, carousel=True, renderer="hyperframes") is False
    assert pl._reels_use_renderer(reel=False, carousel=False, renderer="image") is False


def _stub_silent_final(tmp_path: Path) -> Path:
    """Return a fake silent final.mp4 path for orchestrator mocks."""
    p = tmp_path / "silent_final.mp4"
    p.write_bytes(b"\x00")
    return p


@pytest.mark.parametrize("renderer", ["hyperframes", "ffmpeg"])
def test_renderer_dispatches_to_pov_reel_flow(tmp_path, renderer):
    """Each --renderer value (non-image) reaches the caller-level _pov_reel_flow."""
    import pipeline as pl
    silent = _stub_silent_final(tmp_path)
    with patch.object(pl, "_pov_reel_flow", return_value={"post_id": "x"}) as mock_flow, \
         patch.object(pl, "_run_pov_reel", return_value=silent) as mock_render, \
         patch.object(pl, "init_db"), \
         patch.object(pl, "has_posted_today", return_value=False), \
         patch.object(pl, "get_valid_token_with_fallback", return_value="tok"):
        pl.run_pipeline(reel=True, renderer=renderer)
    assert mock_flow.called, f"_pov_reel_flow not called for renderer={renderer}"
    # The render-only orchestrator is what _pov_reel_flow ultimately invokes.
    # Verify the dispatch wired the renderer into the POV branch.
    mock_render.assert_not_called()  # _pov_reel_flow is patched, so render isn't reached


def test_renderer_hyperframes_takes_pov_branch():
    """HyperFrames is the default POV renderer (MPT + HF + composite)."""
    import pipeline as pl
    with patch.object(pl, "_pov_reel_flow", return_value={"post_id": None}) as mock_flow, \
         patch.object(pl, "init_db"), \
         patch.object(pl, "has_posted_today", return_value=False), \
         patch.object(pl, "get_valid_token_with_fallback", return_value="tok"):
        pl.run_pipeline(reel=True, renderer="hyperframes")
    assert mock_flow.called


def test_renderer_hyperframes_takes_pov_branch():
    """HyperFrames is one of the valid POV renderers (MPT + HF + composite)."""
    import pipeline as pl
    with patch.object(pl, "_pov_reel_flow", return_value={"post_id": None}) as mock_flow, \
         patch.object(pl, "init_db"), \
         patch.object(pl, "has_posted_today", return_value=False), \
         patch.object(pl, "get_valid_token_with_fallback", return_value="tok"):
        pl.run_pipeline(reel=True, renderer="hyperframes")
    assert mock_flow.called


def test_renderer_ffmpeg_takes_pov_branch():
    """ffmpeg renderer is a valid POV dispatch path."""
    import pipeline as pl
    with patch.object(pl, "_pov_reel_flow", return_value={"post_id": None}) as mock_flow, \
         patch.object(pl, "init_db"), \
         patch.object(pl, "has_posted_today", return_value=False), \
         patch.object(pl, "get_valid_token_with_fallback", return_value="tok"):
        pl.run_pipeline(reel=True, renderer="ffmpeg")
    assert mock_flow.called


def test_pov_reel_flow_invokes_new_orchestrator_with_paths(tmp_path):
    """The caller-level reel-flow invokes _run_pov_reel with the new signature.

    Regression guard for Task 11 follow-up: the old _run_pov_reel took
    (cfg, quote_data, mood, …, renderer) — TypeError on the next cron tick.
    The new orchestrator takes (quote_data_path: Path, output_dir: Path).
    """
    import pipeline as pl

    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    silent_final = tmp_path / "silent.mp4"
    silent_final.write_bytes(b"\x00")
    final_with_audio = tmp_path / "final.mp4"
    final_with_audio.write_bytes(b"\x00")

    with patch.object(pl, "_run_pov_reel", return_value=silent_final) as mock_render, \
         patch.object(pl, "_concat_vo_scenes", return_value=tmp_path / "vo.mp3"), \
         patch.object(pl, "_mix_audio_track", return_value=final_with_audio) as mock_mix, \
         patch.object(pl, "_select_reel_music", return_value=None), \
         patch.object(pl, "edge_tts_available", return_value=False), \
         patch.object(pl, "save_post", return_value=1), \
         patch.object(pl, "save_log") as mock_save_log, \
         patch.object(pl, "mark_as_posted"), \
         patch.object(pl, "mark_posted"), \
         patch.object(pl, "pick_best_hook", return_value={"hook_id": "h1"}), \
         patch.object(pl, "post_reel_to_instagram", return_value="ig_1"), \
         patch.object(pl, "Notifier"):
        record = pl._pov_reel_flow(
            MagicMock(), {"quote": "q", "audience": "a", "caption": "c",
                          "row_number": 1, "cta": ""},
            "calm_stoic", 1, "ts", dry_run=True, manual=False,
            access_token="t",
        )

    # Orchestrator invoked with new signature (Path, Path) — regression guard.
    assert mock_render.called
    args = mock_render.call_args.kwargs
    assert "quote_data_path" in args
    assert "output_dir" in args
    assert isinstance(args["quote_data_path"], Path)
    assert isinstance(args["output_dir"], Path)

    # Audio-mix step ran (audio-mix helper invoked).
    assert mock_mix.called

    # Returned the post record (dry_run path).
    assert record["dry_run"] is True
    assert record["pov"] is True
    mock_save_log.assert_called_once()
