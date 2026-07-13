import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import inspect
from src.video import remotion_reel


def test_generate_remotion_reel_accepts_bridge_params():
    sig = inspect.signature(remotion_reel.generate_remotion_reel)
    for p in ("bridge", "bridge_voice", "bridge_words"):
        assert p in sig.parameters, f"generate_remotion_reel missing {p}"
