"""
Visual Effects Overlays — particle systems and atmospheric enhancements.

Generates transparent PNG overlays that can be composited onto scenes:
  - Floating embers (warm, upward drift)
  - Dust motes (neutral, atmospheric depth)
  - Light rays (god rays, volumetric)
  - Rain streaks (moody, dramatic)
  - Fireflies (mystical, bioluminescent)
  - Snow (serene, winter)

Usage:
    from src.overlays.particles import ParticleOverlay
    overlay = ParticleOverlay(type="embers", size=(1080, 1920))
    particle_img = overlay.generate(seed=42)
    # Composite onto scene:
    scene.paste(particle_img, (0, 0), particle_img)
"""

import random
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


class ParticleOverlay:
    """
    Generate particle effect overlays as transparent PNGs.
    """

    PARTICLE_PRESETS = {
        "embers": {
            "color_range": [(255, 200, 100), (255, 150, 50), (255, 100, 30)],
            "size_range": (1, 4),
            "speed_range": (0.3, 1.5),
            "direction": (0.1, -0.9),      # Up with slight drift
            "opacity": 0.7,
            "density": 80,
            "blur": 0,
        },
        "dust": {
            "color_range": [(220, 210, 190), (200, 190, 170), (180, 170, 150)],
            "size_range": (1, 3),
            "speed_range": (0.1, 0.4),
            "direction": (0.3, -0.2),     # Slow drift
            "opacity": 0.4,
            "density": 120,
            "blur": 1,
        },
        "fireflies": {
            "color_range": [(200, 255, 150), (180, 255, 200), (220, 255, 100)],
            "size_range": (2, 5),
            "speed_range": (0.2, 0.8),
            "direction": (0.2, -0.3),
            "opacity": 0.8,
            "density": 40,
            "blur": 2,
        },
        "snow": {
            "color_range": [(255, 255, 255), (240, 245, 255), (230, 235, 250)],
            "size_range": (2, 5),
            "speed_range": (0.5, 1.5),
            "direction": (0.1, 0.8),      # Falling down
            "opacity": 0.6,
            "density": 100,
            "blur": 1,
        },
        "rain": {
            "color_range": [(200, 210, 220), (180, 190, 200)],
            "size_range": (1, 2),
            "speed_range": (3.0, 6.0),
            "direction": (0.3, 1.0),     # Diagonal down
            "opacity": 0.3,
            "density": 200,
            "blur": 0,
        },
        "sparks": {
            "color_range": [(255, 255, 200), (255, 200, 50), (255, 100, 0)],
            "size_range": (1, 3),
            "speed_range": (1.0, 3.0),
            "direction": (0.2, -0.8),
            "opacity": 0.9,
            "density": 60,
            "blur": 0,
        },
    }

    def __init__(self, particle_type: str = "embers", size: tuple = (1080, 1920)):
        self.particle_type = particle_type if particle_type in self.PARTICLE_PRESETS else "embers"
        self.width, self.height = size
        self.config = self.PARTICLE_PRESETS[self.particle_type]

    def generate(self, seed: int = 0, output_path: str | None = None) -> Image.Image:
        """
        Generate a single-frame particle overlay.
        For animation, call this multiple times with different seeds.
        """
        if seed:
            random.seed(seed)

        # Create transparent canvas
        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        density = self.config["density"]
        color_range = self.config["color_range"]
        size_min, size_max = self.config["size_range"]
        opacity = int(255 * self.config["opacity"])

        for _ in range(density):
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            size = random.randint(size_min, size_max)
            color = random.choice(color_range)
            alpha = int(opacity * random.uniform(0.5, 1.0))

            # Draw particle with soft edge (ellipse)
            draw.ellipse(
                [x - size, y - size, x + size, y + size],
                fill=(*color, alpha),
            )

        # Apply blur if configured
        if self.config.get("blur", 0) > 0:
            overlay = overlay.filter(ImageFilter.GaussianBlur(radius=self.config["blur"]))

        # Save if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            overlay.save(output_path)

        return overlay

    def generate_animated_frames(
        self,
        duration: float = 8.0,
        fps: int = 30,
        seed: int = 0,
        output_dir: str = "output/particles",
    ) -> list[Path]:
        """
        Generate frame sequence for animated particles.
        Returns list of frame paths for ffmpeg assembly.
        """
        if seed:
            random.seed(seed)

        total_frames = int(duration * fps)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize particle positions and velocities
        particles = []
        for _ in range(self.config["density"]):
            particles.append({
                "x": random.uniform(0, self.width),
                "y": random.uniform(0, self.height),
                "vx": random.uniform(-0.5, 0.5) + self.config["direction"][0],
                "vy": random.uniform(-0.5, 0.5) + self.config["direction"][1],
                "size": random.randint(*self.config["size_range"]),
                "color": random.choice(self.config["color_range"]),
                "phase": random.uniform(0, math.pi * 2),  # for pulsing
            })

        paths = []
        for frame_idx in range(total_frames):
            overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            for p in particles:
                # Update position
                p["x"] += p["vx"] * 2  # speed multiplier
                p["y"] += p["vy"] * 2

                # Wrap around edges
                if p["x"] < -10:
                    p["x"] = self.width + 10
                if p["x"] > self.width + 10:
                    p["x"] = -10
                if p["y"] < -10:
                    p["y"] = self.height + 10
                if p["y"] > self.height + 10:
                    p["y"] = -10

                # Pulsing opacity
                pulse = math.sin(frame_idx * 0.1 + p["phase"])
                alpha = int(255 * self.config["opacity"] * (0.5 + 0.5 * pulse))

                # Draw
                size = p["size"]
                draw.ellipse(
                    [p["x"] - size, p["y"] - size, p["x"] + size, p["y"] + size],
                    fill=(*p["color"], max(0, min(255, alpha))),
                )

            # Blur
            if self.config.get("blur", 0) > 0:
                overlay = overlay.filter(ImageFilter.GaussianBlur(radius=self.config["blur"]))

            path = output_dir / f"frame_{frame_idx:05d}.png"
            overlay.save(path)
            paths.append(path)

        return paths

    @classmethod
    def for_mood(cls, mood: str, size: tuple = (1080, 1920)) -> "ParticleOverlay":
        """Return a particle overlay matched to the visual mood."""
        mood_particles = {
            "dark_philosophical": "embers",
            "dramatic_ancient": "sparks",
            "cinematic_hopeful": "dust",
            "stark_minimal": "dust",
            "epic_warrior": "embers",
            "mystical_greek": "fireflies",
            "calm_stoic": "dust",
        }
        return cls(
            particle_type=mood_particles.get(mood, "embers"),
            size=size,
        )


class LightRayOverlay:
    """
    Generate volumetric light ray (god ray) overlays.
    Adds depth and atmosphere to scenes.
    """

    def __init__(self, size: tuple = (1080, 1920)):
        self.width, self.height = size

    def generate(
        self,
        origin: tuple = (540, 0),      # Ray origin (x, y)
        angle: float = 45,              # Degrees from vertical
        ray_count: int = 5,
        color: tuple = (255, 240, 200),  # Warm light
        seed: int = 0,
    ) -> Image.Image:
        """Generate a static light ray overlay."""
        if seed:
            random.seed(seed)

        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        angle_rad = math.radians(angle)

        for i in range(ray_count):
            # Each ray is a wide polygon fanning out
            ray_width = random.uniform(30, 80)
            ray_length = random.uniform(self.height * 0.6, self.height * 1.2)
            alpha = int(random.uniform(15, 40))

            # Calculate ray endpoints
            dx = math.sin(angle_rad + random.uniform(-0.1, 0.1)) * ray_length
            dy = math.cos(angle_rad + random.uniform(-0.1, 0.1)) * ray_length

            x1 = origin[0] - ray_width / 2
            y1 = origin[1]
            x2 = origin[0] + dx - ray_width / 2
            y2 = origin[1] + dy
            x3 = origin[0] + dx + ray_width / 2
            y3 = origin[1] + dy
            x4 = origin[0] + ray_width / 2
            y4 = origin[1]

            draw.polygon(
                [(x1, y1), (x2, y2), (x3, y3), (x4, y4)],
                fill=(*color, alpha),
            )

        # Blur for softness
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=20))
        return overlay

    @classmethod
    def for_mood(cls, mood: str, size: tuple = (1080, 1920)) -> "LightRayOverlay":
        """Return light ray config matched to mood."""
        configs = {
            "dark_philosophical": {"origin": (540, 0), "angle": 60, "color": (200, 180, 140)},
            "dramatic_ancient": {"origin": (200, 0), "angle": 75, "color": (255, 200, 100)},
            "cinematic_hopeful": {"origin": (540, 0), "angle": 45, "color": (255, 240, 200)},
            "epic_warrior": {"origin": (800, 0), "angle": 55, "color": (255, 220, 150)},
            "mystical_greek": {"origin": (400, 0), "angle": 30, "color": (200, 180, 255)},
            "calm_stoic": {"origin": (540, 0), "angle": 50, "color": (255, 250, 230)},
        }
        config = configs.get(mood, configs["cinematic_hopeful"])
        overlay = cls(size)
        return overlay.generate(**config, seed=42)


# ── Convenience exports ────────────────────────────────────────────────────────

def add_particles_to_image(
    image: Image.Image,
    mood: str = "dark_philosophical",
    seed: int = 0,
) -> Image.Image:
    """One-shot: composite particles onto an existing image."""
    particles = ParticleOverlay.for_mood(mood, size=image.size)
    overlay = particles.generate(seed=seed)
    result = image.convert("RGBA")
    result = Image.alpha_composite(result, overlay)
    return result.convert("RGB")


def add_light_rays_to_image(
    image: Image.Image,
    mood: str = "cinematic_hopeful",
) -> Image.Image:
    """One-shot: composite light rays onto an existing image."""
    rays = LightRayOverlay.for_mood(mood, size=image.size)
    result = image.convert("RGBA")
    result = Image.alpha_composite(result, rays)
    return result.convert("RGB")
