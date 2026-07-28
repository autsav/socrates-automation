"""Tests for QuoteData overlay fields (HyperFrames integration).

Extends studio QuoteData with three new fields for kinetic text + RPM
retention hooks + CTA card overlays needed by HyperFrames:
  - rpm_hooks: list[RpmHook]  (default empty list)
  - cta_copy: str             (default empty string)
  - cta_url: str | None       (default None)

Plus the new RpmHook dataclass: {at_sec, text, duration_sec, style}.
"""
from studio.types import QuoteData, RpmHook


def test_quote_data_has_rpm_hooks_field():
    """rpm_hooks + cta_copy default to empty values."""
    qd = QuoteData(
        hook="", bridge=None, quote="", attribution="", caption="",
        hashtags=[], mood="", audience="", row_number=1, cta="",
        rpm_hooks=[], cta_copy="", cta_url="",
    )
    assert qd.rpm_hooks == []
    assert qd.cta_copy == ""


def test_quote_data_cta_url_optional():
    """cta_url defaults to None when not supplied."""
    qd = QuoteData(
        hook="", bridge=None, quote="", attribution="", caption="",
        hashtags=[], mood="", audience="", row_number=1, cta="",
        rpm_hooks=[], cta_copy="", cta_url=None,
    )
    assert qd.cta_url is None


def test_rpm_hook_schema():
    """RpmHook carries at_sec / text / duration_sec / style."""
    h = RpmHook(at_sec=2.5, text="Did you know?", duration_sec=1.5, style="pop")
    assert h.at_sec == 2.5
    assert h.text == "Did you know?"
    assert h.duration_sec == 1.5
    assert h.style == "pop"


def test_quote_data_defaults_when_overlay_fields_omitted():
    """Existing callers that don't pass new fields keep working (defaults apply)."""
    qd = QuoteData(
        hook="x", bridge=None, quote="y", attribution="z", caption="c",
        hashtags=["a"], mood="stark", audience="doomscrollers",
        row_number=1, cta="go",
    )
    assert qd.rpm_hooks == []
    assert qd.cta_copy == ""
    assert qd.cta_url is None


def test_quote_data_round_trip_with_overlays():
    """to_dict/from_dict preserves rpm_hooks + cta_copy + cta_url."""
    raw = {
        "hook": "h", "bridge": None, "quote": "q", "cta": "c1",
        "caption": "cap", "hashtags": ["#x", "#y", "#z"],
        "mood": "stark", "attribution": "Seneca",
        "audience": "doomscrollers", "row_number": 1,
        "music_track_id": None, "flux_prompt": None,
        "rpm_hooks": [{"at_sec": 1.0, "text": "?", "duration_sec": 0.5, "style": "pop"}],
        "cta_copy": "Tap the link", "cta_url": "https://example.com",
    }
    qd = QuoteData.from_dict(raw)
    assert qd.to_dict() == raw