"""Tests for pipeline._mix_audio_track() — Task 11 fix-R1 audio-mix helper.

The new render-only ``_run_pov_reel`` produces a silent final.mp4. The
caller-level reel-flow (``_pov_reel_flow``) then calls ``_mix_audio_track``
to overlay the VO track and mix in the Jamendo music bed via ffmpeg amix.

Composition rules (from pipeline.py):
  - Both VO and music → mix VO prominent, music low bed (volume 0.3)
  - VO only → mux VO, no music
  - Music only → mux music, no VO
  - Neither → copy base_video to output (silent reel)

Tests cover the four input combinations and the ffmpeg-failure path.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline import _mix_audio_track, _concat_vo_scenes


# ── _mix_audio_track ─────────────────────────────────────────────────────────


def _make_video(tmp_path: Path, name: str = "base.mp4") -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x00" * 64)
    return p


def _make_audio(tmp_path: Path, name: str = "vo.mp3") -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x00" * 64)
    return p


def _fake_ffmpeg_result(returncode: int = 0, stderr: str = ""):
    r = MagicMock()
    r.returncode = returncode
    r.stderr = stderr
    r.stdout = ""
    return r


def test_mix_both_vo_and_music(tmp_path):
    """Both inputs → ffmpeg amix with VO + music (music ducked to 0.3)."""
    base = _make_video(tmp_path)
    vo = _make_audio(tmp_path, "vo.mp3")
    music = _make_audio(tmp_path, "music.mp3")
    out = tmp_path / "out.mp4"

    with patch("pipeline.subprocess.run",
               return_value=_fake_ffmpeg_result(0)) as mock_run:
        result = _mix_audio_track(base, vo, music, out)

    assert result == out
    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    # Two -i inputs before the base -i → 4 -i flags total (VO, music, base).
    assert "-i" in cmd
    assert str(vo.resolve()) in cmd
    assert str(music.resolve()) in cmd
    assert str(base.resolve()) in cmd
    # Music ducking filter must be present.
    assert "volume=0.3" in " ".join(cmd)
    assert "amix" in " ".join(cmd)


def test_mix_vo_only(tmp_path):
    """VO only (no music) → mux VO onto silent base, no amix filter needed."""
    base = _make_video(tmp_path)
    vo = _make_audio(tmp_path, "vo.mp3")
    out = tmp_path / "out.mp4"

    with patch("pipeline.subprocess.run",
               return_value=_fake_ffmpeg_result(0)) as mock_run:
        result = _mix_audio_track(base, vo, None, out)

    assert result == out
    cmd = mock_run.call_args.args[0]
    assert str(vo.resolve()) in cmd
    assert str(base.resolve()) in cmd
    # No amix for single-input case.
    assert "amix" not in " ".join(cmd)


def test_mix_music_only(tmp_path):
    """Music only (no VO) → mux music onto silent base."""
    base = _make_video(tmp_path)
    music = _make_audio(tmp_path, "music.mp3")
    out = tmp_path / "out.mp4"

    with patch("pipeline.subprocess.run",
               return_value=_fake_ffmpeg_result(0)) as mock_run:
        result = _mix_audio_track(base, None, music, out)

    assert result == out
    cmd = mock_run.call_args.args[0]
    assert str(music.resolve()) in cmd
    assert str(base.resolve()) in cmd
    assert "amix" not in " ".join(cmd)


def test_mix_neither_returns_silent(tmp_path):
    """Neither VO nor music → copy base_video to output (silent reel)."""
    base = _make_video(tmp_path)
    out = tmp_path / "out.mp4"

    with patch("pipeline.subprocess.run") as mock_run, \
         patch("pipeline.shutil.copyfile") as mock_copy:
        result = _mix_audio_track(base, None, None, out)

    # No ffmpeg invocation when both inputs missing.
    assert not mock_run.called
    # Copy was attempted (silent fallback).
    assert mock_copy.called
    assert result == out


def test_mix_neither_input_paths_missing(tmp_path):
    """When input paths don't exist on disk → treated as missing → silent copy."""
    base = _make_video(tmp_path)
    vo = tmp_path / "ghost_vo.mp3"  # doesn't exist
    music = tmp_path / "ghost_music.mp3"  # doesn't exist
    out = tmp_path / "out.mp4"

    with patch("pipeline.subprocess.run") as mock_run:
        result = _mix_audio_track(base, vo, music, out)

    assert not mock_run.called  # treated as silent (paths missing)
    assert result == out


def test_mix_nonzero_exit_falls_back_to_silent(tmp_path):
    """ffmpeg nonzero exit → falls back to silent copy (never crashes reel)."""
    base = _make_video(tmp_path)
    vo = _make_audio(tmp_path, "vo.mp3")
    out = tmp_path / "out.mp4"

    with patch("pipeline.subprocess.run",
               return_value=_fake_ffmpeg_result(1, "boom")) as mock_run, \
         patch("pipeline.shutil.copyfile") as mock_copy:
        result = _mix_audio_track(base, vo, None, out)

    assert mock_run.called
    assert mock_copy.called  # silent fallback
    # The out path is still returned so posting continues.
    assert result == out


def test_mix_timeout_falls_back_to_silent(tmp_path):
    """ffmpeg timeout → silent fallback (never hangs a reel)."""
    base = _make_video(tmp_path)
    vo = _make_audio(tmp_path, "vo.mp3")
    out = tmp_path / "out.mp4"

    with patch("pipeline.subprocess.run",
               side_effect=__import__("subprocess").TimeoutExpired(
                   cmd="ffmpeg", timeout=300)) as mock_run, \
         patch("pipeline.shutil.copyfile"):
        result = _mix_audio_track(base, vo, None, out)

    assert mock_run.called
    # Silent fallback — never raise.
    assert result == out


def test_mix_returns_absolute_paths(tmp_path):
    """The returned path is absolute even when caller passes a relative path."""
    base = _make_video(tmp_path)
    vo = _make_audio(tmp_path, "vo.mp3")
    out = tmp_path / "out.mp4"

    with patch("pipeline.subprocess.run",
               return_value=_fake_ffmpeg_result(0)):
        result = _mix_audio_track(base, vo, None, out)

    assert Path(result).is_absolute()


# ── _concat_vo_scenes ────────────────────────────────────────────────────────


def test_concat_no_vo_returns_none(tmp_path):
    """Empty VO dict → None (caller falls back to silent amix)."""
    assert _concat_vo_scenes(None, tmp_path / "out.mp3") is None
    assert _concat_vo_scenes({}, tmp_path / "out.mp3") is None


def test_concat_single_scene(tmp_path):
    """One scene present → copy verbatim to output."""
    scene = _make_audio(tmp_path, "vo_scene.mp3")
    out = tmp_path / "vo.mp3"

    vo = {"hook_voice": scene}
    with patch("pipeline.shutil.copyfile") as mock_copy:
        result = _concat_vo_scenes(vo, out)

    assert mock_copy.called
    assert mock_copy.call_args.args == (scene, out)


def test_concat_multiple_scenes(tmp_path):
    """Two scenes → ffmpeg concat demuxer produces a single MP3."""
    scene_a = _make_audio(tmp_path, "a.mp3")
    scene_b = _make_audio(tmp_path, "b.mp3")
    out = tmp_path / "vo.mp3"

    vo = {"hook_voice": scene_a, "quote_voice": scene_b}

    # Side-effect runner: ffmpeg "wrote" the output by touching the file
    # (real ffmpeg would concat the MP3 streams — we just need the output to
    # exist for the helper's success path).
    def fake_runner(cmd, **kwargs):
        out.write_bytes(b"\x00" * 64)
        return _fake_ffmpeg_result(0)

    with patch("pipeline.subprocess.run", side_effect=fake_runner) as mock_run:
        result = _concat_vo_scenes(vo, out)

    assert mock_run.called
    # ffmpeg invoked with concat demuxer.
    cmd = mock_run.call_args.args[0]
    assert "concat" in cmd
    assert "-i" in cmd
    # Output path is the last positional arg.
    assert cmd[-1] == str(out)
    # Side-effect: list file written alongside (cleaned up in finally block).
    assert isinstance(result, Path)
    assert result == out


def test_concat_ffmpeg_failure_returns_none(tmp_path):
    """ffmpeg nonzero exit → None (never crashes caller)."""
    scene_a = _make_audio(tmp_path, "a.mp3")
    scene_b = _make_audio(tmp_path, "b.mp3")
    out = tmp_path / "vo.mp3"

    vo = {"hook_voice": scene_a, "quote_voice": scene_b}
    with patch("pipeline.subprocess.run",
               return_value=_fake_ffmpeg_result(1, "boom")):
        result = _concat_vo_scenes(vo, out)

    assert result is None
