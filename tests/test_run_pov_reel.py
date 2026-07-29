"""Tests for pipeline._run_pov_reel() (orchestrator) + _pov_reel_flow() (caller).

Two layers:
  - ``_run_pov_reel(quote_data_path, output_dir)`` → Path
        Render-only orchestrator (MPT → HF → ffmpeg composite, silent final.mp4).
  - ``_pov_reel_flow(cfg, quote_data, mood, slot, timestamp, dry_run, manual,
                    access_token)`` → dict
        Caller-level reel-flow that owns VO, music, audio-mix, posting.

The orchestrator chains MPT → HyperFrames → ffmpeg composite into a single
Path return value. Hard cutover (per Q1): NO in-app fallback reel. Exceptions
(MptRenderError, HfRenderError, CompositeError) propagate.

The ThreadPoolExecutor scaffolding is preserved as future-proofing, but HF
waits on MPT's word_timings so wall-time is sequential in practice.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline import (
    HfRenderError,
    MptRenderError,
    _run_pov_reel,
)


# ── Orchestrator tests (Task 11) ──────────────────────────────────────────────


def _setup_paths(tmp_path: Path) -> tuple[Path, Path]:
    """Return (quote_data_path, output_dir) for orchestrator tests."""
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return quote_data_path, output_dir


def test_run_pov_reel_orchestrates_mpt_hf_composite(tmp_path):
    """Happy path: MPT → HF → composite; returns the composited final path."""
    quote_data_path, output_dir = _setup_paths(tmp_path)

    with patch("pipeline._invoke_mpt") as mock_mpt, \
         patch("pipeline._invoke_hyperframes") as mock_hf, \
         patch("pipeline._composite_reels") as mock_composite:
        mock_mpt.return_value = {
            "base_video": tmp_path / "base.mp4",
            "word_timings": tmp_path / "word_timings.json",
            "duration_sec": 16.0,
            "resolution": [1080, 1920],
        }
        mock_hf.return_value = tmp_path / "overlay.mp4"
        mock_composite.return_value = tmp_path / "final.mp4"

        result = _run_pov_reel(quote_data_path, output_dir)

    expected_final = output_dir / "reels" / "quote_data" / "final.mp4"
    assert result == expected_final
    assert mock_mpt.called
    assert mock_hf.called
    assert mock_composite.called


def test_run_pov_reel_skips_composite_when_mpt_fails(tmp_path):
    """MPT failure propagates and prevents composite (no fallback reel)."""
    quote_data_path, output_dir = _setup_paths(tmp_path)

    with patch("pipeline._invoke_mpt") as mock_mpt, \
         patch("pipeline._invoke_hyperframes") as mock_hf, \
         patch("pipeline._composite_reels") as mock_composite:
        mock_mpt.side_effect = MptRenderError("MPT subprocess crashed")

        with pytest.raises(MptRenderError):
            _run_pov_reel(quote_data_path, output_dir)

    assert not mock_composite.called
    # No fallback.mp4 may exist anywhere — the orchestrator must not silently
    # produce a degraded reel under any stage failure (Q1).
    assert not (output_dir / "fallback.mp4").exists()


def test_run_pov_reel_no_fallback_on_mpt_failure(tmp_path):
    """Per Q1 (hard cutover): NO in-app fallback reel on any stage failure.

    MPT failure surfaces MptRenderError; orchestrator does NOT emit a
    replacement reel (no ffmpeg POV fallback, no Remotion branch).
    """
    quote_data_path, output_dir = _setup_paths(tmp_path)

    with patch("pipeline._invoke_mpt") as mock_mpt:
        mock_mpt.side_effect = MptRenderError("MPT subprocess crashed")
        with pytest.raises(MptRenderError):
            _run_pov_reel(quote_data_path, output_dir)

    # Sanity: no fallback.mp4 was written by any code path.
    assert not (output_dir / "fallback.mp4").exists()


def test_run_pov_reel_returns_final_mp4_path(tmp_path):
    """The returned path is the orchestrator's run_dir/final.mp4."""
    quote_data_path, output_dir = _setup_paths(tmp_path)

    with patch("pipeline._invoke_mpt") as mock_mpt, \
         patch("pipeline._invoke_hyperframes") as mock_hf, \
         patch("pipeline._composite_reels") as mock_composite:
        mock_mpt.return_value = {
            "base_video": tmp_path / "base.mp4",
            "word_timings": tmp_path / "word_timings.json",
            "duration_sec": 16.0,
            "resolution": [1080, 1920],
        }
        mock_hf.return_value = tmp_path / "overlay.mp4"
        mock_composite.return_value = tmp_path / "final.mp4"

        result = _run_pov_reel(quote_data_path, output_dir)

    expected_final = output_dir / "reels" / "quote_data" / "final.mp4"
    assert result == expected_final
    assert result.name == "final.mp4"
    assert result.is_absolute()


def test_run_pov_reel_skips_composite_when_hf_fails(tmp_path):
    """HyperFrames failure propagates and prevents composite (no fallback reel)."""
    quote_data_path, output_dir = _setup_paths(tmp_path)

    with patch("pipeline._invoke_mpt") as mock_mpt, \
         patch("pipeline._invoke_hyperframes") as mock_hf, \
         patch("pipeline._composite_reels") as mock_composite:
        mock_mpt.return_value = {
            "base_video": tmp_path / "base.mp4",
            "word_timings": tmp_path / "word_timings.json",
            "duration_sec": 16.0,
            "resolution": [1080, 1920],
        }
        mock_hf.side_effect = HfRenderError("HyperFrames overlay crashed")

        with pytest.raises(HfRenderError):
            _run_pov_reel(quote_data_path, output_dir)

    assert mock_mpt.called
    assert not mock_composite.called
    assert not (output_dir / "fallback.mp4").exists()


def test_run_pov_reel_isolates_run_dir_via_run_id(tmp_path):
    """Regression for C3: per-invocation run_id isolates run_dirs.

    Caller passes run_id=timestamp so concurrent / overlapping slots don't
    collide in OUTPUT_DIR/reels/quote_data/. Without run_id, the orchestrator
    falls back to quote_data_path.stem — safe for unique JSON names only.
    """
    quote_data_path, output_dir = _setup_paths(tmp_path)

    with patch("pipeline._invoke_mpt") as mock_mpt, \
         patch("pipeline._invoke_hyperframes") as mock_hf, \
         patch("pipeline._composite_reels") as mock_composite:
        mock_mpt.return_value = {
            "base_video": tmp_path / "base.mp4",
            "word_timings": tmp_path / "word_timings.json",
            "duration_sec": 16.0,
            "resolution": [1080, 1920],
        }
        mock_hf.return_value = tmp_path / "overlay.mp4"
        mock_composite.return_value = tmp_path / "final.mp4"

        # Caller-side timestamp uniqueness
        result_a = _run_pov_reel(quote_data_path, output_dir, run_id="20260729_120000")
        result_b = _run_pov_reel(quote_data_path, output_dir, run_id="20260729_130000")

    # Two distinct run_dirs → two distinct final.mp4 paths.
    assert result_a.parent != result_b.parent
    assert result_a.parent.name == "20260729_120000"
    assert result_b.parent.name == "20260729_130000"
    # Backward compat: no run_id → falls back to quote_data_path.stem.
    expected_fallback = output_dir / "reels" / "quote_data" / "final.mp4"
    assert result_a.parent.parent.parent == output_dir


def test_run_pov_reel_run_id_default_uses_stem(tmp_path):
    """Backward compat: without run_id, orchestrator derives from JSON stem."""
    quote_data_path, output_dir = _setup_paths(tmp_path)

    with patch("pipeline._invoke_mpt") as mock_mpt, \
         patch("pipeline._invoke_hyperframes") as mock_hf, \
         patch("pipeline._composite_reels") as mock_composite:
        mock_mpt.return_value = {
            "base_video": tmp_path / "base.mp4",
            "word_timings": tmp_path / "word_timings.json",
            "duration_sec": 16.0,
            "resolution": [1080, 1920],
        }
        mock_hf.return_value = tmp_path / "overlay.mp4"
        mock_composite.return_value = tmp_path / "final.mp4"

        result = _run_pov_reel(quote_data_path, output_dir)  # no run_id

    assert result.parent.name == "quote_data"  # stem fallback
    assert result.parent.parent.parent == output_dir


# ── Caller-level regression tests (Task 11 fix-R1) ───────────────────────────


def _setup_caller(tmp_path: Path) -> tuple:
    """Build files + mocks for a _pov_reel_flow() dry_run=true run.

    Returns (quote_data, cfg, silent_final, final_with_audio, run_dir).
    """
    silent_final = tmp_path / "silent.mp4"
    silent_final.write_bytes(b"\x00")
    final_with_audio = tmp_path / "final.mp4"
    final_with_audio.write_bytes(b"\x00")
    cfg = MagicMock()
    return (
        {"quote": "test quote", "audience": "entrepreneurs",
         "caption": "test caption", "row_number": 1, "hook": "test hook",
         "cta": "test cta", "bridge": ""},
        cfg, silent_final, final_with_audio,
    )


def _patch_caller_common(mocks: dict):
    """Apply the standard mock set used by caller-level tests."""
    mocks.update({
        "init_db": patch.object(__import__("pipeline"), "init_db"),
        "has_posted_today": patch.object(
            __import__("pipeline"), "has_posted_today", return_value=False),
        "get_valid_token": patch.object(
            __import__("pipeline"), "get_valid_token_with_fallback",
            return_value="tok"),
    })


def test_caller_invokes_new_orchestrator_with_paths(tmp_path):
    """Regression: caller invokes _run_pov_reel(quote_data_path, output_dir)."""
    import pipeline as pl
    quote_data, cfg, silent_final, final_with_audio = _setup_caller(tmp_path)

    with patch.object(pl, "_run_pov_reel", return_value=silent_final) as mock_render, \
         patch.object(pl, "_select_reel_music", return_value=None), \
         patch.object(pl, "_concat_vo_scenes", return_value=None), \
         patch.object(pl, "_mix_audio_track", return_value=final_with_audio), \
         patch.object(pl, "edge_tts_available", return_value=False), \
         patch.object(pl, "save_post", return_value=1), \
         patch.object(pl, "pick_best_hook", return_value={"hook_id": "h1"}), \
         patch.object(pl, "post_reel_to_instagram", return_value="ig_1"), \
         patch.object(pl, "mark_as_posted"), \
         patch.object(pl, "mark_posted"), \
         patch.object(pl, "Notifier"), \
         patch.object(pl, "save_log"):
        pl.run_pipeline(dry_run=True, reel=True, renderer="hyperframes")

    # Orchestrator was called with the NEW signature (Path, Path).
    assert mock_render.called
    assert "quote_data_path" in mock_render.call_args.kwargs
    assert "output_dir" in mock_render.call_args.kwargs
    assert isinstance(mock_render.call_args.kwargs["quote_data_path"], Path)
    assert isinstance(mock_render.call_args.kwargs["output_dir"], Path)


def test_caller_runs_audio_mix_when_vo_and_music_succeed(tmp_path):
    """Audio-mix stage runs with VO track + music when both succeed."""
    import pipeline as pl
    quote_data, cfg, silent_final, final_with_audio = _setup_caller(tmp_path)
    vo_track = tmp_path / "vo.mp3"
    vo_track.write_bytes(b"\x00")
    music = tmp_path / "music.mp3"
    music.write_bytes(b"\x00")

    with patch.object(pl, "_run_pov_reel", return_value=silent_final), \
         patch.object(pl, "_select_reel_music", return_value=music), \
         patch.object(pl, "_concat_vo_scenes", return_value=vo_track), \
         patch.object(pl, "_mix_audio_track", return_value=final_with_audio) as mock_mix, \
         patch.object(pl, "edge_tts_available", return_value=True), \
         patch.object(pl, "prepare_reel_voiceover_edge_tts",
                      return_value={"hook_voice": tmp_path / "h.mp3",
                                    "quote_voice": vo_track,
                                    "cta_voice": tmp_path / "c.mp3",
                                    "hook_words": [], "quote_words": [],
                                    "cta_words": []}), \
         patch.object(pl, "_bridge_for_vo", return_value=""), \
         patch.object(pl, "save_post", return_value=1), \
         patch.object(pl, "pick_best_hook", return_value={"hook_id": "h1"}), \
         patch.object(pl, "post_reel_to_instagram", return_value="ig_1"), \
         patch.object(pl, "mark_as_posted"), \
         patch.object(pl, "mark_posted"), \
         patch.object(pl, "Notifier"), \
         patch.object(pl, "save_log"):
        pl.run_pipeline(dry_run=False, reel=True, renderer="hyperframes")

    assert mock_mix.called
    kwargs = mock_mix.call_args.kwargs
    assert kwargs.get("vo_path") == vo_track
    assert kwargs.get("music_path") == music


def test_caller_skips_audio_mix_when_vo_fails(tmp_path):
    """Audio-mix skips VO when _concat_vo_scenes returns None (still mixes music)."""
    import pipeline as pl
    quote_data, cfg, silent_final, final_with_audio = _setup_caller(tmp_path)
    music = tmp_path / "music.mp3"
    music.write_bytes(b"\x00")

    with patch.object(pl, "_run_pov_reel", return_value=silent_final), \
         patch.object(pl, "_select_reel_music", return_value=music), \
         patch.object(pl, "_concat_vo_scenes", return_value=None), \
         patch.object(pl, "_mix_audio_track", return_value=final_with_audio) as mock_mix, \
         patch.object(pl, "edge_tts_available", return_value=False), \
         patch.object(pl, "save_post", return_value=1), \
         patch.object(pl, "pick_best_hook", return_value={"hook_id": "h1"}), \
         patch.object(pl, "post_reel_to_instagram", return_value="ig_1"), \
         patch.object(pl, "mark_as_posted"), \
         patch.object(pl, "mark_posted"), \
         patch.object(pl, "Notifier"), \
         patch.object(pl, "save_log"):
        pl.run_pipeline(dry_run=False, reel=True, renderer="hyperframes")

    # Audio-mix was called with vo_path=None but music_path present.
    assert mock_mix.called
    assert mock_mix.call_args.kwargs.get("vo_path") is None
    assert mock_mix.call_args.kwargs.get("music_path") == music


def test_caller_invokes_post_to_instagram_with_final_video(tmp_path):
    """Post-to-IG is invoked with the mixed-audio final video path."""
    import pipeline as pl
    quote_data, cfg, silent_final, final_with_audio = _setup_caller(tmp_path)

    with patch.object(pl, "_run_pov_reel", return_value=silent_final), \
         patch.object(pl, "_select_reel_music", return_value=None), \
         patch.object(pl, "_concat_vo_scenes", return_value=None), \
         patch.object(pl, "_mix_audio_track", return_value=final_with_audio), \
         patch.object(pl, "edge_tts_available", return_value=False), \
         patch.object(pl, "save_post", return_value=1), \
         patch.object(pl, "pick_best_hook", return_value={"hook_id": "h1"}), \
         patch.object(pl, "post_reel_to_instagram", return_value="ig_42") as mock_post, \
         patch.object(pl, "mark_as_posted"), \
         patch.object(pl, "mark_posted"), \
         patch.object(pl, "Notifier"), \
         patch.object(pl, "save_log") as mock_log:
        record = pl.run_pipeline(dry_run=False, reel=True, renderer="hyperframes")

    # post_to_instagram called with the audio-mixed final path.
    assert mock_post.called
    assert mock_post.call_args.kwargs.get("video_path") == final_with_audio
    # Returned record has the audio-mixed reel_path.
    assert "ig_42" in (record.get("post_id") or "")
    assert "final.mp4" in (record.get("reel_path") or "")
    mock_log.assert_called_once()


def test_caller_uses_elevenlabs_when_api_key_set(tmp_path):
    """Regression for I3: ElevenLabs is the primary VO path when its key is set.

    When ELEVENLABS_API_KEY is available, the caller invokes the ElevenLabs
    engine first. Edge-tts is the fallback only when ElevenLabs is unavailable
    or produced no usable VO.
    """
    import pipeline as pl
    cfg = MagicMock()
    cfg.ELEVENLABS_API_KEY = "el-key-test"
    silent_final = tmp_path / "silent.mp4"
    silent_final.write_bytes(b"\x00")
    final_with_audio = tmp_path / "final.mp4"
    final_with_audio.write_bytes(b"\x00")

    el_vo = {
        "hook_voice": tmp_path / "h.mp3",
        "quote_voice": tmp_path / "q.mp3",  # success marker
        "cta_voice": tmp_path / "c.mp3",
        "hook_words": [], "quote_words": [], "cta_words": [],
    }

    with patch.object(pl, "_run_pov_reel", return_value=silent_final), \
         patch.object(pl, "_select_reel_music", return_value=None), \
         patch.object(pl, "_concat_vo_scenes", return_value=None), \
         patch.object(pl, "_mix_audio_track", return_value=final_with_audio), \
         patch.object(pl, "elevenlabs_available", return_value=True) as mock_el_avail, \
         patch.object(pl, "prepare_reel_voiceover_elevenlabs",
                      return_value=el_vo) as mock_el_vo, \
         patch.object(pl, "edge_tts_available", return_value=False), \
         patch.object(pl, "save_post", return_value=1), \
         patch.object(pl, "pick_best_hook", return_value={"hook_id": "h1"}), \
         patch.object(pl, "post_reel_to_instagram", return_value="ig_99"), \
         patch.object(pl, "mark_as_posted"), \
         patch.object(pl, "mark_posted"), \
         patch.object(pl, "Notifier"), \
         patch.object(pl, "save_log"):
        pl._pov_reel_flow(
            cfg, {"quote": "q", "audience": "a", "caption": "c",
                  "row_number": 1, "hook": "h", "cta": "", "bridge": ""},
            "calm_stoic", 1, "ts", dry_run=True, manual=False,
            access_token="t",
        )

    # ElevenLabs availability check was consulted.
    assert mock_el_avail.called
    # ElevenLabs engine produced the VO (quote_voice present).
    assert mock_el_vo.called


def test_caller_falls_back_to_edge_tts_when_elevenlabs_unavailable(tmp_path):
    """When ELEVENLABS_API_KEY is missing, caller uses edge-tts."""
    import pipeline as pl
    cfg = MagicMock()
    cfg.ELEVENLABS_API_KEY = ""  # no key
    silent_final = tmp_path / "silent.mp4"
    silent_final.write_bytes(b"\x00")
    final_with_audio = tmp_path / "final.mp4"
    final_with_audio.write_bytes(b"\x00")

    with patch.object(pl, "_run_pov_reel", return_value=silent_final), \
         patch.object(pl, "_select_reel_music", return_value=None), \
         patch.object(pl, "_concat_vo_scenes", return_value=None), \
         patch.object(pl, "_mix_audio_track", return_value=final_with_audio), \
         patch.object(pl, "elevenlabs_available", return_value=False), \
         patch.object(pl, "edge_tts_available", return_value=True), \
         patch.object(pl, "prepare_reel_voiceover_edge_tts",
                      return_value={"hook_voice": None, "quote_voice": None,
                                    "cta_voice": None,
                                    "hook_words": [], "quote_words": [],
                                    "cta_words": []}) as mock_edge_vo, \
         patch.object(pl, "save_post", return_value=1), \
         patch.object(pl, "pick_best_hook", return_value={"hook_id": "h1"}), \
         patch.object(pl, "post_reel_to_instagram", return_value=None), \
         patch.object(pl, "mark_as_posted"), \
         patch.object(pl, "mark_posted"), \
         patch.object(pl, "Notifier"), \
         patch.object(pl, "save_log"):
        pl._pov_reel_flow(
            cfg, {"quote": "q", "audience": "a", "caption": "c",
                  "row_number": 1, "hook": "h", "cta": "", "bridge": ""},
            "calm_stoic", 1, "ts", dry_run=True, manual=False,
            access_token="t",
        )

    # Edge-tts is the fallback path.
    assert mock_edge_vo.called
