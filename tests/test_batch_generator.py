import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch

import openpyxl
import pytest

from src.video.batch_generator import read_ready_quotes, generate_batch
from src.core.excel_reader import AUDIENCE_TO_MOOD


def _make_quotes_xlsx(path: Path, rows: list[dict]) -> Path:
    """rows: list of dicts with keys quote, audience, status, posted (all optional)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Quotes"
    ws.append(["#", "Quote", "Audience", "Caption", "Caption B", "F", "Status", "Posted Date", "Post ID"])
    for i, row in enumerate(rows, start=1):
        ws.append([
            i,
            row.get("quote", ""),
            row.get("audience", "stuck"),
            row.get("caption", "caption text"),
            "",
            "",
            row.get("status", ""),
            row.get("posted", ""),
            "",
        ])
    wb.save(path)
    return path


def test_read_ready_quotes_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_ready_quotes(tmp_path / "does_not_exist.xlsx")


def test_read_ready_quotes_filters_skip_and_posted(tmp_path):
    path = _make_quotes_xlsx(tmp_path / "quotes.xlsx", [
        {"quote": "Know thyself.", "audience": "stuck"},
        {"quote": "Skipped one.", "status": "skip"},
        {"quote": "Already posted.", "posted": "2026-01-01"},
        {"quote": "Memento mori.", "audience": "doomscroller"},
        {"quote": "", "audience": "lost"},  # blank quote, should be excluded
    ])

    result = read_ready_quotes(path, limit=10)

    quotes = [r["quote"] for r in result]
    assert "Know thyself." in quotes
    assert "Memento mori." in quotes
    assert "Skipped one." not in quotes
    assert "Already posted." not in quotes
    assert len(result) == 2
    assert all("row_number" in r and "audience" in r for r in result)


def test_read_ready_quotes_respects_limit(tmp_path):
    rows = [{"quote": f"Quote {i}", "audience": "stuck"} for i in range(5)]
    path = _make_quotes_xlsx(tmp_path / "quotes.xlsx", rows)

    result = read_ready_quotes(path, limit=3)
    assert len(result) == 3


def test_generate_batch_no_ready_quotes_returns_empty(tmp_path):
    path = _make_quotes_xlsx(tmp_path / "quotes.xlsx", [
        {"quote": "Already posted.", "posted": "2026-01-01"},
    ])
    result = generate_batch(excel_path=path, output_dir=tmp_path / "out", count=30)
    assert result == []


def test_generate_batch_calls_generate_pov_reels(tmp_path):
    path = _make_quotes_xlsx(tmp_path / "quotes.xlsx", [
        {"quote": "Know thyself.", "audience": "stuck"},
        {"quote": "Memento mori.", "audience": "doomscroller"},
    ])
    output_dir = tmp_path / "pov_reels"
    fake_paths = [output_dir / "a.mp4", output_dir / "b.mp4"]

    with patch("src.video.batch_generator.generate_pov_reels", return_value=fake_paths) as mock_gen:
        result = generate_batch(excel_path=path, output_dir=output_dir, count=30)

    assert result == fake_paths
    mock_gen.assert_called_once()
    _, kwargs = mock_gen.call_args
    assert kwargs["mood_map"] == AUDIENCE_TO_MOOD
    called_quotes = mock_gen.call_args[0][0]
    assert len(called_quotes) == 2
