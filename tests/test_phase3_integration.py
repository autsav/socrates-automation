"""
Phase 3 Integration Tests — Scale (Points 11-15, 18-19, 26-27, 31-32, 37-41, 43, 45-54).
All tests must be importable without ffmpeg/fal.ai/GPU.
Run: python -m pytest test_phase3_integration.py -v
"""

import pytest
from pathlib import Path


# ── Points 11-15: Visual enhancements (image_composer) ───────────────────────

def test_point11_letterbox():
    """Point 11: Letterbox bars produce wider apparent aspect ratio."""
    from PIL import Image
    from src.visual.image_composer import add_letterbox_bars
    img = Image.new("RGB", (1080, 1920), color=(50, 50, 50))
    result = add_letterbox_bars(img, ratio=2.39)
    assert result.size == img.size, "Letterboxed image must keep original dimensions"
    top_pixel = result.getpixel((540, 5))
    assert top_pixel[:3] == (0, 0, 0), f"Top bar not black: {top_pixel}"


def test_point12_gradient_mesh():
    """Point 12: Gradient mesh background generation produces valid image."""
    from src.visual.image_composer import generate_gradient_mesh_bg
    img = generate_gradient_mesh_bg(mood="dark_philosophical", size=(1080, 1920), seed=42)
    assert img.size == (1080, 1920)
    assert img.mode in ("RGB", "RGBA")


def test_point13_qr_placeholder():
    """Point 13: QR placeholder adds to image without external library."""
    from PIL import Image
    from src.visual.image_composer import add_qr_to_image
    img = Image.new("RGB", (1080, 1920), color=(30, 30, 30))
    result = add_qr_to_image(img, url="https://example.com/socrates", position="bottom_right", size=150)
    assert result.size == img.size


def test_point14_seasonal_palette():
    """Point 14: Seasonal palette override returns valid colour dict."""
    from src.visual.brand_design import get_seasonal_palette, get_season
    season = get_season()
    assert season in ("spring", "summer", "autumn", "winter")
    palette = get_seasonal_palette("dark_philosophical")
    assert "primary" in palette or isinstance(palette, dict)


def test_point15_border():
    """Point 15: Border styles produce same-size image."""
    from PIL import Image
    from src.visual.image_composer import add_border, BORDER_STYLES
    img = Image.new("RGB", (1080, 1920), color=(20, 20, 20))
    for style in list(BORDER_STYLES.keys())[:3]:
        result = add_border(img, style=style, margin=30)
        assert result.size == img.size, f"Border style {style!r} changed size"


# ── Point 18: Waveform overlay (reel_composer) ───────────────────────────────

def test_point18_waveform_param():
    """Point 18: waveform_overlay parameter accepted by generate_reel signature."""
    import inspect
    from src.video.reel_composer import generate_reel
    sig = inspect.signature(generate_reel)
    assert "waveform_overlay" in sig.parameters


# ── Point 19: Jingle generation ──────────────────────────────────────────────

def test_point19_jingle_param():
    """Point 19: use_jingle parameter accepted by generate_reel."""
    import inspect
    from src.video.reel_composer import generate_reel
    sig = inspect.signature(generate_reel)
    assert "use_jingle" in sig.parameters


def test_point19_generate_jingle_callable():
    """Point 19: generate_jingle() function is importable."""
    from src.video.reel_composer import generate_jingle
    assert callable(generate_jingle)


# ── Point 26: BTS content ─────────────────────────────────────────────────────

def test_point26_bts_caption():
    """Point 26: BTS caption contains process description."""
    from src.content.content_formats import generate_bts_caption
    cap = generate_bts_caption(
        quote="The unexamined life is not worth living",
        philosopher="Socrates",
        flux_prompt="ancient ruins at sunset",
        mood="dark_philosophical",
    )
    assert "Behind the scenes" in cap
    assert "Socrates" in cap
    assert "ffmpeg" in cap.lower() or "pipeline" in cap.lower()


# ── Point 27: Poll/Quiz interactions ─────────────────────────────────────────

def test_point27_poll_caption():
    """Point 27: Poll caption returns options + CTA."""
    from src.content.content_formats import generate_poll_caption
    cap = generate_poll_caption(quote="Know thyself", seed=0)
    assert "A:" in cap or "a:" in cap.lower()
    assert len(cap) > 20


# ── Point 31: Repost strategy ────────────────────────────────────────────────

def test_point31_top_performers_callable():
    """Point 31: get_top_performers() importable from src.core.data_store."""
    from src.core.data_store import get_top_performers
    assert callable(get_top_performers)


def test_point31_remix_due_callable():
    """Point 31: get_posts_due_for_remix() importable from src.core.data_store."""
    from src.core.data_store import get_posts_due_for_remix
    assert callable(get_posts_due_for_remix)


# ── Point 32: Micro-moment audience ──────────────────────────────────────────

def test_point32_micro_moment():
    """Point 32: pick_micro_moment_audience returns valid audience strings."""
    from src.analytics.ab_test import pick_micro_moment_audience
    valid = {"procrastinator", "stuck", "doomscroller", "overwhelmed", "quitter", "lost", "lazy"}
    for day in range(7):
        result = pick_micro_moment_audience(weekday=day)
        assert result in valid, f"Unexpected audience {result!r} for day {day}"


# ── Point 37: Engagement pod ─────────────────────────────────────────────────

def test_point37_pod_callable():
    """Point 37: save_engagement_pod_member and get_engagement_pod importable."""
    from src.core.data_store import save_engagement_pod_member, get_engagement_pod
    assert callable(save_engagement_pod_member)
    assert callable(get_engagement_pod)


# ── Point 38: Bio link rotation ──────────────────────────────────────────────

def test_point38_bio_link_notifier():
    """Point 38: notify_bio_link_rotation method on Notifier."""
    from src.core.notifier import Notifier
    assert hasattr(Notifier, "notify_bio_link_rotation")


# ── Point 39: Highlight strategy ─────────────────────────────────────────────

def test_point39_highlight_notifier():
    """Point 39: notify_highlight_category method on Notifier."""
    from src.core.notifier import Notifier
    assert hasattr(Notifier, "notify_highlight_category")


# ── Point 40: Contest tracking ───────────────────────────────────────────────

def test_point40_contest_callable():
    """Point 40: contest tracking functions importable from src.core.data_store."""
    from src.core.data_store import save_contest_participant, get_weekly_contest_participants
    assert callable(save_contest_participant)
    assert callable(get_weekly_contest_participants)


# ── Point 41: Cohort analysis ────────────────────────────────────────────────

def test_point41_cohort_by_slot():
    """Point 41: get_optimal_posting_window importable from src.analytics.cohort_analysis."""
    from src.analytics.cohort_analysis import get_optimal_posting_window
    assert callable(get_optimal_posting_window)


# ── Point 43: Competitor benchmarking ────────────────────────────────────────

def test_point43_competitor_benchmark():
    """Point 43: generate_benchmark_prompt returns expected handles."""
    from src.analytics.competitor import generate_benchmark_prompt
    prompt = generate_benchmark_prompt(our_followers=5000, our_avg_likes=300)
    assert "dailystoic" in prompt
    assert "COMPETITOR" in prompt


def test_point43_competitor_snapshot_callable():
    """Point 43: save_competitor_snapshot importable."""
    from src.analytics.competitor import save_competitor_snapshot
    assert callable(save_competitor_snapshot)


# ── Point 45: Comment sentiment ──────────────────────────────────────────────

def test_point45_classify_positive():
    from src.analytics.sentiment import classify_comment
    assert classify_comment("This is amazing and so true!") == "positive"


def test_point45_classify_fire():
    from src.analytics.sentiment import classify_comment
    assert classify_comment("🔥🔥🔥") == "fire"


def test_point45_classify_negative():
    from src.analytics.sentiment import classify_comment
    assert classify_comment("I totally disagree with this") == "negative"


def test_point45_classify_question():
    from src.analytics.sentiment import classify_comment
    assert classify_comment("What does this even mean?") == "question"


def test_point45_analyse_batch():
    from src.analytics.sentiment import analyse_comments
    comments = [
        "🔥 fire content",
        "I disagree",
        "What does this mean?",
        "This is amazing",
        "neutral comment here",
    ]
    result = analyse_comments(comments)
    assert result["total"] == 5
    assert result["fire"] >= 1
    assert result["positivity_rate"] >= 0


def test_point45_sentiment_report():
    from src.analytics.sentiment import sentiment_report
    r = sentiment_report("post_123", ["Amazing!", "🔥", "Why?"])
    assert r["post_id"] == "post_123"
    assert r["comment_count"] == 3
    assert "top_sentiment" in r


# ── Point 46: 60fps parameter ────────────────────────────────────────────────

def test_point46_fps_param():
    """Point 46: fps parameter accepted by generate_reel."""
    import inspect
    from src.video.reel_composer import generate_reel
    sig = inspect.signature(generate_reel)
    assert "fps" in sig.parameters
    assert sig.parameters["fps"].default == 30


# ── Point 47: HDR grading wired ──────────────────────────────────────────────

def test_point47_hdr_grade_in_source():
    """Point 47: HDR curves filter string present in reel_composer.py."""
    src = Path(__file__).parent.parent / "src" / "video" / "reel_composer.py"
    assert "curves" in src.read_text(), "HDR curves filter not found in reel_composer.py"


# ── Point 49: Motion blur transitions ────────────────────────────────────────

def test_point49_tblend_in_source():
    """Point 49: tblend motion blur applied in reel_composer.py."""
    src = Path(__file__).parent.parent / "src" / "video" / "reel_composer.py"
    assert "tblend" in src.read_text(), "tblend motion blur not found in reel_composer.py"


# ── Point 50: A/B variant generation ─────────────────────────────────────────

def test_point50_ab_variants():
    from src.visual.export_formats import generate_caption_variants
    v = generate_caption_variants("Know thyself", "You're lying to yourself", seed=10)
    assert "variant_a" in v and "variant_b" in v
    assert v["variant_a"] != v["variant_b"]
    assert "Know thyself" in v["variant_a"]


# ── Point 51: TikTok format ───────────────────────────────────────────────────

def test_point51_tiktok_caption():
    from src.visual.export_formats import get_tiktok_caption
    cap = get_tiktok_caption("Know thyself", "Socrates", "Stop lying to yourself")
    assert "#fyp" in cap
    assert "Socrates" in cap


def test_point51_export_callable():
    from src.visual.export_formats import export_for_tiktok
    assert callable(export_for_tiktok)


# ── Point 52: YouTube Shorts format ──────────────────────────────────────────

def test_point52_yt_shorts_metadata():
    from src.visual.export_formats import get_youtube_shorts_metadata
    meta = get_youtube_shorts_metadata("Know thyself", "Socrates", "Stop lying to yourself")
    assert "#Shorts" in meta["description"]
    assert len(meta["title"]) <= 100


def test_point52_export_callable():
    from src.visual.export_formats import export_for_youtube_shorts
    assert callable(export_for_youtube_shorts)


# ── Point 54: Telegram channel expansion ─────────────────────────────────────

def test_point54_telegram_channel_notifier():
    from src.core.notifier import Notifier
    assert hasattr(Notifier, "notify_telegram_channel_post")
