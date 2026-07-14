import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video import remotion_reel


def _bridge(tmp_path):
    return tmp_path / "public" / "reel-data.json"


def test_background_included_when_given(tmp_path):
    bg = tmp_path / "bg.jpg"
    bg.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    out = remotion_reel.write_bridge_file(
        hook="h", quote="q", attribution="a", cta="c", mood="dark_philosophical",
        duration=8.0, fps=30, bridge_path=_bridge(tmp_path), background=bg)
    payload = json.loads(Path(out).read_text())
    assert payload["background"] == "bg.jpg"
    assert (Path(out).parent / "bg.jpg").exists()


def test_background_omitted_when_none(tmp_path):
    out = remotion_reel.write_bridge_file(
        hook="h", quote="q", attribution="a", cta="c", mood="dark_philosophical",
        duration=8.0, fps=30, bridge_path=_bridge(tmp_path), background=None)
    payload = json.loads(Path(out).read_text())
    assert "background" not in payload
