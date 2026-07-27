"""Beat-sync transition_type preservation.

When beat_sync_info provides transition_type, MotionEngine.random_transition
must not clobber it. The buggy code unconditionally calls random_transition
(overwriting the beat-sync value); the fix guards the call with
``if transition_type is None:`` at L275-276.
"""
import textwrap
from unittest.mock import patch

from src.video import reel_composer
from src.visual.motion_effects import MotionEngine


def test_random_transition_not_called_when_beat_sync_present():
    """When beat_sync_info has transition_type, MotionEngine.random_transition must not run."""
    captured = {"called": False}

    def fake_random(seed):
        captured["called"] = True
        return "random-cut"

    # Drive the actual assignment block from reel_composer.py. Reading the
    # source lines by content (not line number) keeps the test robust to
    # whitespace changes. The patched MotionEngine.random_transition is what
    # the source code calls, so on baseline the unguarded call clobbers
    # transition_type -> captured["called"] is True -> test fails.
    src = open(reel_composer.__file__).read().splitlines()
    if_start = next(
        i for i, line in enumerate(src)
        if "if beat_sync_info and beat_sync_info" in line
    )
    if_end = next(
        i for i, line in enumerate(src[if_start:], start=if_start)
        if line.strip().startswith("transition_type =")
    )
    block_lines = src[if_start:if_end + 1]
    random_idx = next(
        i for i, line in enumerate(src)
        if "transition_type = MotionEngine.random_transition" in line
    )
    # Include the `if transition_type is None:` guard above the call if present.
    # On baseline the call is unconditional; on the fixed source the guard
    # prevents the call when beat_sync_info provided a transition_type.
    random_block = []
    if random_idx > 0 and "if transition_type is None" in src[random_idx - 1]:
        random_block.append(src[random_idx - 1])
    random_block.append(src[random_idx])
    code = textwrap.dedent("\n".join(block_lines + random_block))

    namespace = {
        "beat_sync_info": {
            "transition_type": "fade",
            "used_beats": True,
            "scene_durations": [4, 8, 3],
            "transition_offsets": [3.5, 11.0],
        },
        "SCENE_DURATIONS": [4, 8, 3],
        "TRANSITION_DURATION": 0.5,
        "MotionEngine": MotionEngine,
        "timestamp": "test",
    }

    with patch.object(MotionEngine, "random_transition", side_effect=fake_random):
        exec(code, namespace)
        transition_type = namespace["transition_type"]

    assert transition_type == "fade"
    assert captured["called"] is False
