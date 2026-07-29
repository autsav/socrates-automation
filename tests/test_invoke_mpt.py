"""Tests for pipeline._invoke_mpt() — Task 8 (HyperFrames MPT integration).

These tests pin down the subprocess contract with the MPT CLI:
- MPT_ROOT is the cwd
- cli.py is the entry point (not main.py / -m mpt.main)
- A predictable set of flags is passed
- stdout JSON is parsed → base_video is copied into run_dir
- SRT is adapted via src.mpt_adapter.srt_to_word_timings
- Failures raise MptRenderError (nonzero exit, malformed stdout, missing file)
"""
from pathlib import Path
import json
import pytest
from unittest.mock import patch, MagicMock

from pipeline import _invoke_mpt, MptRenderError, MPT_ROOT


@pytest.fixture
def fake_mpt_outputs(tmp_path):
    """Simulate MPT's storage/tasks/<task-id>/ outputs."""
    task_dir = tmp_path / "mpt" / "storage" / "tasks" / "abc-uuid"
    task_dir.mkdir(parents=True)
    (task_dir / "1.mp4").write_bytes(b"fake-mp4")
    srt = (
        "1\n00:00:00,000 --> 00:00:01,000\nhello world\n\n"
        "2\n00:00:01,500 --> 00:00:02,500\nfoo bar\n"
    )
    (task_dir / "subtitle.srt").write_text(srt)
    return task_dir


def test_invoke_mpt_returns_paths(tmp_path, fake_mpt_outputs):
    quote_data = tmp_path / "quote_data.json"
    quote_data.write_text("{}")
    run_dir = tmp_path / "run"

    stdout = json.dumps({
        "task_id": "abc-uuid",
        "result": {"videos": [str(fake_mpt_outputs / "1.mp4")],
                   "subtitle": str(fake_mpt_outputs / "subtitle.srt")},
    })

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        result = _invoke_mpt(quote_data, run_dir)

    assert result["base_video"] == run_dir / "base.mp4"
    assert result["base_video"].exists()
    assert result["word_timings"] == run_dir / "word_timings.json"
    assert result["word_timings"].exists()


def test_invoke_mpt_uses_correct_cli_contract(tmp_path, fake_mpt_outputs):
    quote_data = tmp_path / "quote_data.json"
    quote_data.write_text("{}")
    run_dir = tmp_path / "run"

    stdout = json.dumps({
        "task_id": "abc-uuid",
        "result": {"videos": [str(fake_mpt_outputs / "1.mp4")],
                   "subtitle": str(fake_mpt_outputs / "subtitle.srt")},
    })

    with patch("subprocess.run") as mock_run, \
         patch("pipeline.uuid.uuid4", return_value="fixed-uuid"):
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        _invoke_mpt(quote_data, run_dir)

    call = mock_run.call_args
    cmd = call.args[0]
    kwargs = call.kwargs
    # Must use cli.py (not main.py / -m mpt.main)
    assert cmd[1] == "cli.py"
    assert "--stop-at" in cmd and "video" in cmd
    assert "--no-subtitle-enabled" not in cmd  # WE want subtitles for SRT
    # actually we DO want subtitles for word timings → assert below
    assert "--voice-name" in cmd and "no-voice" in cmd
    assert "--bgm-type" in cmd and "none" in cmd
    assert "--video-aspect" in cmd and "9:16" in cmd
    # cwd MUST be MPT_ROOT
    assert kwargs["cwd"] == MPT_ROOT


def test_invoke_mpt_raises_on_nonzero_exit(tmp_path):
    quote_data = tmp_path / "quote_data.json"
    quote_data.write_text("{}")
    run_dir = tmp_path / "run"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="MPT failed")
        with pytest.raises(MptRenderError):
            _invoke_mpt(quote_data, run_dir)


def test_invoke_mpt_raises_on_missing_base_video(tmp_path):
    quote_data = tmp_path / "quote_data.json"
    quote_data.write_text("{}")
    run_dir = tmp_path / "run"

    # stdout says success but video path doesn't exist
    bogus_path = tmp_path / "does-not-exist.mp4"
    stdout = json.dumps({
        "task_id": "abc",
        "result": {"videos": [str(bogus_path)], "subtitle": str(bogus_path) + ".srt"},
    })

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        with pytest.raises(MptRenderError):
            _invoke_mpt(quote_data, run_dir)


def test_invoke_mpt_raises_on_missing_quote_data(tmp_path):
    missing_quote_data = tmp_path / "missing_quote_data.json"
    run_dir = tmp_path / "run"

    with pytest.raises(MptRenderError, match=str(missing_quote_data)):
        _invoke_mpt(missing_quote_data, run_dir)
