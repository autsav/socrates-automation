"""
Batch POV Reel Generator — produces a week's worth of Reels in one run.

Reads unposted quotes from quotes.xlsx and generates up to `count` POV text
Reels (default 30 — enough for 4-5/day for a week) via
src.video.pov_reel_generator, saving them to output/pov_reels/.

Zero API cost: no FLUX, no TTS, ffmpeg + Pillow only.

Usage:
    python -m src.video.batch_generator --count 30

    from src.video.batch_generator import generate_batch
    paths = generate_batch(excel_path="quotes.xlsx", output_dir="output/pov_reels", count=30)
"""

from __future__ import annotations

from src.utils.logger import get_logger
logger = get_logger(__name__)

from pathlib import Path

import openpyxl

from src.core.excel_reader import AUDIENCE_TO_MOOD
from src.video.pov_reel_generator import generate_pov_reels

DEFAULT_EXCEL_PATH = "quotes.xlsx"
DEFAULT_OUTPUT_DIR = "output/pov_reels"
DEFAULT_COUNT = 30


def read_ready_quotes(excel_path: str | Path = DEFAULT_EXCEL_PATH, limit: int = DEFAULT_COUNT) -> list[dict]:
    """
    Read up to `limit` unposted, non-skipped quotes from quotes.xlsx.
    Returns dicts: row_number, quote, audience.
    """
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"quotes.xlsx not found at {path.absolute()}")

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb["Quotes"]

    ready = []
    for row in ws.iter_rows(min_row=2, values_only=False):
        row_num = row[0].value    # col A: #
        quote = row[1].value      # col B: Quote
        audience = row[2].value   # col C: Audience
        status = row[6].value     # col G: Status
        posted = row[7].value     # col H: Posted Date

        if not quote:
            continue
        if status and str(status).lower() == "skip":
            continue
        if posted:
            continue

        ready.append({
            "row_number": row_num,
            "quote": str(quote).strip(),
            "audience": str(audience).strip().lower() if audience else "stuck",
        })
        if len(ready) >= limit:
            break

    return ready


def generate_batch(
    excel_path: str | Path = DEFAULT_EXCEL_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    count: int = DEFAULT_COUNT,
) -> list[Path]:
    """
    Generate up to `count` POV Reels from the next unposted quotes in
    quotes.xlsx. Returns the list of successfully generated file paths.
    """
    quotes = read_ready_quotes(excel_path, limit=count)
    if not quotes:
        logger.info("  [batch] No ready quotes found in quotes.xlsx")
        return []

    logger.info(f"  [batch] Generating {len(quotes)} POV Reels from quotes.xlsx...")
    paths = generate_pov_reels(quotes, output_dir=output_dir, mood_map=AUDIENCE_TO_MOOD)

    _print_summary(quotes, paths, output_dir)
    return paths


def _print_summary(quotes: list[dict], paths: list, output_dir: str | Path) -> None:
    logger.info("\n" + "=" * 60)
    logger.info("  POV REEL BATCH GENERATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Requested:  {len(quotes)}")
    logger.info(f"  Generated:  {len(paths)}")
    logger.info(f"  Failed:     {len(quotes) - len(paths)}")
    logger.info(f"  Output dir: {Path(output_dir).resolve()}")
    logger.info(f"  ≈ {len(paths) / 5:.1f} days of content at 5/day, "
          f"{len(paths) / 4:.1f} days at 4/day")
    logger.info("-" * 60)
    for i, path in enumerate(paths[:10]):
        preview = quotes[i]["quote"][:50] if i < len(quotes) else ""
        logger.info(f"    {i + 1:>2}. {Path(path).name}  —  {preview}...")
    if len(paths) > 10:
        logger.info(f"    ... and {len(paths) - 10} more")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch-generate POV text Reels")
    parser.add_argument("--excel", default=DEFAULT_EXCEL_PATH, help="Path to quotes.xlsx")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Number of Reels to generate")
    args = parser.parse_args()

    generate_batch(excel_path=args.excel, output_dir=args.output_dir, count=args.count)
