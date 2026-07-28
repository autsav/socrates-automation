import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def test_any_reel_routes_to_pov():
    # Any reel invocation (studio/manual/plain) must now take the POV path.
    assert pipeline._reels_use_renderer(reel=True, carousel=False, renderer="remotion")
    assert pipeline._reels_use_renderer(reel=True, carousel=False, renderer="hyperframes")


def test_explicit_flags_still_force_pov():
    assert pipeline._reels_use_renderer(reel=False, carousel=False, renderer="remotion")
    assert pipeline._reels_use_renderer(reel=False, carousel=False, renderer="ffmpeg")


def test_image_and_carousel_are_not_forced_to_reel():
    # Plain image post (no reel) and carousel must NOT be forced onto the reel path.
    assert not pipeline._reels_use_renderer(reel=False, carousel=False, renderer="image")
    assert not pipeline._reels_use_renderer(reel=True, carousel=True, renderer="remotion")
