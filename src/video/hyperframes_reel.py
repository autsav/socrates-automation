"""HyperFrames Reel generator — deterministic HTML+GSAP video path.

Renders the Instagram POV Reel with a plain-HTML HyperFrames composition
(``hyperframes/`` at the repo root) that produces broadcast-quality text
animations via seek-safe GSAP timelines.

The ONLY communication between Python and HyperFrames is a self-contained
``index.html`` file. Python renders a Jinja2 template, copies media next to
it, and invokes ``npx hyperframes render``.

This path degrades gracefully: any failure returns ``None`` so callers can
fall back to Remotion → ffmpeg POV.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.utils.logger import get_logger
from src.video.reel_data import build_reel_data
from src.video.remotion_reel import _loudnorm, _probe_duration

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
HYPERFRAMES_DIR = REPO_ROOT / "hyperframes"
TEMPLATES_DIR = HYPERFRAMES_DIR / "templates"
ASSETS_DIR = HYPERFRAMES_DIR / "assets"
BRIDGE_FILE = HYPERFRAMES_DIR / "index.html"


def _hyperframes_available() -> bool:
    """True if Node.js is installed AND the HyperFrames project's deps are present."""
    if shutil.which("node") is None:
        return False
    if not (HYPERFRAMES_DIR / "package.json").exists():
        return False
    if not (HYPERFRAMES_DIR / "node_modules").exists():
        return False
    return True


def _copy_assets(payload: dict, dest: Path) -> dict:
    """Copy media files referenced in ``payload`` into ``dest`` and rewrite
    payload paths to be relative to the HTML location."""
    dest.mkdir(parents=True, exist_ok=True)
    updated = dict(payload)

    def _relocate(key: str, src: str | None) -> str | None:
        if not src:
            return None
        p = Path(src)
        if not p.exists():
            return src
        dst = dest / p.name
        if p.resolve() != dst.resolve():
            shutil.copy(p, dst)
        return f"assets/{p.name}"

    voices = updated.get("voices") or {}
    updated["voices"] = {k: _relocate(k, v) for k, v in voices.items()}

    if updated.get("music"):
        updated["music"] = _relocate("music", updated["music"])

    if updated.get("background"):
        updated["background"] = _relocate("background", updated["background"])

    if updated.get("backgrounds"):
        updated["backgrounds"] = [_relocate(f"bg{i}", b) for i, b in enumerate(updated["backgrounds"])]

    sfx = updated.get("sfx")
    if sfx:
        updated["sfx"] = {k: _relocate(k, v) for k, v in sfx.items()}

    return updated


def _render_html(payload: dict, output_path: Path) -> Path:
    """Render the Jinja2 template into a self-contained ``index.html``."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("index.html.j2")

    # Resolve background to file:// URI for local playback
    bg = payload.get("background")
    if bg and Path(bg).exists():
        payload["background"] = Path(bg).resolve().as_uri()

    bgs = payload.get("backgrounds")
    if bgs:
        payload["backgrounds"] = [
            Path(b).resolve().as_uri() if Path(b).exists() else b for b in bgs
        ]

    # Compute sceneFrames from voiceDurations for the template
    from src.video.reel_data import SUPPORTED_MOODS, sceneFrames

    mood = payload.get("mood", "dark_philosophical")
    if mood not in SUPPORTED_MOODS:
        mood = SUPPORTED_MOODS[0]

    vd = payload.get("voiceDurations", {})
    has_bridge = bool(payload.get("bridge"))
    has_hook = bool(payload.get("hook"))
    sf = sceneFrames(
        payload.get("duration", 10.5),
        payload.get("fps", 30),
        {
            "hook": vd.get("hook"),
            "bridge": vd.get("bridge"),
            "quote": vd.get("quote"),
            "cta": vd.get("cta"),
        } if vd else None,
        has_bridge,
        has_hook,
    )

    # Remove computed keys so they don't collide with explicit kwargs
    render_ctx = {k: v for k, v in payload.items() if k not in ("sceneFrames", "mood")}
    html = template.render(
        **render_ctx,
        reel_data=payload,
        sceneFrames=sf,
        mood=mood,
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


def generate_hyperframes_reel(
    hook: str,
    quote: str,
    attribution: str = "— Socrates",
    cta: str = "",
    mood: str = "dark_philosophical",
    output_path: str | Path | None = None,
    duration: float | None = None,
    fps: int = 30,
    timeout: int = 600,
    hook_voice: Path | None = None,
    quote_voice: Path | None = None,
    cta_voice: Path | None = None,
    music_path: Path | None = None,
    hook_words: list | None = None,
    quote_words: list | None = None,
    cta_words: list | None = None,
    bridge: str = "",
    bridge_voice: Path | None = None,
    bridge_words: list | None = None,
    background: Path | None = None,
    backgrounds: list | None = None,
    silence_drop_sec: float = 0.0,
    anim_seed: int = 0,
) -> Path | None:
    """Render a POV Reel via HyperFrames (HTML+GSAP, headless-browser rendering).

    Steps:
      1. Build the shared reel-data dict.
      2. Copy media assets next to the template.
      3. Render ``hyperframes/index.html`` from Jinja2.
      4. Run ``npx hyperframes render``.
      5. Return the output MP4 path.

    Returns ``None`` (never raises) if Node/HyperFrames is unavailable or the
    render fails, so callers can fall back to Remotion.
    """
    if output_path is None:
        output_path = REPO_ROOT / "output" / "hyperframes_reel.mp4"
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not _hyperframes_available():
        logger.warning("  [hyperframes] Node/HyperFrames not installed — skipping")
        return None

    # 1. Build canonical reel data
    payload = build_reel_data(
        hook=hook,
        quote=quote,
        attribution=attribution,
        cta=cta,
        mood=mood,
        duration=duration or 10.5,
        fps=fps,
        hook_voice=hook_voice,
        quote_voice=quote_voice,
        cta_voice=cta_voice,
        bridge_voice=bridge_voice,
        music_path=music_path,
        hook_words=hook_words,
        quote_words=quote_words,
        cta_words=cta_words,
        bridge=bridge,
        bridge_words=bridge_words,
        background=background,
        backgrounds=backgrounds,
        silence_drop_sec=silence_drop_sec,
        anim_seed=anim_seed,
    )

    # 2. Stage assets
    payload = _copy_assets(payload, ASSETS_DIR)

    # 3. Render Jinja → index.html
    try:
        _render_html(payload, BRIDGE_FILE)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"  [hyperframes] HTML render failed ({e}) — falling back")
        return None

    # 4. Invoke HyperFrames CLI
    cmd = ["npx", "hyperframes", "render"]
    logger.info(f"  [hyperframes] Rendering Reel ({payload.get('duration', 10.5):.1f}s, mood={mood})...")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(HYPERFRAMES_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"  [hyperframes] ⚠️ Render timed out after {timeout}s — falling back")
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"  [hyperframes] ⚠️ Render invocation failed: {e} — falling back")
        return None

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error")[-800:]
        logger.warning(f"  [hyperframes] ⚠️ Render failed — falling back:\n{err}")
        return None

    # HyperFrames writes to renders/ with a timestamp — find the newest MP4
    renders_dir = HYPERFRAMES_DIR / "renders"
    mp4s = sorted(renders_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mp4s:
        logger.warning("  [hyperframes] ⚠️ Render reported success but output missing — falling back")
        return None

    latest = mp4s[0]
    shutil.copy(latest, output_path)
    size = output_path.stat().st_size
    logger.info(f"  [hyperframes] Saved: {output_path} ({size / 1024:.0f} KB)")
    _loudnorm(output_path)
    return output_path
