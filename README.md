# Socrates Instagram Pipeline

Automated daily philosophy Reels/carousels for Instagram.

## Publishing model (important)

The scheduled cron (`.github/workflows/daily_post.yml`) generates content and sends it to Telegram for manual posting. This is intentional -- you need trending audio for reach, which the Graph API cannot attach.

- **Reel slots** (08:00, 18:00) run `python pipeline.py --studio --manual --remotion` — AI Creative Studio generates content, sends to Telegram.
- **POV Reel slot** (15:00) runs `python pipeline.py --manual --remotion` — zero-cost text Reel.
- **Carousel slots** (Wed/Thu) run `python pipeline.py --carousel` — auto-publishes via Graph API.

3 posts/day + 2 carousels (Wed/Thu) = quality over quantity.

## Content strategy (2026)

The pipeline uses a **confrontational, modern** content style:

- **Hooks**: Provocative, scroll-stopping, reference modern life (scrolling, 9-to-5, comfort zones)
- **Controversy Engine**: 3 modes — ROAST (Socrates roasts modern habits), VERDICT (What would Socrates say about [trend]?), DEBATE (bold claims that split the audience)
- **Visuals**: Photographic realism (not AI art) to avoid Instagram's AI content suppression
- **CTAs**: Confrontational engagement triggers that spark debate
- **Hashtags**: Data-driven, non-generic, no banned tags (#fyp, #viral, etc.)

## Tests

Run with the 3.11 venv: `.venv/bin/python -m pytest`
(Two `tests/test_reel_composer.py` ffmpeg cases fail in environments without a
matching ffmpeg build — pre-existing, not regressions.)
