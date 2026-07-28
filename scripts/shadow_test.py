#!/usr/bin/env python3
"""Shadow test parity harness — render the same reel via Remotion AND HyperFrames,
compare duration/frames/color/audio, write report_NNN.json.

Usage:
    .venv/bin/python scripts/shadow_test.py \
        --content '{"hook":"...","quote":"...","cta":"...","mood":"dark_philosophical"}'

Output: output/shadow/report_NNN.json + side-by-side frame PNGs.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = REPO_ROOT / "output" / "shadow"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)


def _ffprobe_duration(path: Path) -> float | None:
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)], timeout=15)
    s = (r.stdout or "").strip()
    return round(float(s), 3) if r.returncode == 0 and s else None


def _extract_frame(video: Path, sec: float, out: Path) -> bool:
    r = _run([
        "ffmpeg", "-y", "-ss", str(sec), "-i", str(video),
        "-frames:v", "1", "-q:v", "2", str(out),
    ], timeout=30)
    return r.returncode == 0 and out.exists()


def _pixel_diff(a: Path, b: Path) -> float:
    """Return average per-channel diff % between two PNGs."""
    try:
        from PIL import Image
        im1 = Image.open(a).convert("RGB")
        im2 = Image.open(b).convert("RGB")
        if im1.size != im2.size:
            im2 = im2.resize(im1.size)
        total = 0
        count = 0
        for p1, p2 in zip(im1.getdata(), im2.getdata()):
            for c1, c2 in zip(p1, p2):
                total += abs(c1 - c2)
                count += 1
        return (total / count / 255) * 100 if count else 0
    except Exception:
        return 100.0


def _dominant_color(path: Path) -> tuple[int, int, int]:
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im = im.resize((100, 100))
        pixels = list(im.getdata())
        # Simple average
        r = sum(p[0] for p in pixels) // len(pixels)
        g = sum(p[1] for p in pixels) // len(pixels)
        b = sum(p[2] for p in pixels) // len(pixels)
        return (r, g, b)
    except Exception:
        return (0, 0, 0)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", required=True, help="JSON string with hook/quote/cta/mood")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    content = json.loads(args.content)
    mood = content.get("mood", "dark_philosophical")
    quote = content.get("quote", "Know thyself.")
    hook = content.get("hook", "This changed me.")
    cta = content.get("cta", "Save this.")
    attribution = content.get("attribution", "— Socrates")

    # Build a counter for this shadow run
    counter = 1
    while (args.out / f"report_{counter:03d}.json").exists():
        counter += 1
    run_dir = args.out / f"run_{counter:03d}"
    run_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "run_id": counter,
        "mood": mood,
        "quote": quote,
        "remotion": {},
        "hyperframes": {},
        "parity": {},
    }

    # ── Remotion render ────────────────────────────────────────────────────
    remotion_mp4 = run_dir / "remotion.mp4"
    try:
        from src.video.remotion_reel import generate_remotion_reel
        p = generate_remotion_reel(
            hook=hook, quote=quote, attribution=attribution, cta=cta,
            mood=mood, output_path=remotion_mp4, duration=10.5,
        )
        if p and p.exists():
            report["remotion"]["path"] = str(p)
            report["remotion"]["duration"] = _ffprobe_duration(p)
            report["remotion"]["size"] = p.stat().st_size
        else:
            report["remotion"]["error"] = "render returned None or missing"
    except Exception as e:
        report["remotion"]["error"] = str(e)

    # ── HyperFrames render ─────────────────────────────────────────────────
    hyper_mp4 = run_dir / "hyperframes.mp4"
    try:
        from src.video.hyperframes_reel import generate_hyperframes_reel
        p = generate_hyperframes_reel(
            hook=hook, quote=quote, attribution=attribution, cta=cta,
            mood=mood, output_path=hyper_mp4, duration=10.5,
        )
        if p and p.exists():
            report["hyperframes"]["path"] = str(p)
            report["hyperframes"]["duration"] = _ffprobe_duration(p)
            report["hyperframes"]["size"] = p.stat().st_size
        else:
            report["hyperframes"]["error"] = "render returned None or missing"
    except Exception as e:
        report["hyperframes"]["error"] = str(e)

    # ── Parity comparison ──────────────────────────────────────────────────
    r_dur = report["remotion"].get("duration")
    h_dur = report["hyperframes"].get("duration")
    if r_dur and h_dur:
        report["parity"]["duration_diff_ms"] = round(abs(r_dur - h_dur) * 1000, 1)

    # Extract 3 frames (first, middle, last) from each and compare
    frame_diffs = []
    if remotion_mp4.exists() and hyper_mp4.exists():
        r_dur = r_dur or 10.5
        h_dur = h_dur or 10.5
        for label, sec in [("first", 0.2), ("middle", r_dur / 2), ("last", r_dur - 0.2)]:
            r_png = run_dir / f"remotion_{label}.png"
            h_png = run_dir / f"hyperframes_{label}.png"
            if _extract_frame(remotion_mp4, sec, r_png) and _extract_frame(hyper_mp4, sec, h_png):
                diff = _pixel_diff(r_png, h_png)
                frame_diffs.append({"label": label, "diff_percent": round(diff, 2)})
        report["parity"]["frame_diffs"] = frame_diffs

    # Color parity
    if frame_diffs:
        first_r = run_dir / "remotion_first.png"
        first_h = run_dir / "hyperframes_first.png"
        if first_r.exists() and first_h.exists():
            rc = _dominant_color(first_r)
            hc = _dominant_color(first_h)
            report["parity"]["color_diff"] = {
                "remotion_rgb": rc,
                "hyperframes_rgb": hc,
                "channel_diffs": [abs(rc[i] - hc[i]) for i in range(3)],
            }

    # Audio parity (placeholder — would need more complex analysis)
    report["parity"]["audio"] = "not_implemented"

    # Write report
    report_path = args.out / f"report_{counter:03d}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Shadow report: {report_path}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
