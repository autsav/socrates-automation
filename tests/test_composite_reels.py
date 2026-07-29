import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline import SCRIPTS_DIR, CompositeError, _composite_reels


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    base = tmp_path / "base.mp4"
    overlay = tmp_path / "overlay.mp4"
    final = tmp_path / "final.mp4"
    base.write_bytes(b"base")
    overlay.write_bytes(b"overlay")
    return base, overlay, final


def test_composite_reels_invokes_shell_script(tmp_path):
    base, overlay, final = _inputs(tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        final.write_bytes(b"final")  # shell script would have produced this
        result = _composite_reels(base, overlay, final)

    assert result == final
    assert mock_run.called

    cmd = mock_run.call_args.args[0]
    script = SCRIPTS_DIR / "composite_overlay.sh"
    # Absolute path — relative paths break when cwd differs in production.
    assert script.is_absolute()
    assert str(script) in cmd
    assert str(base) in cmd
    assert str(overlay) in cmd
    assert str(final) in cmd

    kwargs = mock_run.call_args.kwargs
    assert kwargs["timeout"] == 300
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def test_composite_reels_raises_on_nonzero_exit(tmp_path):
    base, overlay, final = _inputs(tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ffmpeg failed")
        with pytest.raises(CompositeError):
            _composite_reels(base, overlay, final)


def test_composite_reels_raises_on_missing_input(tmp_path):
    base = tmp_path / "base.mp4"  # not created
    overlay = tmp_path / "overlay.mp4"
    overlay.write_bytes(b"overlay")
    final = tmp_path / "final.mp4"

    with pytest.raises(CompositeError):
        _composite_reels(base, overlay, final)


def test_composite_reels_raises_on_timeout(tmp_path):
    base, overlay, final = _inputs(tmp_path)

    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=300),
    ):
        with pytest.raises(CompositeError):
            _composite_reels(base, overlay, final)


def test_composite_reels_raises_on_missing_cli(tmp_path):
    base, overlay, final = _inputs(tmp_path)

    with patch("subprocess.run", side_effect=FileNotFoundError("bash")):
        with pytest.raises(CompositeError):
            _composite_reels(base, overlay, final)
