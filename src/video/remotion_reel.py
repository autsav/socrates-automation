"""
Remotion Reel generator — the professional-animation video path.

Renders the Instagram POV Reel with a React/Remotion project (``remotion/`` at
the repo root) that produces broadcast-quality, physics-driven text animations:
word-by-word spring reveals, animated mood-colored gradient + particle fields,
breathing vignette, and pattern-interrupt flashes.

The ONLY communication between Python and Remotion is a JSON bridge file. Python
writes ``remotion/public/reel-data.json`` and invokes ``npx remotion render``.

This path degrades gracefully: if Node.js or the Remotion project isn't installed,
``generate_remotion_reel`` returns ``None`` so callers can fall back to the
ffmpeg-based POV generator (``src.video.pov_reel_generator``).

Usage:
    from src.video.remotion_reel import generate_remotion_reel

    path = generate_remotion_reel(
        hook="Purpose doesn't find you. You find it.",
        quote="The beginning of wisdom is the desire to learn.",
        attribution="— Socrates",
        cta="Save this. You'll need it again.",
        mood="dark_philosophical",
        output_path="output/reel.mp4",
    )
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from src.video import beat_sync

# Repo root: src/video/remotion_reel.py -> src -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
REMOTION_DIR = REPO_ROOT / "remotion"
BRIDGE_FILE = REMOTION_DIR / "public" / "reel-data.json"
COMPOSITION_ID = "PovReel"
ENTRY_POINT = "src/index.ts"

MIN_DURATION = 7.0
MAX_DURATION = 15.0

# The 7 moods the theme.ts palette supports. Anything else falls back to the
# first (dark_philosophical) inside Remotion, but we keep the list here so the
# Python side can validate/round-trip too.
SUPPORTED_MOODS = (
    "dark_philosophical",
    "dramatic_ancient",
    "cinematic_hopeful",
    "stark_minimal",
    "epic_warrior",
    "mystical_greek",
    "calm_stoic",
)


def node_available() -> bool:
    """True if a Node.js runtime is on PATH."""
    return shutil.which("node") is not None


def remotion_available() -> bool:
    """True if Node.js is installed AND the Remotion project's deps are present.

    We check for ``remotion/node_modules/remotion`` rather than shelling out, so
    the check is fast and side-effect free.
    """
    if not node_available():
        return False
    if not (REMOTION_DIR / "package.json").exists():
        return False
    if not (REMOTION_DIR / "node_modules" / "remotion").exists():
        return False
    return True


def _clamp_duration(quote: str, duration: float | None) -> float:
    """Pick a sensible reel duration, scaled with quote length when unset."""
    if duration is None:
        duration = min(MAX_DURATION, max(MIN_DURATION, 8.0 + len(quote) / 90))
    return max(MIN_DURATION, min(MAX_DURATION, float(duration)))


def write_bridge_file(
    hook: str,
    quote: str,
    attribution: str,
    cta: str,
    mood: str,
    duration: float,
    fps: int,
    bridge_path: Path = BRIDGE_FILE,
    voiceover_path: Path | None = None,
) -> Path:
    """Write the reel-data.json bridge file the Remotion composition reads.

    When ``voiceover_path`` is supplied, its beats are detected and written as
    ``beats`` (absolute seconds), and the audio is copied next to the bridge as
    ``reel-audio<ext>`` and referenced by the ``audio`` key so Remotion's
    ``<Audio>`` (via ``staticFile``) can play — and bake — it into the render.
    With no voiceover, ``beats`` is ``[]`` and ``audio`` is omitted, giving the
    original silent-reel behavior.

    Returns the path written. Exposed separately so tests can exercise it
    without invoking Node.
    """
    if mood not in SUPPORTED_MOODS:
        mood = SUPPORTED_MOODS[0]

    beats: list[float] = []
    audio_name: str | None = None
    if voiceover_path is not None and Path(voiceover_path).exists():
        voiceover_path = Path(voiceover_path)
        audio_name = "reel-audio" + voiceover_path.suffix
        bridge_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(voiceover_path, bridge_path.parent / audio_name)
        try:
            beats = beat_sync.detect_beats(voiceover_path)
        except Exception as e:  # pragma: no cover - defensive
            print(f"  [remotion] beat detection failed ({e}) — reel stays un-synced")
            beats = []

    payload = {
        "hook": hook or "",
        "quote": quote or "",
        "attribution": attribution or "",
        "cta": cta or "",
        "mood": mood,
        "duration": round(float(duration), 3),
        "fps": int(fps),
        "beats": beats,
    }
    if audio_name:
        payload["audio"] = audio_name

    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return bridge_path


def generate_remotion_reel(
    hook: str,
    quote: str,
    attribution: str = "— Socrates",
    cta: str = "",
    mood: str = "dark_philosophical",
    output_path: str | Path | None = None,
    duration: float | None = None,
    fps: int = 30,
    timeout: int = 600,
    voiceover_path: Path | None = None,
) -> Path | None:
    """
    Render a POV Reel via Remotion (React-based, headless-browser rendering).

    Steps:
      1. Write the reel data to ``remotion/public/reel-data.json``.
      2. Run ``npx remotion render <entry> PovReel <output> --props=<bridge>``.
      3. Return the output MP4 path.

    Returns ``None`` (never raises) if Node/Remotion is unavailable or the render
    fails, so callers can fall back to the ffmpeg POV generator.
    """
    if output_path is None:
        output_path = REPO_ROOT / "output" / "remotion_reel.mp4"
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not remotion_available():
        print("  [remotion] Node/Remotion not installed — skipping (use POV fallback)")
        return None

    duration = _clamp_duration(quote, duration)

    # 1. Write the JSON bridge — the ONLY channel between Python and Remotion.
    bridge = write_bridge_file(
        hook=hook,
        quote=quote,
        attribution=attribution,
        cta=cta,
        mood=mood,
        duration=duration,
        fps=fps,
        voiceover_path=voiceover_path,
    )

    # 2. Invoke the Remotion CLI. --props takes a path to the JSON bridge file.
    cmd = [
        "npx",
        "remotion",
        "render",
        ENTRY_POINT,
        COMPOSITION_ID,
        str(output_path),
        f"--props={bridge}",
        "--log=error",
    ]

    print(f"  [remotion] Rendering Reel ({duration:.1f}s, mood={mood})...")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REMOTION_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"  [remotion] ⚠️ Render timed out after {timeout}s — falling back")
        return None
    except Exception as e:  # pragma: no cover - defensive
        print(f"  [remotion] ⚠️ Render invocation failed: {e} — falling back")
        return None

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error")[-800:]
        print(f"  [remotion] ⚠️ Render failed — falling back to POV generator:\n{err}")
        return None

    if not output_path.exists():
        print("  [remotion] ⚠️ Render reported success but output missing — falling back")
        return None

    size = output_path.stat().st_size
    print(f"  [remotion] Saved: {output_path} ({size / 1024:.0f} KB)")
    return output_path


if __name__ == "__main__":
    out = generate_remotion_reel(
        hook="Purpose doesn't find you. You find it.",
        quote="The unexamined life is not worth living.",
        attribution="— Socrates",
        cta="Save this before you forget it.",
        mood="dark_philosophical",
        output_path=REPO_ROOT / "output" / "remotion_demo.mp4",
    )
    print(out)
