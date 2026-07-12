# Socrates Instagram Pipeline

Automated daily philosophy Reels/carousels for Instagram.

## Publishing model (important)

Scheduled production runs `python pipeline.py --studio --manual`. **Manual mode
is intentional and is the default**: the pipeline generates the asset, sends it
to Telegram, and records it as `PENDING_MANUAL` — a human then uploads it so
they can add **trending audio** (the #1 Reels reach lever, which the Graph API
cannot attach).

The fully-automated Graph-API publish path (`src/core/instagram_poster.py`)
exists and is exercised by a contract test (`tests/test_publish_contract.py`),
but is **opt-in** — it runs only when a slot executes with `not dry_run and not
manual`. It is not used by the scheduled cron.

Manual posts are reconciled back to their real `post_id` by
`studio/reconcile.py`, which matches a stable hashtag token (`#sq…`) appended to
each caption, falling back to timestamp proximity if the caption was rewritten.

## Tests

Run with the 3.11 venv: `.venv/bin/python -m pytest`
(Two `tests/test_reel_composer.py` ffmpeg cases fail in environments without a
matching ffmpeg build — pre-existing, not regressions.)
