#!/usr/bin/env python3
"""Studio mode — agent-driven hero reels via the /hyperframes skill.

Shells out to `claude --print` with the /hyperframes skill, isolated workdir,
30-min timeout, NO fallback. Manual trigger only — never cron.

Usage:
    .venv/bin/python scripts/studio_render.py \\
        --content '{"hook":"...","quote":"...","cta":"...","mood":"dark_philosophical"}' \\
        --vibe "dark cinematic, Netflix-investigation opening" \\
        --workflow faceless-explainer \\
        --out output/studio_001.mp4
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
STUDIO_DIR = REPO_ROOT / "hyperframes_studio"
DEFAULT_WORKFLOW = "faceless-explainer"


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def _build_prompt(quote_data: dict, vibe: str, workflow: str, out: Path) -> str:
    mood = quote_data.get("mood", "dark_philosophical")
    # Read mood palette from theme.ts (already synced to moods.css)
    # We inject the palette so the agent stays on-brand.
    palette = {
        "dark_philosophical": {"bg": ["#0a0805", "#2a1f12", "#0a0805"], "text": "#f5f0e8", "accent": "#c9a96e"},
        "dramatic_ancient": {"bg": ["#140a06", "#3a1d0f", "#140a06"], "text": "#fff8eb", "accent": "#dc5f32"},
        "cinematic_hopeful": {"bg": ["#060e18", "#153554", "#060e18"], "text": "#ffffff", "accent": "#64b4ff"},
        "stark_minimal": {"bg": ["#e6e6e6", "#f6f6f6", "#e6e6e6"], "text": "#141414", "accent": "#1e1e1e"},
        "epic_warrior": {"bg": ["#140808", "#3a120e", "#140808"], "text": "#fff5eb", "accent": "#dc3c28"},
        "mystical_greek": {"bg": ["#0a0618", "#2c1948", "#0a0618"], "text": "#f5f0ff", "accent": "#b478ff"},
        "calm_stoic": {"bg": ["#0e140f", "#233228", "#0e140f"], "text": "#fafaf5", "accent": "#8cbe8c"},
    }.get(mood, palette["dark_philosophical"])

    prompt = f"""Using /hyperframes and /{workflow}, create a 10-15 second reel from this philosophy content:

hook: "{quote_data.get('hook', '')}"
quote: "{quote_data.get('quote', '')}"
attribution: "{quote_data.get('attribution', '— Socrates')}"
cta: "{quote_data.get('cta', '')}"
mood: {mood}

Brand palette for this mood:
  bg outer: {palette['bg'][0]}
  bg core: {palette['bg'][1]}
  text: {palette['text']}
  accent: {palette['accent']}

Vibe direction: {vibe}

Requirements:
- 1080x1920 vertical format
- Use GSAP for all animations (seek-safe, paused timeline)
- Apply the brand palette — no off-brand colors
- One scene per beat: Hook → [Bridge] → Quote → CTA
- Word-by-word reveal animation for narration
- Subtle particle field + breathing vignette
- Film grain overlay for cinematic finish

Render the final MP4 to: {out}
"""
    return prompt


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", required=True, help="JSON string with hook/quote/cta/mood/attribution")
    parser.add_argument("--vibe", default="cinematic philosophy reel", help="Free-text vibe direction")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="HyperFrames workflow/skill")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "output" / f"studio_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
    parser.add_argument("--clean", action="store_true", help="Clear studio workdir before run")
    args = parser.parse_args()

    if not _claude_available():
        print("ERROR: `claude` CLI not on PATH. Install: https://claude.ai/code", file=sys.stderr)
        sys.exit(1)

    quote_data = json.loads(args.content)
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for f in STUDIO_DIR.iterdir():
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                shutil.rmtree(f)

    prompt = _build_prompt(quote_data, args.vibe, args.workflow, out)
    prompt_path = STUDIO_DIR / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    print(f"Studio workdir: {STUDIO_DIR}")
    print(f"Output target: {out}")
    print(f"Workflow: /{args.workflow}")
    print("-" * 40)

    result = subprocess.run(
        ["claude", "--print", "--allowedTools", "Bash,Read,Write,Edit", prompt],
        cwd=str(STUDIO_DIR),
        capture_output=True,
        text=True,
        timeout=1800,  # 30 min cap
    )

    transcript_path = out.parent / f"{out.stem}_transcript.txt"
    transcript_path.write_text(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}", encoding="utf-8")

    if result.returncode != 0:
        print(f"ERROR: Agent exited with code {result.returncode}", file=sys.stderr)
        print(f"Transcript saved: {transcript_path}", file=sys.stderr)
        sys.exit(1)

    if not out.exists():
        print(f"ERROR: Output MP4 not found at {out}", file=sys.stderr)
        print(f"Transcript saved: {transcript_path}", file=sys.stderr)
        sys.exit(1)

    # Verify with ffprobe
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out)],
        capture_output=True, text=True, timeout=15,
    )
    duration = (probe.stdout or "").strip()
    print(f"SUCCESS: {out} ({duration}s)")
    print(f"Transcript: {transcript_path}")


if __name__ == "__main__":
    main()
