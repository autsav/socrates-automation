from pathlib import Path
import pytest
import json
from unittest.mock import patch, MagicMock
from pipeline import _invoke_hyperframes, HfRenderError


def test_invoke_hyperframes_writes_overlay_input_and_renders(tmp_path):
    quote_data = {"hook": "X", "quote": "Y", "rpm_hooks": [], "cta_copy": ""}
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text(json.dumps(quote_data))
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text(json.dumps({"scenes": {}, "total_duration_sec": 16.0}))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        (run_dir / "overlay.mp4").write_bytes(b"fake")

        result = _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)

    assert result == run_dir / "overlay.mp4"
    assert (run_dir / "overlay_input.json").exists()
    overlay_input = json.loads((run_dir / "overlay_input.json").read_text())
    assert overlay_input["quote_data"] == str(quote_data_path)
    assert overlay_input["word_timings"] == str(word_timings_path)
    assert overlay_input["base_duration_sec"] == 16.0
    assert overlay_input["overlay_only"] is True


def test_invoke_hyperframes_raises_on_nonzero_exit(tmp_path):
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text("{}")
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="HF failed")
        with pytest.raises(HfRenderError):
            _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)


def test_invoke_hyperframes_raises_on_missing_output(tmp_path):
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text("{}")
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        # overlay.mp4 NOT created
        with pytest.raises(HfRenderError):
            _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)
