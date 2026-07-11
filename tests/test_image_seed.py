import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.visual import image_generator as ig


def test_resolve_seed_prefers_explicit():
    assert ig._resolve_seed(4242) == 4242


def test_resolve_seed_reads_env(monkeypatch):
    monkeypatch.setenv("FAL_SEED", "77")
    assert ig._resolve_seed(None) == 77


def test_resolve_seed_random_in_range(monkeypatch):
    monkeypatch.delenv("FAL_SEED", raising=False)
    s = ig._resolve_seed(None)
    assert 0 <= s <= 999999


def test_generate_background_returns_path_and_seed(monkeypatch, tmp_path):
    monkeypatch.setattr(ig, "enhance_prompt", lambda *a, **k: "p")
    monkeypatch.setattr(ig, "_generate_with_retry", lambda h, p, **k: {"images": [{"url": "http://x/y.jpg"}]})

    class _Resp:
        content = b"x" * 50
        def raise_for_status(self):
            pass

    monkeypatch.setattr(ig.requests, "get", lambda *a, **k: _Resp())
    path, seed = ig.generate_background("calm_stoic", "key", output_dir=str(tmp_path), quote="q", seed=4242)
    assert seed == 4242
    assert Path(path).exists()
