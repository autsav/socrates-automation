"""Bridge payload carries word classes + the deterministic anim seed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.remotion_reel import write_bridge_file


def test_wordtimes_classified_and_seed_written(tmp_path):
    p = tmp_path / "reel-data.json"
    write_bridge_file(
        hook="h", quote="q", attribution="— S", cta="c",
        mood="dark_philosophical", duration=10, fps=30, bridge_path=p,
        hook_words=[{"w": "Nobody", "start": 0.0, "end": 0.4},
                    {"w": "moved.", "start": 0.5, "end": 0.9}],
        anim_seed=42)
    d = json.loads(p.read_text())
    assert d["animSeed"] == 42
    assert d["wordTimes"]["hook"][0]["cls"] == "neg"
    assert d["wordTimes"]["hook"][1]["cls"] == "end"


def test_default_seed_zero(tmp_path):
    p = tmp_path / "reel-data.json"
    write_bridge_file(hook="h", quote="q", attribution="— S", cta="c",
                      mood="dark_philosophical", duration=10, fps=30,
                      bridge_path=p)
    assert json.loads(p.read_text())["animSeed"] == 0
