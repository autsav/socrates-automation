import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.visual.motion_effects import MotionEngine, Easing


def _eng():
    return MotionEngine(image_size=(1080, 1920), fps=30)


def test_tilt_expression_uses_n_not_in():
    # The tilt expression feeds ffmpeg's `rotate` filter, whose valid frame
    # variable is `n` (NOT `in`). Using `in` makes ffmpeg fail to parse the
    # angle expression -> "Invalid argument" (-22).
    expr = _eng()._build_tilt_expression(0.0, 2.0, 120, Easing.EASE_OUT_EXPO)
    assert "n/120" in expr
    assert "in/" not in expr, f"rotate has no 'in' variable: {expr!r}"


def test_zoom_expression_still_uses_in_for_zoompan():
    # zoompan DOES have an `in` variable — leave the zoom/pan path unchanged.
    z = _eng()._build_zoom_expression(1.0, 1.1, 120, Easing.EASE_OUT_EXPO)
    assert "in/120" in z


def test_pan_expressions_still_use_in_for_zoompan():
    x, y = _eng()._build_pan_expressions((0.0, 0.0), (0.1, 0.1), 120, Easing.EASE_OUT_EXPO)
    assert "in/120" in x and "in/120" in y
