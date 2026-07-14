import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


class _Cfg:
    FAL_API_KEY = "k"


def test_reel_background_returns_path_on_success(monkeypatch, tmp_path):
    img = tmp_path / "bg.jpg"
    img.write_bytes(b"x")
    monkeypatch.setattr("src.visual.image_generator.generate_background",
                        lambda **k: (img, 7))
    out = pipeline._reel_background(_Cfg(), {"quote": "Q", "trend_topic": "World Cup"},
                                    "dark_philosophical")
    assert out == img


def test_reel_background_none_on_failure(monkeypatch):
    def boom(**k):
        raise RuntimeError("fal down")
    monkeypatch.setattr("src.visual.image_generator.generate_background", boom)
    assert pipeline._reel_background(_Cfg(), {"quote": "Q"}, "dark_philosophical") is None
