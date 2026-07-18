import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


class _Cfg:
    FAL_API_KEY = "k"


def _no_pexels(monkeypatch):
    # Tests must not depend on the ambient PEXELS_API_KEY (or hit the network).
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)


def test_reel_background_returns_path_on_success(monkeypatch, tmp_path):
    _no_pexels(monkeypatch)
    img = tmp_path / "bg.jpg"
    img.write_bytes(b"x")
    monkeypatch.setattr("src.visual.image_generator.generate_background",
                        lambda **k: (img, 7))
    out = pipeline._reel_background(_Cfg(), {"quote": "Q", "trend_topic": "World Cup"},
                                    "dark_philosophical")
    assert out == img


def test_reel_background_none_on_failure(monkeypatch):
    _no_pexels(monkeypatch)

    def boom(**k):
        raise RuntimeError("fal down")
    monkeypatch.setattr("src.visual.image_generator.generate_background", boom)
    assert pipeline._reel_background(_Cfg(), {"quote": "Q"}, "dark_philosophical") is None


def test_stock_footage_wins_over_flux_when_key_present(monkeypatch, tmp_path):
    clip = tmp_path / "stock.mp4"
    clip.write_bytes(b"\x00" * 16)

    class _CfgPexels:
        FAL_API_KEY = "k"
        PEXELS_API_KEY = "px"

    monkeypatch.setattr("src.visual.stock_footage.pexels_available", lambda key: True)
    monkeypatch.setattr("src.visual.stock_footage.fetch_stock_background",
                        lambda **k: clip)
    flux_called = {"n": 0}
    monkeypatch.setattr("src.visual.image_generator.generate_background",
                        lambda **k: flux_called.__setitem__("n", flux_called["n"] + 1) or (tmp_path / "f.jpg", 1))
    out = pipeline._reel_background(_CfgPexels(), {"quote": "Q"}, "dark_philosophical")
    assert out == clip
    assert flux_called["n"] == 0   # FLUX never touched when real footage lands
