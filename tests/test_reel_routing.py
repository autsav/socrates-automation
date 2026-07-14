import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def test_any_reel_routes_to_remotion():
    # The previously-buggy invocations (studio/manual reel, plain reel) must now
    # take the Remotion POV path.
    assert pipeline._reels_use_remotion(reel=True, carousel=False, remotion=False, pov=False)
    assert pipeline._reels_use_remotion(reel=True, carousel=False, remotion=True, pov=False)


def test_explicit_flags_still_force_remotion():
    assert pipeline._reels_use_remotion(reel=False, carousel=False, remotion=True, pov=False)
    assert pipeline._reels_use_remotion(reel=False, carousel=False, remotion=False, pov=True)


def test_image_and_carousel_are_not_forced_to_reel():
    # Plain image post (no reel) and carousel must NOT be forced onto the reel path.
    assert not pipeline._reels_use_remotion(reel=False, carousel=False, remotion=False, pov=False)
    assert not pipeline._reels_use_remotion(reel=True, carousel=True, remotion=False, pov=False)
