#!/usr/bin/env python3
"""Quick smoke test: render hyperframes/templates/index.html.j2 with fixture data
and run `npx hyperframes render` to produce an MP4.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def main() -> None:
    repo = Path(__file__).parent.parent
    templates_dir = repo / "hyperframes" / "templates"
    out_dir = repo / "hyperframes" / "out"
    out_dir.mkdir(exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("index.html.j2")

    reel_data = {
        "hook": "This changed me.",
        "quote": "Know thyself.",
        "attribution": "— Socrates",
        "cta": "Save this.",
        "mood": "dark_philosophical",
        "duration": 10.5,
        "fps": 30,
        "animSeed": 0,
        "sceneFrames": {"total": 10.5, "hook": 2.45, "bridge": 0, "quote": 4.2, "cta": 1.8},
        "voices": {},
        "wordTimes": {},
        "music": None,
    }

    html = template.render(
        **reel_data,
        reel_data=reel_data,
    )

    html_path = repo / "hyperframes" / "index.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"Rendered test HTML -> {html_path}")

    # Run HyperFrames render
    result = subprocess.run(
        ["npx", "hyperframes", "render"],
        cwd=str(repo / "hyperframes"),
        capture_output=True,
        text=True,
        timeout=120,
    )
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("Return code:", result.returncode)

    # HyperFrames writes to renders/ with a timestamp
    renders_dir = repo / "hyperframes" / "renders"
    mp4s = sorted(renders_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if mp4s:
        mp4 = mp4s[0]
        size = mp4.stat().st_size
        print(f"MP4 exists: {mp4} ({size} bytes)")
    else:
        print("MP4 NOT found")
        sys.exit(1)


if __name__ == "__main__":
    main()
