import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video import remotion_reel


def test_defaultprops_and_payload_agree_on_background_key(tmp_path):
    # The Remotion component reads props.background; the payload key must be
    # exactly "background".
    bg = tmp_path / "bg.jpg"
    bg.write_bytes(b"\xff\xd8\xffx")
    out = remotion_reel.write_bridge_file(
        hook="h", quote="q", attribution="a", cta="c", mood="dark_philosophical",
        duration=8.0, fps=30, bridge_path=tmp_path / "public" / "reel-data.json",
        background=bg)
    payload = json.loads(Path(out).read_text())
    assert payload.get("background") == "bg.jpg"
