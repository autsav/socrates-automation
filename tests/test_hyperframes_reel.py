"""Tests for the HyperFrames Python bridge.

Covers:
- build_reel_data returns the canonical dict shape
- _render_html produces valid HTML with inlined reel data
- _copy_assets stages media files correctly
- generate_hyperframes_reel falls back gracefully
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.video.reel_data import build_reel_data
from src.video.hyperframes_reel import _copy_assets, _render_html


def test_build_reel_data_returns_canonical_shape():
    data = build_reel_data(
        hook="This changed me.",
        quote="Know thyself.",
        attribution="— Socrates",
        cta="Save this.",
        mood="dark_philosophical",
        duration=10.5,
        fps=30,
    )
    assert data["hook"] == "This changed me."
    assert data["quote"] == "Know thyself."
    assert data["mood"] == "dark_philosophical"
    assert data["fps"] == 30
    assert "sceneFrames" not in data  # computed downstream, not in canonical dict
    assert "voices" in data
    assert "voiceDurations" in data
    assert "wordTimes" in data


def test_build_reel_data_normalizes_unknown_mood():
    data = build_reel_data(quote="test", mood="invalid_mood")
    assert data["mood"] == "dark_philosophical"


def test_render_html_produces_valid_structure(tmp_path):
    payload = {
        "hook": "Hook text",
        "quote": "Quote text",
        "attribution": "— Author",
        "cta": "CTA text",
        "mood": "dark_philosophical",
        "duration": 10.5,
        "fps": 30,
        "animSeed": 0,
        "sceneFrames": {"total": 10.5, "hook": 2.45, "bridge": 0, "quote": 4.2, "cta": 1.8},
        "voices": {},
        "wordTimes": {},
    }
    html_path = tmp_path / "test.html"
    _render_html(payload, html_path)
    html = html_path.read_text()
    assert 'data-mood="dark_philosophical"' in html
    assert "Hook text" in html
    assert "Quote text" in html
    assert "CTA text" in html
    # Inlined JSON
    assert '<script type="application/json" id="reel-data">' in html
    assert "Hook text" in html


def test_render_html_includes_bridge_when_present(tmp_path):
    payload = {
        "hook": "H",
        "quote": "Q",
        "attribution": "— A",
        "cta": "C",
        "bridge": "Bridge text",
        "mood": "dark_philosophical",
        "duration": 10.5,
        "fps": 30,
        "sceneFrames": {"total": 10.5, "hook": 2.0, "bridge": 2.5, "quote": 4.0, "cta": 1.8},
        "voices": {},
        "wordTimes": {},
    }
    html_path = tmp_path / "test.html"
    _render_html(payload, html_path)
    html = html_path.read_text()
    assert "Bridge text" in html


def test_copy_assets_relocates_paths(tmp_path):
    src = tmp_path / "vo-hook.mp3"
    src.write_bytes(b"\x00")
    payload = {
        "voices": {"hook": str(src)},
        "music": None,
    }
    dest = tmp_path / "assets"
    updated = _copy_assets(payload, dest)
    assert updated["voices"]["hook"] == "assets/vo-hook.mp3"
    assert (dest / "vo-hook.mp3").exists()


def test_generate_hyperframes_reel_returns_none_when_not_available():
    with patch("src.video.hyperframes_reel._hyperframes_available", return_value=False):
        from src.video.hyperframes_reel import generate_hyperframes_reel
        result = generate_hyperframes_reel(
            hook="H", quote="Q", cta="C", mood="dark_philosophical",
        )
    assert result is None
