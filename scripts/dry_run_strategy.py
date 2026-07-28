#!/usr/bin/env python
"""Manual dry-run of --strategy path. Saves sidecar JSON for human review.
No render, no post. Use to evaluate Opus social_strategist output quality
on real trends before flipping a cron slot.

Usage:
  .venv/bin/python scripts/dry_run_strategy.py
  .venv/bin/python scripts/dry_run_strategy.py --trend "Marcus Aurelius on doomscrolling"

Output:
  content/strategy/<YYYY-MM-DD>/<slug>.json  (sidecar; gitignored)
  stdout preview
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import Pipeline


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() or c == "-" else "-" for c in text.lower())[:50]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trend", help="Override trend headline (else auto-fetched)")
    args = ap.parse_args()

    p = Pipeline.from_args(argparse.Namespace(strategy=True, trend=args.trend))
    quote_data = p._build_quote_data_for_dry_run(args.trend)
    if not quote_data:
        print("dry-run failed at orchestrator level", file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    slug = _slug(quote_data.get("hook", "untitled"))
    out_dir = Path("content/strategy") / today
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.json"
    out_path.write_text(json.dumps(quote_data, indent=2))
    print(f"\nSaved → {out_path}\n")
    print(json.dumps(quote_data, indent=2))


if __name__ == "__main__":
    main()
