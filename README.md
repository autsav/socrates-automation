# Socrates Instagram Pipeline

Automated daily philosophy Reels/carousels for Instagram.

## Publishing model (important)

The scheduled cron (`.github/workflows/daily_post.yml`) posts in two modes:

- **Reel / regular slots** run `python pipeline.py --manual …` — **manual mode
  is intentional and is the default for these slots**: the pipeline generates
  the asset, sends it to Telegram, and records it as `PENDING_MANUAL`. A human
  then uploads it so they can add **trending audio** (the #1 Reels reach lever,
  which the Graph API cannot attach).
- **Carousel slots** (Wed/Thu) run `python pipeline.py --carousel` with no
  `--manual`, so they **auto-publish** via the Graph API
  (`src/core/instagram_poster.py`) unattended.

So the Graph-API publish path (`post_to_instagram` / `post_reel_to_instagram` /
`post_carousel_to_instagram`) does run in production for carousels, and runs for
any slot executed with `not dry_run and not manual`. It is guarded by a contract
test (`tests/test_publish_contract.py`) so it cannot silently rot.

Manual posts are reconciled back to their real `post_id` by
`studio/reconcile.py`, which matches a stable hashtag token (`#sq…`) appended to
each caption, falling back to timestamp proximity if the caption was rewritten.

## Tests

Run with the 3.11 venv: `.venv/bin/python -m pytest`
(Two `tests/test_reel_composer.py` ffmpeg cases fail in environments without a
matching ffmpeg build — pre-existing, not regressions.)
