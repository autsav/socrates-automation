"""
Phase 2 Integration Test — verifies motion effects and particle overlays.

Real pytest tests: assertions propagate. Previously each body was wrapped in
try/except → return True/False, which swallowed AssertionError so every test
passed unconditionally.
"""

import sys


def test_motion_engine():
    """Test MotionEngine filter generation."""
    from src.visual.motion_effects import MotionEngine, Easing, CameraMove

    engine = MotionEngine(image_size=(1080, 1920), fps=30)

    move = MotionEngine.hook_scene_move(duration=4.0, seed=42)
    assert move.end_zoom > 1.1

    move = MotionEngine.quote_scene_move(duration=8.0, seed=42)
    assert move.easing == Easing.EASE_IN_OUT_QUAD

    hook_filter = engine.build_ken_burns_filter(move, motion_blur=True)
    assert "zoompan" in hook_filter

    ttypes = MotionEngine.transition_types()
    assert len(ttypes) > 10


def test_particle_overlay():
    """Test particle overlay generation."""
    from src.overlays.particles import ParticleOverlay, add_particles_to_image
    from PIL import Image

    overlay = ParticleOverlay(particle_type="embers", size=(1080, 1920))
    img = overlay.generate(seed=42)
    assert img.size == (1080, 1920)
    assert img.mode == "RGBA"

    for mood in ["dark_philosophical", "cinematic_hopeful", "mystical_greek"]:
        overlay = ParticleOverlay.for_mood(mood)
        overlay.generate(seed=42)

    bg = Image.new("RGB", (1080, 1920), (30, 30, 30))
    result = add_particles_to_image(bg, mood="dark_philosophical", seed=42)
    assert result.size == bg.size


def test_light_ray_overlay():
    """Test light ray overlay generation."""
    from src.overlays.particles import LightRayOverlay, add_light_rays_to_image
    from PIL import Image

    overlay = LightRayOverlay(size=(1080, 1920))
    rays = overlay.generate(origin=(540, 0), angle=45, seed=42)
    assert rays.size == (1080, 1920)

    bg = Image.new("RGB", (1080, 1920), (20, 20, 30))
    result = add_light_rays_to_image(bg, mood="cinematic_hopeful")
    assert result.size == bg.size


def main():
    """Manual smoke runner — raises (non-zero exit) on the first failing test."""
    test_motion_engine()
    test_particle_overlay()
    test_light_ray_overlay()
    print("All Phase 2 integration tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
