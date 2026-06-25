"""
Phase 2 Integration Test — verifies motion effects and particle overlays.
"""

import sys
from pathlib import Path

def test_motion_engine():
    """Test MotionEngine filter generation."""
    print("[TEST] MotionEngine...")
    try:
        from motion_effects import MotionEngine, Easing, CameraMove

        engine = MotionEngine(image_size=(1080, 1920), fps=30)

        # Test hook scene move
        move = MotionEngine.hook_scene_move(duration=4.0, seed=42)
        assert move.end_zoom > 1.1
        print(f"    Hook zoom: {move.start_zoom:.2f} → {move.end_zoom:.2f}")

        # Test quote scene move
        move = MotionEngine.quote_scene_move(duration=8.0, seed=42)
        assert move.easing == Easing.EASE_IN_OUT_QUAD
        print(f"    Quote easing: {move.easing.name}")

        # Test filter string generation
        hook_filter = engine.build_ken_burns_filter(move, motion_blur=True)
        assert "zoompan" in hook_filter
        print(f"    Filter string length: {len(hook_filter)} chars")

        # Test transition types
        ttypes = MotionEngine.transition_types()
        assert len(ttypes) > 10
        print(f"    Available transitions: {len(ttypes)}")

        return True
    except Exception as e:
        print(f"  MotionEngine failed: {e}")
        return False


def test_particle_overlay():
    """Test particle overlay generation."""
    print("[TEST] ParticleOverlay...")
    try:
        from overlays.particles import ParticleOverlay, add_particles_to_image
        from PIL import Image

        # Test static overlay
        overlay = ParticleOverlay(particle_type="embers", size=(1080, 1920))
        img = overlay.generate(seed=42)
        assert img.size == (1080, 1920)
        assert img.mode == "RGBA"
        print(f"    Embers overlay: {img.size}, mode={img.mode}")

        # Test mood-matched overlay
        for mood in ["dark_philosophical", "cinematic_hopeful", "mystical_greek"]:
            overlay = ParticleOverlay.for_mood(mood)
            img = overlay.generate(seed=42)
            print(f"    {mood}: {overlay.particle_type}")

        # Test composite onto image
        bg = Image.new("RGB", (1080, 1920), (30, 30, 30))
        result = add_particles_to_image(bg, mood="dark_philosophical", seed=42)
        assert result.size == bg.size
        print(f"    Composite: OK")

        return True
    except Exception as e:
        print(f"  ParticleOverlay failed: {e}")
        return False


def test_light_ray_overlay():
    """Test light ray overlay generation."""
    print("[TEST] LightRayOverlay...")
    try:
        from overlays.particles import LightRayOverlay, add_light_rays_to_image
        from PIL import Image

        overlay = LightRayOverlay(size=(1080, 1920))
        rays = overlay.generate(origin=(540, 0), angle=45, seed=42)
        assert rays.size == (1080, 1920)
        print(f"    Light rays: {rays.size}, mode={rays.mode}")

        # Test mood-matched
        bg = Image.new("RGB", (1080, 1920), (20, 20, 30))
        result = add_light_rays_to_image(bg, mood="cinematic_hopeful")
        assert result.size == bg.size
        print(f"    Mood-matched composite: OK")

        return True
    except Exception as e:
        print(f"  LightRayOverlay failed: {e}")
        return False


def main():
    print("=" * 60)
    print("PHASE 2 INTEGRATION TEST")
    print("=" * 60)
    print()

    tests = [
        test_motion_engine,
        test_particle_overlay,
        test_light_ray_overlay,
    ]

    results = []
    for test in tests:
        results.append(test())
        print()

    passed = sum(results)
    total = len(results)

    print("=" * 60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
