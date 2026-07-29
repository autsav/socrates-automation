import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline import (
    HF_OVERLAY_CLI,
    HYPERFRAMES_ROOT,
    HfRenderError,
    _invoke_hyperframes,
    _render_overlay_html,
)


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text("{}")
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text("{}")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    return quote_data_path, word_timings_path, run_dir


def test_invoke_hyperframes_renders_html_and_invokes_cli(tmp_path):
    quote = "The obstacle is the way."
    quote_data = {
        "hook": "X",
        "quote": quote,
        "rpm_hooks": [
            {"at_sec": 1.0, "text": quote, "duration_sec": 2.0, "style": "pop"}
        ],
        "cta_copy": "",
    }
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text(json.dumps(quote_data))
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text(
        json.dumps({"scenes": {}, "total_duration_sec": 16.0})
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        (run_dir / "overlay.mp4").write_bytes(b"fake")

        result = _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)

    assert result == run_dir / "overlay.mp4"
    assert result.exists()

    # overlay.html MUST be inside hyperframes/output/ so render-overlay.ts's
    # static server (rooted at hyperframes/) can serve it without a 403.
    cmd = mock_run.call_args.args[0]
    rendered_html = Path(cmd[cmd.index("--input") + 1])
    assert rendered_html.is_relative_to(HYPERFRAMES_ROOT / "output")
    assert rendered_html.exists()
    assert quote in rendered_html.read_text()

    kwargs = mock_run.call_args.kwargs
    assert str(HF_OVERLAY_CLI) in cmd
    assert HF_OVERLAY_CLI.is_absolute()
    assert "--input" in cmd
    assert "--overlay-data" not in cmd
    assert str(run_dir / "overlay.mp4") in cmd
    assert kwargs["cwd"] == HYPERFRAMES_ROOT
    assert kwargs["timeout"] == 600
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def test_render_overlay_html_writes_inside_hf_root(tmp_path):
    quote = "Waste no more time arguing what a good man should be."
    quote_data_path = tmp_path / "quote_data.json"
    quote_data_path.write_text(
        json.dumps(
            {
                "quote": quote,
                "rpm_hooks": [
                    {"at_sec": 0.5, "text": quote, "duration_sec": 3.0, "style": "pop"}
                ],
                "cta_copy": "Follow for more.",
            }
        )
    )
    word_timings_path = tmp_path / "word_timings.json"
    word_timings_path.write_text(json.dumps({"scenes": {}, "total_duration_sec": 16.0}))
    run_dir = tmp_path / "run_hfroot"
    run_dir.mkdir()

    rendered = _render_overlay_html(
        quote_data_path, word_timings_path, 16.0, run_dir
    )

    assert str(rendered).startswith(str(HYPERFRAMES_ROOT / "output"))
    assert rendered.is_relative_to(HYPERFRAMES_ROOT / "output")
    assert rendered.exists()
    assert rendered.name == "overlay.html"
    assert quote in rendered.read_text()
    # NOT written to run_dir — that path is unreachable by the HF static server.
    assert not (run_dir / "overlay.html").exists()


def test_invoke_hyperframes_raises_on_timeout(tmp_path):
    quote_data_path, word_timings_path, run_dir = _inputs(tmp_path)

    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="npx", timeout=600),
    ):
        with pytest.raises(HfRenderError):
            _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)


def test_invoke_hyperframes_raises_on_missing_cli(tmp_path):
    quote_data_path, word_timings_path, run_dir = _inputs(tmp_path)

    with patch("subprocess.run", side_effect=FileNotFoundError("npx")):
        with pytest.raises(HfRenderError):
            _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)


def test_invoke_hyperframes_raises_on_nonzero_exit(tmp_path):
    quote_data_path, word_timings_path, run_dir = _inputs(tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="HF failed")
        with pytest.raises(HfRenderError):
            _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)


def test_invoke_hyperframes_raises_on_missing_output(tmp_path):
    quote_data_path, word_timings_path, run_dir = _inputs(tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        with pytest.raises(HfRenderError):
            _invoke_hyperframes(quote_data_path, word_timings_path, run_dir)
