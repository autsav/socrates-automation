"""Bridge-file payload: multi-clip backgrounds + silence drop, back-compatible."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.remotion_reel import write_bridge_file


def _write(tmp_path, **kw):
    p = tmp_path / "reel-data.json"
    write_bridge_file(hook="h", quote="q", attribution="— S", cta="c",
                      mood="dark_philosophical", duration=10, fps=30,
                      bridge_path=p, **kw)
    return json.loads(p.read_text())


def test_single_clip_payload_unchanged(tmp_path):
    clip = tmp_path / "one.mp4"; clip.write_bytes(b"x")
    d = _write(tmp_path, background=clip)
    assert "backgrounds" not in d and d["background"] == "bg.mp4"
    assert "silenceDropSec" not in d


def test_multi_clip_payload(tmp_path):
    clips = []
    for i in range(3):
        c = tmp_path / f"c{i}.mp4"; c.write_bytes(b"x"); clips.append(c)
    d = _write(tmp_path, backgrounds=clips, silence_drop_sec=0.8)
    assert len(d["backgrounds"]) == 3
    assert "background" not in d
    assert len(d["backgroundDurationsSec"]) == 3
    assert d["silenceDropSec"] == 0.8


def test_sfx_set_includes_riser_and_sub_impact(tmp_path):
    d = _write(tmp_path)
    if d.get("sfx"):                      # ffmpeg present in env
        assert "riser" in d["sfx"] and "sub_impact" in d["sfx"]
