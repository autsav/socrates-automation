"""
Motion Effects Engine — cinematic camera movement and visual dynamics for Reels.

Replaces basic zoompan with physics-informed motion:
  - Easing curves (ease-in-out, expo, elastic) for natural camera feel
  - Motion blur simulation via frame blending
  - Multi-axis Ken Burns (zoom + pan + tilt simultaneously)
  - Speed ramping (slow→fast→slow) for dramatic pacing
  - Particle overlay compositing (embers, dust, light rays)

Usage:
    from src.visual.motion_effects import MotionEngine, Easing
    engine = MotionEngine(image_size=(1080, 1920))
    cmd = engine.build_ken_burns_cmd(
        input_path="scene.jpg",
        duration=8.0,
        start_rect=(0.0, 0.0, 1.0, 1.0),    # full frame
        end_rect=(0.2, 0.3, 0.8, 0.9),      # zoom to center-right
        easing=Easing.EASE_IN_OUT_QUAD,
        motion_blur=True,
    )
"""

import math
import random
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable


class Easing(Enum):
    """Easing functions for natural camera movement."""
    LINEAR = auto()
    EASE_IN_OUT_QUAD = auto()      # Smooth accel/decel — most cinematic
    EASE_OUT_EXPO = auto()          # Fast start, slow landing — dramatic reveal
    EASE_IN_BACK = auto()           # Slight overshoot — punchy
    EASE_OUT_ELASTIC = auto()       # Bouncy settle — energetic
    EASE_IN_OUT_CUBIC = auto()      # Very smooth — documentary style

    def apply(self, t: float) -> float:
        """Map linear time t (0-1) to eased value."""
        if self == Easing.LINEAR:
            return t
        elif self == Easing.EASE_IN_OUT_QUAD:
            return t * t * (3 - 2 * t)
        elif self == Easing.EASE_OUT_EXPO:
            return 1 - math.pow(2, -10 * t)
        elif self == Easing.EASE_IN_BACK:
            c1 = 1.70158
            c3 = c1 + 1
            return c3 * t * t * t - c1 * t * t
        elif self == Easing.EASE_OUT_ELASTIC:
            c4 = (2 * math.pi) / 3
            if t == 0:
                return 0
            if t == 1:
                return 1
            return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1
        elif self == Easing.EASE_IN_OUT_CUBIC:
            return t * t * t * (t * (t * 6 - 15) + 10)
        return t


@dataclass
class CameraMove:
    """Defines a camera movement from start to end state."""
    start_zoom: float = 1.0          # 1.0 = no zoom
    end_zoom: float = 1.12
    start_pan: tuple = (0.0, 0.0)    # (x_offset, y_offset) as fraction of image
    end_pan: tuple = (0.0, 0.0)
    start_tilt: float = 0.0          # Rotation in degrees
    end_tilt: float = 0.0
    duration: float = 8.0
    easing: Easing = Easing.EASE_IN_OUT_QUAD
    fps: int = 30


@dataclass
class ParticleConfig:
    """Configuration for particle overlay effects."""
    enabled: bool = False
    particle_type: str = "embers"    # embers | dust | snow | rain | fireflies
    density: int = 50                # particles per frame
    color: tuple = (255, 200, 100)   # RGB
    size_range: tuple = (1, 4)       # pixel size min/max
    speed_range: tuple = (0.5, 2.0)  # pixels per frame
    direction: tuple = (0, -1)       # (x, y) vector
    opacity: float = 0.6


class MotionEngine:
    """
    Build ffmpeg filter strings for cinematic camera movements.
    """

    def __init__(self, image_size: tuple = (1080, 1920), fps: int = 30):
        self.width, self.height = image_size
        self.fps = fps
        self.total_frames = 0

    # ── Ken Burns with Easing ──────────────────────────────────────────────────

    def build_ken_burns_filter(
        self,
        move: CameraMove,
        motion_blur: bool = False,
        motion_blur_frames: int = 3,
    ) -> str:
        """
        Build an ffmpeg zoompan filter string with easing.
        Returns a filter chain that can be inserted into -filter_complex.
        """
        total_frames = int(move.duration * move.fps)
        self.total_frames = total_frames

        # Build zoom expression with easing
        zoom_expr = self._build_zoom_expression(
            move.start_zoom, move.end_zoom, total_frames, move.easing
        )

        # Build pan expressions
        x_expr, y_expr = self._build_pan_expressions(
            move.start_pan, move.end_pan, total_frames, move.easing
        )

        # Build tilt expression (rotation)
        tilt_expr = self._build_tilt_expression(
            move.start_tilt, move.end_tilt, total_frames, move.easing
        )

        # Base zoompan filter
        zoompan = (
            f"zoompan=z='{zoom_expr}':"
            f"x='{x_expr}':y='{y_expr}':"
            f"d={total_frames}:s={self.width}x{self.height}:fps={move.fps}"
        )

        # Add rotation if tilt is non-zero
        if abs(move.start_tilt) > 0.1 or abs(move.end_tilt) > 0.1:
            zoompan += f",rotate='{tilt_expr}:ow={self.width}:oh={self.height}:c=black'"

        # Add motion blur via frame blending
        if motion_blur:
            # tblend averages consecutive frames to simulate motion blur
            zoompan += f",tblend=all_mode=average,framestep=1"
            # Alternative: minterpolate + blend for smoother blur
            zoompan += f",minterpolate='mi_mode=mci:mc_mode=aobmc:vsbmc=1:fps={move.fps}'"

        return zoompan

    @staticmethod
    def _eased_t_expr(easing: Easing, frames: int, var: str = "in") -> str:
        """ffmpeg per-frame expression for eased progress t in [0,1], using
        the same curves as Easing.apply() but evaluated by ffmpeg itself.

        ``var`` is the ffmpeg frame-index variable to divide by: the ``zoompan``
        filter exposes ``in`` (input frame count), but the ``rotate`` filter has
        NO ``in`` variable — it uses ``n`` (frame number). Passing ``in`` to
        ``rotate`` makes ffmpeg fail to parse the angle expression ("Invalid
        argument", -22), so the tilt/rotate path must use ``n``."""
        t = f"({var}/{frames})"
        if easing == Easing.EASE_IN_OUT_QUAD:
            return f"({t}*{t}*(3-2*{t}))"
        if easing == Easing.EASE_OUT_EXPO:
            return f"(1-pow(2,-10*{t}))"
        if easing == Easing.EASE_IN_BACK:
            c1 = 1.70158
            c3 = c1 + 1
            return f"({c3:.5f}*{t}*{t}*{t}-{c1:.5f}*{t}*{t})"
        if easing == Easing.EASE_OUT_ELASTIC:
            c4 = (2 * math.pi) / 3
            return f"(pow(2,-10*{t})*sin(({t}*10-0.75)*{c4:.6f})+1)"
        if easing == Easing.EASE_IN_OUT_CUBIC:
            return f"({t}*{t}*{t}*({t}*({t}*6-15)+10))"
        return t  # LINEAR

    def _build_zoom_expression(
        self, z_start: float, z_end: float, frames: int, easing: Easing
    ) -> str:
        """Build zoom expression with easing using ffmpeg's expression evaluator."""
        eased_t = self._eased_t_expr(easing, frames)
        return f"({z_start:.6f}+({z_end - z_start:.6f})*{eased_t})"

    def _build_pan_expressions(
        self, p_start: tuple, p_end: tuple, frames: int, easing: Easing
    ) -> tuple[str, str]:
        """Build x/y pan expressions."""
        eased_t = self._eased_t_expr(easing, frames)

        # x offset in pixels
        x_start_px = int(p_start[0] * self.width)
        x_end_px = int(p_end[0] * self.width)

        y_start_px = int(p_start[1] * self.height)
        y_end_px = int(p_end[1] * self.height)

        # Standard centering formula with offset: (iw-iw/zoom)/2 + offset
        x_expr = f"(iw-iw/zoom)/2+{x_start_px}+({x_end_px - x_start_px})*{eased_t}"
        y_expr = f"(ih-ih/zoom)/2+{y_start_px}+({y_end_px - y_start_px})*{eased_t}"

        return x_expr, y_expr

    def _build_tilt_expression(
        self, t_start: float, t_end: float, frames: int, easing: Easing
    ) -> str:
        """Build rotation expression in radians. Uses ``n`` (the rotate filter's
        frame variable) — the ``rotate`` filter has no ``in`` variable."""
        eased_t = self._eased_t_expr(easing, frames, var="n")
        return f"({math.radians(t_start):.6f}+{math.radians(t_end - t_start):.6f}*{eased_t})"

    # ── Pre-computed Eased Keyframes (higher quality) ──────────────────────────

    def build_eased_ken_burns(
        self,
        move: CameraMove,
        output_dir: str = "output",
        prefix: str = "kb",
    ) -> str:
        """
        Generate individual eased frames and reassemble.
        More accurate than zoompan expression but slower.
        Returns path to generated frame sequence or video.
        """
        from PIL import Image

        output_dir = Path(output_dir)
        frames_dir = output_dir / f"{prefix}_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        total_frames = int(move.duration * move.fps)

        # This is a placeholder for the full implementation
        # In practice, we'd generate frames here using PIL transforms
        # For now, return a filter string that approximates easing
        return self.build_ken_burns_filter(move, motion_blur=True)

    # ── Motion Blur Standalone ────────────────────────────────────────────────

    @staticmethod
    def motion_blur_filter(strength: int = 2) -> str:
        """
        Add motion blur to video via temporal averaging.
        strength = number of frames to blend.
        """
        if strength <= 1:
            return ""
        # Use tmix for temporal mixing (ffmpeg 4.4+)
        return f"tmix=frames={strength}:weights='1 1 1'"

    @staticmethod
    def speed_ramp_filter(
        keyframes: list[tuple[float, float]],  # (time_seconds, speed_multiplier)
        fps: int = 30,
    ) -> str:
        """
        Build a speed ramp filter.
        Example: [(0, 0.5), (2, 1.0), (6, 1.0), (8, 0.5)]
        = slow start, normal middle, slow end
        """
        if not keyframes:
            return ""
        # Build setpts expression
        expr_parts = []
        for i in range(len(keyframes) - 1):
            t_start, s_start = keyframes[i]
            t_end, s_end = keyframes[i + 1]
            # Simplified: just use minsetpts for speed changes
            pass
        # Return minterpolate-based speed change
        return "setpts='PTS/1.0'"  # placeholder

    # ── Scene-Specific Presets ─────────────────────────────────────────────────

    @classmethod
    def hook_scene_move(cls, duration: float = 4.0, seed: int = 0) -> CameraMove:
        """
        Dramatic hook scene: fast zoom from wide to tight with slight tilt.
        Research: viewers decide in 2.5-3.5s. Motion must be immediate.
        """
        if seed:
            random.seed(seed)
        # Randomize direction for variety
        pan_dirs = [
            ((0, 0), (0.15, 0.05)),    # pan right slightly
            ((0, 0), (-0.1, 0.08)),     # pan left + down
            ((0, 0), (0, 0.1)),         # tilt down
            ((0, 0), (0.05, -0.05)),    # pan right + up
        ]
        start_pan, end_pan = random.choice(pan_dirs)
        return CameraMove(
            start_zoom=1.0,
            end_zoom=1.15 + random.uniform(0, 0.05),  # 1.15-1.20
            start_pan=start_pan,
            end_pan=end_pan,
            start_tilt=random.uniform(-1.5, 1.5),
            end_tilt=random.uniform(-3, 3),
            duration=duration,
            easing=Easing.EASE_OUT_EXPO,  # Fast reveal, slow settle
            fps=30,
        )

    @classmethod
    def quote_scene_move(cls, duration: float = 8.0, seed: int = 0) -> CameraMove:
        """
        Quote scene: slow, contemplative drift.
        Enough motion to keep algorithm happy but slow enough to read.
        """
        if seed:
            random.seed(seed)
        pan_dirs = [
            ((0, 0), (0.08, 0.03)),
            ((0, 0), (-0.05, 0.06)),
            ((0, 0), (0.03, -0.04)),
        ]
        start_pan, end_pan = random.choice(pan_dirs)
        return CameraMove(
            start_zoom=1.05,              # Already slightly zoomed in
            end_zoom=1.12 + random.uniform(0, 0.03),
            start_pan=start_pan,
            end_pan=end_pan,
            start_tilt=random.uniform(-0.5, 0.5),
            end_tilt=random.uniform(-1, 1),
            duration=duration,
            easing=Easing.EASE_IN_OUT_QUAD,  # Smooth sailing
            fps=30,
        )

    @classmethod
    def cta_scene_move(cls, duration: float = 3.0, seed: int = 0) -> CameraMove:
        """
        CTA scene: punchy snap-zoom for urgency.
        """
        if seed:
            random.seed(seed)
        return CameraMove(
            start_zoom=1.0,
            end_zoom=1.08,
            start_pan=(0, 0),
            end_pan=(random.uniform(-0.03, 0.03), random.uniform(-0.02, 0.02)),
            start_tilt=0,
            end_tilt=random.uniform(-1, 1),
            duration=duration,
            easing=Easing.EASE_OUT_EXPO,
            fps=30,
        )

    @classmethod
    def transition_types(cls) -> list[str]:
        """Return available xfade transition types for variety."""
        return [
            "fade",           # Default, safe
            "wipeleft",       # Directional wipe
            "wiperight",
            "wipeup",
            "wipedown",
            "slideleft",      # Slide transition
            "slideright",
            "slideup",
            "slidedown",
            "smoothleft",     # Smooth directional
            "smoothright",
            "circlecrop",     # Circle reveal
            "rectcrop",       # Rectangle reveal
            "distance",       # Distance fade
            "hblur",          # Horizontal blur transition
        ]

    @classmethod
    def random_transition(cls, seed: int = 0) -> str:
        """Pick a random transition type, weighted toward safe options."""
        if seed:
            random.seed(seed)
        types = cls.transition_types()
        # Weight fade higher for reliability
        weights = [30] + [5] * (len(types) - 1)
        return random.choices(types, weights=weights, k=1)[0]


# ── Standalone motion blur filter builder ─────────────────────────────────────

def build_motion_blur_filter(strength: int = 2) -> str:
    """Quick motion blur filter string for ffmpeg."""
    if strength <= 0:
        return ""
    return MotionEngine.motion_blur_filter(strength)


def build_ken_burns_preset(
    scene_type: str,  # "hook", "quote", "cta"
    duration: float,
    seed: int = 0,
) -> CameraMove:
    """Factory for scene-type-specific camera moves."""
    if scene_type == "hook":
        return MotionEngine.hook_scene_move(duration, seed)
    elif scene_type == "quote":
        return MotionEngine.quote_scene_move(duration, seed)
    elif scene_type == "cta":
        return MotionEngine.cta_scene_move(duration, seed)
    return CameraMove(duration=duration)
