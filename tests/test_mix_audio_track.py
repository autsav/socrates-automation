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


def _ffmpeg_runner_success(out_path: Path, returncode: int = 0):
    """Return a fake runner that simulates ffmpeg writing a non-empty output."""
    def runner(cmd, **kwargs):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Real ffmpeg writes 100s of KB; tiny non-zero bytes are enough to
        # satisfy the helper's "exists() and stat().st_size > 0" guard.
        out_path.write_bytes(b"\x00" * 1024)
        return _fake_ffmpeg_result(returncode)
    return runner


def test_mix_both_vo_and_music(tmp_path):
    """Both inputs → ffmpeg amix with VO + music (music ducked to 0.3)."""
    base = _make_video(tmp_path)
    vo = _make_audio(tmp_path, "vo.mp3")
    music = _make_audio(tmp_path, "music.mp3")
    out = tmp_path / "out.mp4"

    fake_runner = _ffmpeg_runner_success(out)
    with patch("pipeline.subprocess.run", side_effect=fake_runner) as mock_run, \
         patch("pipeline.shutil.copyfile") as mock_copy:
        result = _mix_audio_track(base, vo, music, out)

    assert result == out
    assert mock_run.called
    # SUCCESS path: copyfile MUST NOT be called — that's the silent fallback.
    assert not mock_copy.called, "silent-copy fallback ran despite ffmpeg success"
    # Output is the ffmpeg-written file, not the silent copy.
    assert out.exists() and out.stat().st_size > 0

    cmd = mock_run.call_args.args[0]
    # Base is input 0 (regression: bug C1 was audio-first → -map 0:v hit audio).
    base_pos = cmd.index(str(base.resolve()))
    assert cmd[base_pos - 1] == "-i"
    # -map 0:v must point to base video, never to audio inputs.
    map_idx = cmd.index("-map")
    assert cmd[map_idx + 1] == "0:v", "video-map must reference base video (index 0)"
    # Both audio inputs present, with amix filter.
    assert "-i" in cmd
    assert str(vo.resolve()) in cmd
    assert str(music.resolve()) in cmd
    # Music ducking filter must be present.
    assert "volume=0.3" in " ".join(cmd)
    assert "amix" in " ".join(cmd)


def test_mix_vo_only(tmp_path):
    """VO only (no music) → mux VO onto silent base, no amix filter needed."""
    base = _make_video(tmp_path)
    vo = _make_audio(tmp_path, "vo.mp3")
    out = tmp_path / "out.mp4"

    fake_runner = _ffmpeg_runner_success(out)
    with patch("pipeline.subprocess.run", side_effect=fake_runner) as mock_run, \
         patch("pipeline.shutil.copyfile") as mock_copy:
        result = _mix_audio_track(base, vo, None, out)

    assert result == out
    # SUCCESS path: copyfile MUST NOT be called.
    assert not mock_copy.called, "silent-copy fallback ran despite ffmpeg success"
    assert out.exists() and out.stat().st_size > 0

    cmd = mock_run.call_args.args[0]
    # Base is input 0; VO is input 1.
    base_pos = cmd.index(str(base.resolve()))
    assert cmd[base_pos - 1] == "-i"
    map_idx = cmd.index("-map")
    assert cmd[map_idx + 1] == "0:v", "video-map must reference base video (index 0)"
    # VO audio is at input 1 → "-map 1:a".
    assert "1:a" in cmd
    assert str(vo.resolve()) in cmd
    assert str(base.resolve()) in cmd
    # No amix for single-input case.
    assert "amix" not in " ".join(cmd)


def test_mix_music_only(tmp_path):
    """Music only (no VO) → mux music onto silent base."""
    base = _make_video(tmp_path)
    music = _make_audio(tmp_path, "music.mp3")
    out = tmp_path / "out.mp4"

    fake_runner = _ffmpeg_runner_success(out)
    with patch("pipeline.subprocess.run", side_effect=fake_runner) as mock_run, \
         patch("pipeline.shutil.copyfile") as mock_copy:
        result = _mix_audio_track(base, None, music, out)

    assert result == out
    # SUCCESS path: copyfile MUST NOT be called.
    assert not mock_copy.called, "silent-copy fallback ran despite ffmpeg success"
    assert out.exists() and out.stat().st_size > 0

    cmd = mock_run.call_args.args[0]
    base_pos = cmd.index(str(base.resolve()))
    assert cmd[base_pos - 1] == "-i"
    map_idx = cmd.index("-map")
    assert cmd[map_idx + 1] == "0:v", "video-map must reference base video (index 0)"
    # Music audio is at input 1 → "-map 1:a".
    assert "1:a" in cmd
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

    fake_runner = _ffmpeg_runner_success(out)
    with patch("pipeline.subprocess.run", side_effect=fake_runner), \
         patch("pipeline.shutil.copyfile") as mock_copy:
        result = _mix_audio_track(base, vo, None, out)

    assert Path(result).is_absolute()
    assert not mock_copy.called, "silent-copy fallback ran despite ffmpeg success"


def test_mix_video_map_always_points_to_base(tmp_path):
    """Regression for C1: -map 0:v must always point at the base video,
    regardless of which optional audio inputs are present.

    The bug was audio-first ordering + audio-only -map 0:v → exit 1 →
    silent-copy fallback (which the previous test suite silently asserted).
    """
    base = _make_video(tmp_path)

    # All three combinations exercise the same invariant: -map 0:v must
    # be the first -map (i.e. base video stream), not an audio input.
    for vo_p, music_p in [
        (None, None),  # silent — never reaches ffmpeg
    ]:
        # silent path: no ffmpeg call, can't check -map (already covered
        # by test_mix_neither_returns_silent).
        pass

    # Case A: both VO and music
    vo = _make_audio(tmp_path, "vo.mp3")
    music = _make_audio(tmp_path, "music.mp3")
    out_a = tmp_path / "out_a.mp4"
    fake_runner_a = _ffmpeg_runner_success(out_a)
    with patch("pipeline.subprocess.run", side_effect=fake_runner_a) as mock_a, \
         patch("pipeline.shutil.copyfile") as mock_copy_a:
        _mix_audio_track(base, vo, music, out_a)
    assert not mock_copy_a.called
    cmd_a = mock_a.call_args.args[0]
    # -map 0:v must be the very first -map (base video).
    assert cmd_a[cmd_a.index("-map") + 1] == "0:v"

    # Case B: VO only
    out_b = tmp_path / "out_b.mp4"
    fake_runner_b = _ffmpeg_runner_success(out_b)
    with patch("pipeline.subprocess.run", side_effect=fake_runner_b) as mock_b, \
         patch("pipeline.shutil.copyfile") as mock_copy_b:
        _mix_audio_track(base, vo, None, out_b)
    assert not mock_copy_b.called
    cmd_b = mock_b.call_args.args[0]
    assert cmd_b[cmd_b.index("-map") + 1] == "0:v"

    # Case C: music only
    out_c = tmp_path / "out_c.mp4"
    fake_runner_c = _ffmpeg_runner_success(out_c)
    with patch("pipeline.subprocess.run", side_effect=fake_runner_c) as mock_c, \
         patch("pipeline.shutil.copyfile") as mock_copy_c:
        _mix_audio_track(base, None, music, out_c)
    assert not mock_copy_c.called
    cmd_c = mock_c.call_args.args[0]
    assert cmd_c[cmd_c.index("-map") + 1] == "0:v"


def test_mix_no_silent_copy_on_success(tmp_path):
    """Direct regression for C2: success path must not invoke shutil.copyfile.

    Previous tests asserted `result == out` without checking that out was
    ffmpeg-written vs silent-copied. With copyfile mocked, ensure it
    stayed uncalled when ffmpeg returned 0 + wrote a non-empty file.
    """
    base = _make_video(tmp_path)
    vo = _make_audio(tmp_path, "vo.mp3")
    out = tmp_path / "out.mp4"

    fake_runner = _ffmpeg_runner_success(out)
    with patch("pipeline.subprocess.run", side_effect=fake_runner), \
         patch("pipeline.shutil.copyfile") as mock_copy:
        result = _mix_audio_track(base, vo, None, out)

    assert result == out
    assert out.stat().st_size > 0
    # The whole point of the regression: silent copy must NOT have run.
    assert not mock_copy.called


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


def _capture_list_file_writes(tmp_path, out):
    """Patch ``io.open`` so writes to the *.list.txt file are captured.

    Returns (captured_lines, fake_runner) ready to use in a ``with`` block.
    ``Path.open`` does NOT route through ``builtins.open`` (it uses ``io.open``
    directly), so we patch at the io level.
    """
    import io as _io
    real_open = _io.open
    written_lines: list[str] = []

    def fake_open(path, *args, **kwargs):
        f = real_open(path, *args, **kwargs)
        if str(path).endswith(".list.txt"):
            original_write = f.write

            def capturing_write(s):
                written_lines.append(s)
                return original_write(s)

            f.write = capturing_write
        return f

    def fake_runner(cmd, **kwargs):
        out.write_bytes(b"\x00" * 64)
        return _fake_ffmpeg_result(0)

    return written_lines, fake_runner, fake_open


def test_concat_scene_order_hook_bridge_quote_cta(tmp_path):
    """Regression for I1: scene order in concat list file must match
    the documented arc (Hook → [Bridge] → Quote → CTA).

    The R1 implementation ordered bridge first; this reordered to hook
    first. Verify by inspecting the written list file.
    """
    hook = _make_audio(tmp_path, "hook.mp3")
    bridge = _make_audio(tmp_path, "bridge.mp3")
    quote = _make_audio(tmp_path, "quote.mp3")
    cta = _make_audio(tmp_path, "cta.mp3")
    out = tmp_path / "vo.mp3"

    vo = {
        "hook_voice": hook,
        "bridge_voice": bridge,
        "quote_voice": quote,
        "cta_voice": cta,
    }

    written_lines, fake_runner, fake_open = _capture_list_file_writes(
        tmp_path, out)

    with patch("pipeline.subprocess.run", side_effect=fake_runner), \
         patch("io.open", side_effect=fake_open):
        result = _concat_vo_scenes(vo, out)

    assert result == out
    # The list file should mention paths in scene order:
    # hook, bridge, quote, cta (NOT bridge, hook, quote, cta).
    hook_pos = next(i for i, line in enumerate(written_lines) if "hook.mp3" in line)
    bridge_pos = next(i for i, line in enumerate(written_lines) if "bridge.mp3" in line)
    quote_pos = next(i for i, line in enumerate(written_lines) if "quote.mp3" in line)
    cta_pos = next(i for i, line in enumerate(written_lines) if "cta.mp3" in line)

    assert hook_pos < bridge_pos < quote_pos < cta_pos, (
        f"scene order wrong: hook={hook_pos} bridge={bridge_pos} "
        f"quote={quote_pos} cta={cta_pos}")


def test_concat_partial_scenes_keeps_arc(tmp_path):
    """Without bridge scene, the order is hook → quote → cta (bridge gap ok)."""
    hook = _make_audio(tmp_path, "hook.mp3")
    quote = _make_audio(tmp_path, "quote.mp3")
    cta = _make_audio(tmp_path, "cta.mp3")
    out = tmp_path / "vo.mp3"

    vo = {"hook_voice": hook, "quote_voice": quote, "cta_voice": cta}

    written_lines, fake_runner, fake_open = _capture_list_file_writes(
        tmp_path, out)

    with patch("pipeline.subprocess.run", side_effect=fake_runner), \
         patch("io.open", side_effect=fake_open):
        result = _concat_vo_scenes(vo, out)

    assert result == out
    hook_pos = next(i for i, line in enumerate(written_lines) if "hook.mp3" in line)
    quote_pos = next(i for i, line in enumerate(written_lines) if "quote.mp3" in line)
    cta_pos = next(i for i, line in enumerate(written_lines) if "cta.mp3" in line)
    assert hook_pos < quote_pos < cta_pos
