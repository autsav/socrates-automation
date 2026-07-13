import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def _write(tmp_path, obj):
    p = tmp_path / "content.json"
    p.write_text(json.dumps(obj))
    return str(p)


def test_injected_content_full_override(tmp_path):
    p = _write(tmp_path, {
        "hook": "Stop scrolling. Start living.", "bridge": "But Socrates knew this.",
        "quote": "The unexamined life is not worth living.", "attribution": "— Socrates",
        "cta": "Save this for later.", "caption": "A caption.",
        "hashtags": ["#Stoicism", "#Socrates", "#Mindset"], "mood": "dark_philosophical",
        "audience": "stuck", "row_number": None})
    qd, mood = pipeline._injected_content(p, cfg=None)
    assert qd["quote"].startswith("The unexamined")
    assert qd["bridge"] == "But Socrates knew this."
    assert mood == "dark_philosophical"
    assert qd["row_number"] is None
    assert "#Stoicism" in qd["caption"]  # hashtags appended to caption


def test_injected_content_partial_falls_back(tmp_path):
    p = _write(tmp_path, {"quote": "Know thyself.", "audience": "lost", "mood": "calm_stoic"})
    qd, mood = pipeline._injected_content(p, cfg=None)
    # Missing hook/cta -> generators fill them; hashtags -> 3-5 generated.
    assert qd["hook"]  # non-empty
    assert qd["cta"]
    assert 3 <= len([t for t in qd["caption"].split() if t.startswith("#")]) <= 5
