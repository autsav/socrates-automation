# Socrates Instagram Pipeline

Automated daily philosophy Reels/carousels for Instagram.

## Publishing model (important)

The scheduled cron (`.github/workflows/daily_post.yml`) **auto-posts directly to Instagram** via the Graph API for all scheduled slots:

- **Reel slots** (03:00, 12:00, 21:00) run `python pipeline.py --remotion` — generates the Reel via Remotion + edge-tts and **posts directly to Instagram** via the Graph API.
- **Regular slots** (08:00, 15:00, 18:00) run `python pipeline.py --studio --remotion` — uses the AI Creative Studio to generate content and **posts directly to Instagram**.
- **Carousel slots** (Wed/Thu) run `python pipeline.py --carousel` and **auto-publish** via the Graph API.

The `--manual` flag is still available for local testing — it generates the asset and sends it to Telegram instead of posting, so you can manually upload with trending audio (the #1 Reels reach lever, which the Graph API cannot attach).

## Tests

Run with the 3.11 venv: `.venv/bin/python -m pytest`
(Two `tests/test_reel_composer.py` ffmpeg cases fail in environments without a
matching ffmpeg build — pre-existing, not regressions.)
