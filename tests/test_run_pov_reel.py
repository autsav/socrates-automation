"""Tests for pipeline._run_pov_reel() — Task 11 orchestrator.

The orchestrator chains MPT → HyperFrames → ffmpeg composite into a single
Path return value. Hard cutover (per Q1): NO in-app fallback reel. Exceptions
(MptRenderError, HfRenderError, CompositeError) propagate.

The ThreadPoolExecutor scaffolding is preserved as future-proofing, but HF
waits on MPT's word_timings so wall-time is sequential in practice.
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline import (
    HfRenderError,
    MptRenderError,
    _run_pov_reel,
)


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