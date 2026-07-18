"""T4: product generator — schema validation, branded render, graceful PDF skip."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import generate_product as gp


def _content(days=21):
    return {
        "title": "The Stoic Reset Journal",
        "subtitle": "Come back on track in three lines.",
        "intro": ["Willpower is a myth.", "This journal works differently."],
        "protocol": ["Name what you control.", "Drop what you don't.", "Do the next small thing."],
        "protocol_explainer": ["Run it when you slip.", "It takes thirty seconds."],
        "daily_pages": [
            {"quote": f"Quote {i}", "attribution": "— Epictetus",
             "prompts": ["What slipped?", "What was yours to control?", "What now?"],
             "micro_action": "Close one tab."}
            for i in range(days)
        ],
        "seven_day": [{"theme": f"Theme {i}", "instruction": "Do the thing."} for i in range(7)],
        "closing": ["Keep going."],
    }


def test_validate_accepts_good_content():
    ok, reason = gp.validate_content(_content())
    assert ok, reason


def test_validate_rejects_wrong_day_count():
    ok, reason = gp.validate_content(_content(days=20))
    assert not ok and "21" in reason


def test_validate_rejects_missing_prompts():
    c = _content()
    c["daily_pages"][3]["prompts"] = ["only one"]
    ok, reason = gp.validate_content(c)
    assert not ok and "3 prompts" in reason


def test_render_html_includes_brand_and_all_days():
    html_doc = gp.render_html(_content())
    assert "#d8b25c" in html_doc            # gold
    assert "#0e0e13" in html_doc            # ink
    assert "DAY 01 / 21" in html_doc and "DAY 21 / 21" in html_doc
    assert "The 7-Day Reset" in html_doc
    assert "&" not in "Quote 1" or True     # escaping covered below


def test_render_escapes_html():
    c = _content()
    c["daily_pages"][0]["quote"] = 'He said <b>"control"</b> & meant it'
    html_doc = gp.render_html(c)
    assert "&lt;b&gt;" in html_doc      # user content escaped (template's own <b> is fine)
    assert "&amp;" in html_doc


def test_html_to_pdf_graceful_without_chrome(tmp_path, monkeypatch):
    monkeypatch.setattr(gp, "_CHROME_CANDIDATES", ["/definitely/not/chrome"])
    monkeypatch.setattr(gp.shutil, "which", lambda _: None)
    src = tmp_path / "x.html"
    src.write_text("<html></html>")
    assert gp.html_to_pdf(src, tmp_path / "x.pdf") is False   # no raise
