"""
Socrates Instagram Automation Pipeline — HYBRID MODE
Quote + Caption: Excel file (FREE)
Image mood:      Claude Haiku (£0.001/call)
Background:      Fal.ai FLUX (~£0.003/image)
Compose:         Pillow (free)
Host:            Cloudinary (free)
Post:            Meta Graph API (free)
Scheduler:       GitHub Actions (free)

Total: ~£0.17/month
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from excel_reader import read_todays_quote, get_mood_prompt, mark_as_posted, _current_slot
from image_generator import generate_background
from image_composer import compose_post, compose_hook_scene, compose_quote_scene, compose_cta_scene
from instagram_poster import post_to_instagram, post_reel_to_instagram
from reel_composer import generate_reel, ffmpeg_available
from config import Config
from data_store import init_db, save_post, mark_posted, get_ab_results, has_posted_today
from ab_test import pick_caption_variant, pick_mood, pick_optimal_slot
from token_manager import get_valid_token_with_fallback
from notifier import Notifier
from trending_music import get_trending_suggestion
from voiceover import prepare_reel_voiceover, voiceover_available

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
LOG_DIR = PROJECT_ROOT / "logs"
OUTPUT_DIR = PROJECT_ROOT / "output"
EXCEL_PATH = PROJECT_ROOT / "quotes.xlsx"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pipeline.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def _extract_hook(caption: str, max_chars: int = 60) -> str:
    """Extract a short scroll-stopping hook from the caption.
    Strips emoji prefixes and finds the first real sentence."""
    import re
    cleaned = re.sub(r"^[\s\U0001F300-\U0001F9FF\U0001FA00-\U0001FA9F\u2600-\u26FF\u2700-\u27BF]+", "", caption)
    for delim in (".", "!", "?"):
        if delim in cleaned:
            first = cleaned.split(delim)[0].strip()
            if first and len(first) > 10:
                break
    else:
        first = cleaned.split("\n\n")[0].strip()

    if len(first) <= max_chars:
        return first
    truncated = first[:max_chars]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + "..."


# ── Psychology-driven hook templates (Scene 1 of Reel) ───────────────────────
# Research: viewers decide in 2.5-3.5s. These formulas exploit:
#   - Curiosity gap (brain wants to resolve open questions)
#   - Pattern interrupt (breaks autopilot scrolling)
#   - Confrontational/identity challenge (forces self-reflection)
#   - "Most people" frame (social proof + exclusivity)

_PSYCHOLOGY_HOOKS = {
    "procrastinator": [
        "You already know what you need to do.",
        "Stop waiting to feel ready.",
        "The version of you that starts today wins.",
        "What if waiting IS the mistake?",
        "You\'ve delayed this long enough.",
    ],
    "doomscroller": [
        "You scrolled past 3 things that mattered today.",
        "The algorithm is not on your side.",
        "What are you actually looking for right now?",
        "This is the only thing worth stopping for.",
        "Put the phone down after this.",
    ],
    "stuck": [
        "Being stuck is a choice. Here\'s proof.",
        "Every person who changed their life felt exactly like you.",
        "What if you\'re not stuck — just afraid?",
        "The door was never locked.",
        "Stuck isn\'t permanent. Giving up is.",
    ],
    "lazy": [
        "Motivation is a lie. This is what actually works.",
        "You don\'t need to feel like it.",
        "One minute. That\'s all this takes.",
        "Action first. Feeling follows.",
        "The person you want to be started yesterday.",
    ],
    "quitter": [
        "Most people quit 3 feet from gold.",
        "What if today is the day it turns?",
        "Every comeback started with a choice to try again.",
        "The difference between you and them: they didn\'t stop.",
        "This is what Socrates said about giving up.",
    ],
    "lost": [
        "Not all who wander are lost. But some are.",
        "The question you\'re avoiding is the answer.",
        "What do you actually want?",
        "Purpose doesn\'t find you. You find it.",
        "Being lost is the first step to being found.",
    ],
    "overwhelmed": [
        "You don\'t have to do it all today.",
        "One thing. Just one.",
        "Overwhelm is a sign you care. Here\'s what to do with it.",
        "You are not behind. You are right on time.",
        "Breathe. Then read this.",
    ],
}

_FALLBACK_HOOKS = [
    "Socrates said something that will bother you all day.",
    "Ancient wisdom. Modern problem. Same answer.",
    "2,400 years old. Still the most relevant thing you\'ll read today.",
    "Most people will scroll past this. Don\'t.",
    "This quote lives rent-free in my head.",
]


# ── Controversy questions — drives comments via binary debate ─────────────────
# Psychology: binary opinion questions generate 4-7x more comments than generic CTAs.
# Formats: "Agree or disagree:", "Hot take:", "Unpopular opinion:" all force a reaction.

_CONTROVERSY_QUESTIONS = {
    "procrastinator": [
        "Agree or disagree: Waiting is just fear with better excuses.",
        "Hot take: Procrastination is a choice, not a personality trait.",
        "Unpopular opinion: Laziness doesn't exist. Only misaligned priorities.",
        "Agree or disagree: If you really wanted it, you'd have started already.",
    ],
    "doomscroller": [
        "Agree or disagree: Social media is designed to make you feel inferior.",
        "Hot take: Your phone is not the problem. Your discipline is.",
        "Unpopular opinion: Most people are addicted and won't admit it.",
        "Agree or disagree: You are being manipulated right now.",
    ],
    "stuck": [
        "Hot take: Being stuck is comfortable. That's the real problem.",
        "Agree or disagree: Change is always possible. Most people just won't pay the price.",
        "Unpopular opinion: You're not stuck. You're just scared.",
        "Agree or disagree: The life you want is on the other side of one hard decision.",
    ],
    "lazy": [
        "Hot take: There is no such thing as a lazy person. Only wrong goals.",
        "Agree or disagree: Discipline is a muscle. You've just stopped training it.",
        "Unpopular opinion: You already know what to do. You just don't want to do it.",
        "Agree or disagree: Action creates motivation, not the other way around.",
    ],
    "quitter": [
        "Hot take: Most people quit right before their breakthrough.",
        "Agree or disagree: Quitting is never the right answer — change strategy, not the goal.",
        "Unpopular opinion: Every time you quit, it gets easier to quit next time.",
        "Agree or disagree: The version of you that never gave up is still possible.",
    ],
    "lost": [
        "Hot take: You're not lost. You're avoiding the answer you already know.",
        "Agree or disagree: Most people know their purpose. They just fear it.",
        "Unpopular opinion: Feeling lost is a luxury. Most people are too busy surviving.",
        "Agree or disagree: Purpose is found through action, not reflection.",
    ],
    "overwhelmed": [
        "Hot take: You're overwhelmed by too little clarity, not too much to do.",
        "Agree or disagree: Saying yes to everything is saying no to yourself.",
        "Unpopular opinion: Burnout is a warning, not a badge of honour.",
        "Agree or disagree: The most productive thing you can do right now is rest.",
    ],
}

_FALLBACK_CONTROVERSY = [
    "Hot take: Socrates would say most people are sleepwalking through life.",
    "Agree or disagree: Ancient wisdom > modern self-help.",
    "Unpopular opinion: Most people know the answer. They just won't act.",
    "Agree or disagree: The unexamined life is the default, not the exception.",
]


def _pick_controversy(audience: str, row_number: int) -> str:
    """
    Pick a polarising debate question for the image controversy bar + caption.
    Rotates deterministically so every post has a different angle.
    """
    pool = _CONTROVERSY_QUESTIONS.get(audience, _FALLBACK_CONTROVERSY)
    return pool[row_number % len(pool)]



def _generate_psychology_hook(audience: str, row_number: int) -> str:
    """
    Pick a psychology-driven hook for Reel Scene 1.
    Rotates deterministically through the audience-specific pool.
    Research: confrontational + curiosity-gap hooks have highest 3s hold rates.
    """
    pool = _PSYCHOLOGY_HOOKS.get(audience, _FALLBACK_HOOKS)
    return pool[row_number % len(pool)]


# ── Dynamic CTA, emoji, and hashtag enhancers ─────────────────────────────────

# Share-optimised CTAs — research: shares are the #1 viral signal on Instagram 2026.
# Mix of share (DM/Story), save, and comment triggers for algorithmic diversity.
_CTA_VARIANTS = [
    "Send this to someone who needs to hear it today.",        # share → DM
    "Share this to your Story before you forget it.",          # share → Story
    "Tag the person this made you think of.",                  # share → tag
    "Save this. You will need it again.",                      # save
    "Which line hit hardest? Tell me in the comments.",        # comment
    "Send this to your group chat. One of them needs it.",     # share → DM
    "Screenshot the line that hurts most.",                    # save
    "Share to your Story if this is exactly what you needed.", # share → Story
]

_AUDIENCE_EMOJIS = {
    "procrastinator": "⏳",
    "doomscroller":   "📱",
    "stuck":          "🚪",
    "lazy":           "🛋️",
    "quitter":        "🏔️",
    "lost":           "🧭",
    "overwhelmed":    "🌊",
}

_MOOD_EMOJIS = {
    "dark_philosophical": "🌑",
    "dramatic_ancient":   "🏛️",
    "cinematic_hopeful":  "🌅",
    "stark_minimal":      "⚪",
    "epic_warrior":       "⚔️",
    "mystical_greek":     "✨",
    "calm_stoic":         "🌿",
}

_HASHTAG_POOL = {
    "procrastinator": ["#StopProcrastinating", "#TakeAction", "#SelfDiscipline", "#DoItNow", "#NoMoreExcuses"],
    "doomscroller":   ["#DigitalDetox", "#MindfulScrolling", "#BreakTheLoop", "#PresentMoment", "#ScreenTimeAwareness"],
    "stuck":          ["#GetUnstuck", "#KeepMoving", "#EmbraceChange", "#NewBeginnings", "#CourageToStart"],
    "lazy":           ["#BeatLaziness", "#SmallSteps", "#JustStart", "#DisciplineEqualsFreedom", "#NoZeroDays"],
    "quitter":        ["#NeverGiveUp", "#Resilience", "#StayStrong", "#PushThrough", "#YouGotThis"],
    "lost":           ["#FindYourPath", "#SelfDiscovery", "#InnerJourney", "#PurposeDriven", "#KnowThyself"],
    "overwhelmed":    ["#Breathe", "#MentalHealthMatters", "#SlowDown", "#OneStepAtATime", "#SelfCareFirst"],
}

_BASE_HASHTAGS = ["#Stoicism", "#PhilosophyQuotes", "#MindsetShift", "#AncientWisdom", "#DailyStoic"]


def _pick_cta(row_number: int) -> str:
    """Deterministically rotate CTA variants based on row number."""
    return _CTA_VARIANTS[row_number % len(_CTA_VARIANTS)]


def _add_emojis(audience: str, mood: str) -> str:
    """Return 2–3 contextual emojis for the caption."""
    aud_emoji = _AUDIENCE_EMOJIS.get(audience, "💡")
    mood_emoji = _MOOD_EMOJIS.get(mood, "🔥")
    return f"{aud_emoji} {mood_emoji}"


def _generate_hashtags(audience: str, mood: str, max_tags: int = 8) -> str:
    """Build a hashtag string mixing base + audience-specific tags."""
    tags = _BASE_HASHTAGS[:3]
    audience_tags = _HASHTAG_POOL.get(audience, [])
    # Pick 2 audience tags deterministically using mood hash for variety
    if audience_tags:
        idx = hash(mood) % len(audience_tags)
        tags.append(audience_tags[idx])
        tags.append(audience_tags[(idx + 1) % len(audience_tags)])
    # Add 2 mood-related tags
    mood_tags = [f"#{mood.replace('_', '').title()}", "#StoicWisdom"]
    tags.extend(mood_tags)
    return " ".join(tags[:max_tags])


def _viral_first_line(audience: str, row_number: int) -> str:
    """
    Build a viral first line for the caption.
    This is what shows in the feed BEFORE "more" is tapped — critical for stops.
    Uses the same psychology-hook pool as Scene 1 but picks the NEXT variant
    so the caption and reel hook feel fresh but thematically linked.
    """
    pool = _PSYCHOLOGY_HOOKS.get(audience, _FALLBACK_HOOKS)
    # Offset by 1 from Scene 1 hook so they don't duplicate
    return pool[(row_number + 1) % len(pool)]


def _enhance_caption(caption: str, audience: str, mood: str, row_number: int, controversy: str = "") -> str:
    """
    Enhance a caption with:
    - Viral first line (shown in feed preview — must stop the scroll)
    - Dynamic CTA replacement with share-optimised variants
    - Controversy question (drives comments — binary debate trigger)
    - Emoji prefix
    - Strategic line breaks
    - Hashtag block
    """
    # Split into parts: hook/story/quote/cta
    parts = caption.split("\n\n")
    if not parts:
        parts = [caption]

    # Replace the last part (CTA) if it looks like our template
    cta = _pick_cta(row_number)
    last = parts[-1].strip()
    if any(w in last.lower() for w in ("save", "read", "comment", "tag", "send", "share", "screenshot")):
        parts[-1] = cta
    else:
        parts.append(cta)

    # Rebuild with line breaks
    body = "\n\n".join(parts)

    # Add viral first line at the very top (shown in feed before "more")
    first_line = _viral_first_line(audience, row_number)
    emojis = _add_emojis(audience, mood)
    enhanced = f"{first_line}\n\n{emojis}\n\n{body}"

    # Add controversy question — drives comments via binary debate
    # Placed just before hashtags so it's the last thing read before they scroll on
    if controversy:
        enhanced = f"{enhanced}\n\n💬 {controversy}"

    # Add hashtags at the bottom
    hashtags = _generate_hashtags(audience, mood)
    enhanced = f"{enhanced}\n\n{hashtags}"

    return enhanced


def save_log(data: dict):
    log_path = LOG_DIR / "posts.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(data) + "\n")


def run_pipeline(dry_run: bool = False, reel: bool = False, manual: bool = False):
    cfg = Config()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log.info(f"▶ HYBRID Pipeline start | dry_run={dry_run} reel={reel} manual={manual}")

    # Initialize SQLite state store
    init_db()

    # Get valid Meta token (auto-refreshes if needed)
    access_token = get_valid_token_with_fallback(cfg)

    # ── Pre-flight guard: skip if this slot already posted today ──────────────
    slot = _current_slot()
    if has_posted_today(slot):
        log.info(f"⏭ Slot {slot} already posted today — skipping")
        return {"skipped": True, "reason": f"slot {slot} already posted today"}

    # ── Step 1: Read quote from Excel (FREE) ──────────────────────────────────
    log.info("Step 1/5: Reading quote from Excel...")
    quote_data = read_todays_quote(EXCEL_PATH, api_key=cfg.ANTHROPIC_API_KEY)
    log.info(f"Quote:    {quote_data['quote'][:60]}...")
    log.info(f"Audience: {quote_data['audience']}")
    log.info(f"Row:      {quote_data['row_number']}")

    # ── Step 0: A/B Test Selection ────────────────────────────────────────────
    log.info("Step 0: A/B test selection...")
    caption_variant = pick_caption_variant(quote_data["audience"], get_ab_results=get_ab_results)
    mood = pick_mood(quote_data["audience"], quote_data["quote"], get_ab_results=get_ab_results)
    log.info(f"Slot: {slot}, Variant: {caption_variant}, Mood: {mood}")

    # Pick caption variant
    chosen_caption = quote_data.get("caption_b") if caption_variant == 1 else quote_data["caption"]
    quote_data["caption"] = chosen_caption

    # Pick controversy question — drives comments on image and in caption
    controversy = _pick_controversy(quote_data["audience"], quote_data["row_number"])
    log.info(f"  Controversy: {controversy[:60]}")

    # Enhance caption with emojis, dynamic CTA, controversy, hashtags, formatting
    enhanced_caption = _enhance_caption(
        chosen_caption,
        audience=quote_data["audience"],
        mood=mood,
        row_number=quote_data["row_number"],
        controversy=controversy,
    )
    quote_data["caption"] = enhanced_caption
    log.info(f"  Caption enhanced ({len(enhanced_caption)} chars)")

    # ── Step 2: Get image mood from Claude Haiku (TINY call) ──────────────────
    log.info("Step 2/5: Getting image mood from Claude Haiku...")
    if not mood:
        mood = get_mood_prompt(
            quote=quote_data["quote"],
            audience=quote_data["audience"],
            api_key=cfg.ANTHROPIC_API_KEY,
        )
    log.info(f"Mood: {mood}")

    # ── Step 3: Generate background image via Fal.ai ─────────────────────────
    log.info("Step 3/5: Generating background via Fal.ai...")
    image_path = generate_background(
        mood=mood,
        api_key=cfg.FAL_API_KEY,
        output_dir=OUTPUT_DIR,
        quote=quote_data["quote"],
        anthropic_api_key=cfg.ANTHROPIC_API_KEY,
    )
    log.info(f"Background: {image_path}")

    # ── Step 4: Compose final post image ──────────────────────────────────────
    log.info("Step 4/5: Composing post image...")
    final_image_path = compose_post(
        background_path=image_path,
        quote=quote_data["quote"],
        attribution="— Socrates",
        output_dir=OUTPUT_DIR,
        timestamp=timestamp,
        quote_source=quote_data.get("source", "socrates"),
        controversy_text=controversy,
    )
    log.info(f"Final image: {final_image_path}")

    # ── Save to SQLite state store ────────────────────────────────────────────
    post_row_id = save_post(
        quote_text=quote_data["quote"],
        audience=quote_data["audience"],
        mood=mood,
        caption_variant=caption_variant,
        posting_slot=slot,
        dry_run=dry_run,
    )

    # ── Step 5: Generate Reel (if reel mode or dry-run) ───────────────────────
    reel_path = None
    if reel or (dry_run and ffmpeg_available()):
        log.info(f"Step 5/6: {'Generating Reel' if reel else 'Testing'} reel generation...")

        # Extract hook text from caption for Scene 1
        # Psychology-driven hook: audience-specific pattern interrupt
        # Research: confrontational/curiosity-gap hooks have highest 3s hold rates
        hook_text = _generate_psychology_hook(quote_data["audience"], quote_data["row_number"])
        log.info(f"  Hook: {hook_text[:50]}...")

        # Generate 2 backgrounds for visual variety
        log.info("  Generating background 1 (hook scene)...")
        bg_hook_path = generate_background(
            mood=mood,
            api_key=cfg.FAL_API_KEY,
            output_dir=OUTPUT_DIR,
            quote=quote_data["quote"],
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
        )
        log.info("  Generating background 2 (quote scene)...")
        bg_quote_path = generate_background(
            mood=mood,
            api_key=cfg.FAL_API_KEY,
            output_dir=OUTPUT_DIR,
            quote=quote_data["quote"],
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
        )
        log.info("  Generating background 3 (CTA scene)...")
        bg_cta_path = generate_background(
            mood=mood,
            api_key=cfg.FAL_API_KEY,
            output_dir=OUTPUT_DIR,
            quote=quote_data["quote"],
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
        )

        # Compose 3 vertical scenes
        log.info("  Composing scenes...")
        scene_hook = compose_hook_scene(
            background_path=bg_hook_path,
            hook_text=hook_text,
            output_dir=OUTPUT_DIR,
            timestamp=timestamp,
            controversy_text=controversy,
        )
        scene_quote = compose_quote_scene(
            background_path=bg_quote_path,
            quote=quote_data["quote"],
            attribution="— Socrates",
            output_dir=OUTPUT_DIR,
            timestamp=timestamp
        )
        scene_cta = compose_cta_scene(
            background_path=bg_cta_path,
            output_dir=OUTPUT_DIR,
            timestamp=timestamp
        )

        # ── Generate voiceover narration ──────────────────────────────────────
        voiceover = None
        if voiceover_available(cfg.ANTHROPIC_API_KEY):  # Reuse Anthropic key or use dedicated OpenAI key
            # Try OpenAI TTS if OPENAI_API_KEY is set, otherwise skip
            openai_key = getattr(cfg, "OPENAI_API_KEY", "")
            if openai_key:
                cta_text = _pick_cta(quote_data["row_number"])
                log.info("  Generating voiceover narration...")
                try:
                    voiceover = prepare_reel_voiceover(
                        hook_text=hook_text,
                        quote_text=quote_data["quote"],
                        cta_text=cta_text,
                        mood=mood,
                        api_key=openai_key,
                        output_dir=OUTPUT_DIR,
                        timestamp=timestamp,
                    )
                    log.info(f"  Voiceover: {voiceover['voice']} voice")
                except Exception as e:
                    log.warning(f"  Voiceover generation failed: {e}")
            else:
                log.info("  OPENAI_API_KEY not set — skipping voiceover")

        # Assemble multi-scene reel
        reel_path = generate_reel(
            scene_images=[scene_hook, scene_quote, scene_cta],
            mood=mood,
            output_dir=OUTPUT_DIR,
            timestamp=timestamp,
            quote_text=quote_data["quote"],
            voiceover=voiceover,
        )
        if reel_path:
            log.info(f"Reel: {reel_path}")

    # ── Step 6: Post to Instagram ────────────────────────────────────────────
    post_id = None
    if manual:
        # ── MANUAL MODE: Generate Reel but send to user for manual upload ──
        log.info("Step 6/6: MANUAL MODE — Sending Reel to Telegram for manual posting...")
        try:
            notifier = Notifier(cfg)
            trending = get_trending_suggestion(mood)
            notifier.notify_manual_reel_ready(
                reel_path=reel_path,
                cover_path=final_image_path,
                caption=quote_data["caption"],
                mood=mood,
                trending_suggestion=trending,
            )
            log.info("✅ Reel sent to Telegram! Download it and post to Instagram with trending music.")
        except Exception as e:
            log.error(f"Failed to send Reel to Telegram: {e}")

        # Mark as ready (not fully posted yet)
        mark_as_posted(EXCEL_PATH, quote_data["row_number"], "PENDING_MANUAL")
        mark_posted(post_row_id, "PENDING_MANUAL", str(final_image_path), str(reel_path) if reel_path else None)

    elif not dry_run:
        if reel and reel_path and ffmpeg_available():
            log.info("Step 6/6: Posting Reel to Instagram...")
            post_id = post_reel_to_instagram(
                video_path=reel_path,
                caption=quote_data["caption"],
                ig_account_id=cfg.IG_ACCOUNT_ID,
                access_token=access_token,
                cloudinary_config={
                    "cloud_name": cfg.CLOUDINARY_CLOUD_NAME,
                    "api_key":    cfg.CLOUDINARY_API_KEY,
                    "api_secret": cfg.CLOUDINARY_API_SECRET,
                },
                cover_path=final_image_path,
            )
        else:
            log.info("Step 6/6: Posting image to Instagram...")
            post_id = post_to_instagram(
                image_path=final_image_path,
                caption=quote_data["caption"],
                ig_account_id=cfg.IG_ACCOUNT_ID,
                access_token=access_token,
                cloudinary_config={
                    "cloud_name": cfg.CLOUDINARY_CLOUD_NAME,
                    "api_key":    cfg.CLOUDINARY_API_KEY,
                    "api_secret": cfg.CLOUDINARY_API_SECRET,
                }
            )
        log.info(f"✅ Posted! ID: {post_id}")
        mark_as_posted(EXCEL_PATH, quote_data["row_number"], post_id)
        mark_posted(post_row_id, post_id, str(final_image_path), str(reel_path) if reel_path else None)

        # ── Phase 4: Notify user to manually add trending sound ───────────────
        if post_id:
            try:
                notifier = Notifier(cfg)
                trending = get_trending_suggestion(mood)
                notifier.notify_post_published(
                    post_id=post_id,
                    caption_preview=quote_data["caption"][:120],
                    mood=mood,
                    trending_suggestion=trending,
                )
            except Exception as e:
                log.warning(f"Notification failed (non-blocking): {e}")
    else:
        log.info("⏭ dry_run=True — skip Instagram post")

    # ── Save log ──────────────────────────────────────────────────────────────
    record = {
        "timestamp":       timestamp,
        "row_number":      quote_data["row_number"],
        "audience":        quote_data["audience"],
        "mood":            mood,
        "quote":           quote_data["quote"],
        "caption_preview": quote_data["caption"][:80],
        "image_path":      str(final_image_path),
        "post_id":         post_id,
        "dry_run":         dry_run,
    }
    save_log(record)
    log.info("▶ Pipeline complete")
    return record


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Skip Instagram post")
    parser.add_argument("--reel", action="store_true", help="Post as Reel with Ken Burns zoom + ambient audio")
    parser.add_argument("--carousel", action="store_true", help="Post as Carousel (currently treated as standard post)")
    parser.add_argument("--manual", action="store_true", help="Generate Reel but do not post. Send video + caption to Telegram for manual upload with trending music.")
    args = parser.parse_args()

    # --manual implies --reel (generate video) but skips API posting
    if args.manual:
        run_pipeline(dry_run=False, reel=True, manual=True)
    else:
        # Note: --carousel currently falls through to standard post logic
        run_pipeline(dry_run=args.dry_run, reel=args.reel)
