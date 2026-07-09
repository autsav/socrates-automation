import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.visual.motion_effects import Easing, MotionEngine, CameraMove


@pytest.mark.parametrize("member", list(Easing))
def test_apply_does_not_raise_for_any_member(member):
    """Regression: EASE_OUT_EXPO.apply() used to reference the bare enum
    member name instead of Easing.EASE_OUT_EXPO, raising a NameError."""
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        member.apply(t)


def test_ease_out_expo_matches_formula():
    import math
    assert Easing.EASE_OUT_EXPO.apply(0.5) == pytest.approx(1 - math.pow(2, -5))


def test_zoom_expression_differs_by_easing_curve():
    """Regression: the ffmpeg expression builders accepted an `easing` param
    but always computed a straight linear interpolation regardless."""
    engine = MotionEngine()
    linear = engine._build_zoom_expression(1.0, 1.2, 90, Easing.LINEAR)
    eased = engine._build_zoom_expression(1.0, 1.2, 90, Easing.EASE_OUT_EXPO)
    assert linear != eased
    assert "pow" in eased


def test_pan_and_tilt_expressions_use_easing():
    engine = MotionEngine()
    linear_x, linear_y = engine._build_pan_expressions((0, 0), (0.1, 0.1), 90, Easing.LINEAR)
    eased_x, eased_y = engine._build_pan_expressions((0, 0), (0.1, 0.1), 90, Easing.EASE_IN_OUT_CUBIC)
    assert linear_x != eased_x
    assert linear_y != eased_y

    linear_tilt = engine._build_tilt_expression(0, 5, 90, Easing.LINEAR)
    eased_tilt = engine._build_tilt_expression(0, 5, 90, Easing.EASE_OUT_ELASTIC)
    assert linear_tilt != eased_tilt
    assert "sin" in eased_tilt


def test_build_ken_burns_filter_still_builds_a_valid_zoompan_string():
    engine = MotionEngine()
    move = CameraMove(easing=Easing.EASE_OUT_EXPO, duration=2.0, fps=30)
    result = engine.build_ken_burns_filter(move)
    assert result.startswith("zoompan=")


def test_hook_scene_move_apply_does_not_raise():
    """hook_scene_move() sets easing=Easing.EASE_OUT_EXPO — calling .apply()
    on it must not raise (the dormant NameError this preset was hit by)."""
    move = MotionEngine.hook_scene_move(seed=1)
    assert move.easing.apply(0.5) is not None
