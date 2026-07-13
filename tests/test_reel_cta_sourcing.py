import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def _run_and_capture_cta(monkeypatch, tmp_path, quote_data):
    """Drive the real _run_pov_reel (ffmpeg/Pillow fallback path, dry_run=True,
    manual=False) with heavy deps mocked, and capture the `cta` kwarg it hands
    to the renderer. dry_run=True + manual=False means Notifier/Instagram/
    mark_as_posted/mark_posted are never reached, so only save_post,
    pick_best_hook, generate_pov_reel and the log dir need stubbing."""
    captured = {}

    def fake_generate_pov_reel(quote, hook, cta, output_path, mood):
        captured["cta"] = cta
        return None  # reel_path=None short-circuits the rest cleanly

    monkeypatch.setattr(pipeline, "generate_pov_reel", fake_generate_pov_reel)
    monkeypatch.setattr(pipeline, "pick_best_hook", lambda audience, quote_text: {"hook_id": "h1"})
    monkeypatch.setattr(pipeline, "save_post", lambda **kwargs: 1)
    monkeypatch.setattr(pipeline, "LOG_DIR", tmp_path)

    pipeline._run_pov_reel(
        cfg=None,
        quote_data=quote_data,
        mood="calm_stoic",
        slot=1,
        timestamp="20260713_000000",
        dry_run=True,
        manual=False,
        access_token="token",
        use_remotion=False,
    )
    return captured["cta"]


def test_injected_cta_is_preferred_over_pick_cta(monkeypatch, tmp_path):
    """Custom CTA from injected --content JSON must not be silently discarded."""
    quote_data = {
        "row_number": None,
        "audience": "stuck",
        "quote": "Know thyself.",
        "hook": "Stop scrolling.",
        "cta": "Save this for later.",
        "caption": "A caption.",
    }
    cta = _run_and_capture_cta(monkeypatch, tmp_path, quote_data)
    assert cta == "Save this for later."


def test_null_row_number_does_not_crash_and_falls_back_to_variant(monkeypatch, tmp_path):
    """row_number=None (the --content injection case) must not raise TypeError
    from `None % len(...)`; it should fall back to a real CTA variant."""
    quote_data = {
        "row_number": None,
        "audience": "stuck",
        "quote": "Know thyself.",
        "hook": "Stop scrolling.",
        "caption": "A caption.",
        # no "cta" key -> must fall back to _pick_cta
    }
    cta = _run_and_capture_cta(monkeypatch, tmp_path, quote_data)
    assert cta in pipeline._CTA_VARIANTS
