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

from src.core.excel_reader import read_todays_quote, get_mood_prompt, mark_as_posted, _current_slot
from src.visual.image_generator import generate_background
from src.visual.image_composer import compose_post, compose_hook_scene, compose_quote_scene, compose_cta_scene
from src.visual.carousel_composer import compose_carousel
from src.core.instagram_poster import post_to_instagram, post_reel_to_instagram, post_carousel_to_instagram
from src.video.reel_composer import generate_reel, ffmpeg_available
from config import Config
from src.core.data_store import init_db, save_post, mark_posted, get_ab_results, has_posted_today, save_proposal
from src.analytics.ab_test import pick_caption_variant, pick_mood, pick_optimal_slot
from src.analytics.hook_tracker import pick_best_hook
from src.core.token_manager import get_valid_token_with_fallback
from src.core.notifier import Notifier
from src.audio.trending_music import get_trending_suggestion
from src.audio.voiceover import prepare_reel_voiceover, voiceover_available

# ── Phase 1 Viral Upgrades ─────────────────────────────────────────────────────
from src.hooks.pattern_interrupt import PatternInterrupter
from src.visual.brand_design import get_design
from src.engagement.comment_bait import CommentBait
from src.prompts.architect import PromptArchitect
from src.wallpapers.composer import WallpaperComposer

# ── Phase 3 Audio Engineering ──────────────────────────────────────────────────
from src.audio.trending_audio import TrendingAudioEngine, download_music_for_mood
from src.audio.voiceover_engine import VoiceoverEngine, generate_enhanced_voiceover
from src.audio.edge_tts_engine import prepare_reel_voiceover_edge_tts, edge_tts_available

# ── Viral Growth: POV text Reels (zero-cost — ffmpeg + Pillow only) ───────────
from src.video.pov_reel_generator import generate_pov_reel

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


def _apply_studio_decision(brief, decision, concepts_by_id):
    """Map a studio Decision onto the quote_data dict the renderer consumes.
    Stamps caption_marker (the hook) onto visual_direction for reconcile."""
    concept = concepts_by_id.get(decision.top_pick)
    if concept is None:
        from studio.client import StudioError
        raise StudioError(
            f"director picked unknown concept id {decision.top_pick!r} "
            f"(known ids: {list(concepts_by_id)})")
    decision.visual_direction["caption_marker"] = concept.hook
    return {
        "row_number": brief.quote.get("row_number"),
        "audience": brief.audience,
        "quote": brief.quote.get("text", ""),
        "caption": concept.caption,
        "mood": decision.visual_direction["mood"],
        "hook": concept.hook,
        "flux_prompt": decision.visual_direction.get("flux_prompt", ""),
        "format": brief.format,
        "reel_scenes": concept.reel_scenes,
    }


def _studio_stage(cfg, slot):
    """Run the AI Creative Studio. Returns (quote_data, decision) or None (fallback)."""
    from studio.run import run_studio, _build_pool
    from studio.client import StudioClient

    client = StudioClient(cfg.ANTHROPIC_API_KEY)
    pool = _build_pool(str(EXCEL_PATH))
    result = run_studio(client, slot, pool, [])
    if result is None:
        return None
    brief, decision, cmap = result
    # Resolve the quote text from the pool if the strategist returned only a row.
    if not brief.quote.get("text") and brief.quote.get("row_number") is not None:
        match = next((r for r in pool if r["row_number"] == brief.quote["row_number"]), None)
        if match:
            brief.quote["text"] = match["quote"]
    if not brief.quote.get("text"):
        log.warning("[studio] strategist returned no resolvable quote text "
                    "(need_new=%s) — falling back to legacy", brief.quote.get("need_new"))
        return None
    return _apply_studio_decision(brief, decision, cmap), decision


def _legacy_content(cfg):
    """Legacy templated content prep (quote pool + A/B + caption templates)."""
    quote_data = read_todays_quote(EXCEL_PATH, api_key=cfg.ANTHROPIC_API_KEY)
    caption_variant = pick_caption_variant(quote_data["audience"], get_ab_results=get_ab_results)
    mood = pick_mood(quote_data["audience"], quote_data["quote"], get_ab_results=get_ab_results)
    chosen_caption = quote_data.get("caption_b") if caption_variant == 1 else quote_data["caption"]
    controversy = _pick_controversy(quote_data["audience"], quote_data["row_number"])
    quote_data["caption"] = _enhance_caption(
        chosen_caption,
        audience=quote_data["audience"],
        mood=mood,
        row_number=quote_data["row_number"],
        controversy=controversy,
    )
    if not mood:
        mood = get_mood_prompt(quote=quote_data["quote"], audience=quote_data["audience"],
                               api_key=cfg.ANTHROPIC_API_KEY)
    return quote_data, mood, controversy, caption_variant


def _run_pov_reel(cfg, quote_data: dict, mood: str, slot: int, timestamp: str,
                   dry_run: bool, manual: bool, access_token: str,
                   use_remotion: bool = False) -> dict:
    """
    POV mode: generate a text Reel and post/send it exactly like the regular Reel
    flow, minus the background-image generation steps.

    Renderer selection:
      - use_remotion=True → render with the Remotion project (professional,
        physics-driven text animations). Falls back to the ffmpeg POV generator
        automatically if Node/Remotion isn't installed or the render fails.
      - otherwise → the zero-cost ffmpeg + Pillow POV generator.
    """
    hook_text = quote_data.get("hook") or _generate_psychology_hook(
        quote_data["audience"], quote_data["row_number"])
    cta_text = _pick_cta(quote_data["row_number"])
    log.info(f"  [pov] Hook: {hook_text[:50]}...")

    reel_path = None

    if use_remotion:
        # Produce full VO (hook/quote/cta) + a music bed for the narrated
        # Remotion reel. Best-effort: any failure → that piece is simply absent
        # (the reel still renders; the ffmpeg fallback below makes zero TTS calls).
        hook_voice = quote_voice = cta_voice = music_path = None
        hook_words = quote_words = cta_words = []
        try:
            if edge_tts_available():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                vo = prepare_reel_voiceover_edge_tts(
                    hook_text=hook_text,
                    quote_text=quote_data["quote"],
                    cta_text=cta_text,
                    mood=mood,
                    output_dir=OUTPUT_DIR,
                    timestamp=ts,
                )
                if isinstance(vo, dict):
                    hook_voice = vo.get("hook_voice")
                    quote_voice = vo.get("quote_voice")
                    cta_voice = vo.get("cta_voice")
                    hook_words = vo.get("hook_words") or []
                    quote_words = vo.get("quote_words") or []
                    cta_words = vo.get("cta_words") or []
        except Exception as e:
            log.warning(f"  [remotion] reel voiceover unavailable ({e}) — silent reel")
        try:
            from src.audio.trending_audio import download_music_for_mood
            music_path = download_music_for_mood(mood)
        except Exception as e:
            log.warning(f"  [remotion] music bed unavailable ({e}) — VO-only reel")

        try:
            from src.video.remotion_reel import generate_remotion_reel
            # Auto-numbered output: reel_001.mp4, reel_002.mp4, ...
            counter = 1
            while (OUTPUT_DIR / f"reel_{counter:03d}.mp4").exists():
                counter += 1
            reel_path = generate_remotion_reel(
                    hook=hook_text,
                    quote=quote_data["quote"],
                    attribution="— Socrates",
                    cta=_pick_cta(quote_data["row_number"]),
                    mood=mood,
                    output_path=OUTPUT_DIR / f"reel_{counter:03d}.mp4",
                    hook_voice=hook_voice,
                    quote_voice=quote_voice,
                    cta_voice=cta_voice,
                    music_path=music_path,
                    hook_words=hook_words,
                    quote_words=quote_words,
                    cta_words=cta_words,
            )
        except Exception as e:
            log.warning(f"  [remotion] renderer errored ({e}) — falling back to POV")
        if reel_path is None:
            log.info("  [remotion] unavailable/failed — using ffmpeg POV fallback")

    if reel_path is None:
        counter = 1
        while (OUTPUT_DIR / f"reel_{counter:03d}.mp4").exists():
            counter += 1
        reel_path = generate_pov_reel(
            quote=quote_data["quote"],
            hook=hook_text,
            cta=cta_text,
            output_path=OUTPUT_DIR / f"reel_{counter:03d}.mp4",
            mood=mood,
        )
    if reel_path:
        log.info(f"POV Reel: {reel_path}")

    hook_pick = pick_best_hook(audience=quote_data["audience"], quote_text=quote_data["quote"])
    post_row_id = save_post(
        quote_text=quote_data["quote"],
        audience=quote_data["audience"],
        mood=mood,
        caption_variant=-1,
        posting_slot=slot,
        dry_run=dry_run,
        hook_id=hook_pick["hook_id"],
    )

    if post_row_id is None:
        log.warning(
            f"  [dedup] slot {slot} already claimed today (concurrent run) — "
            f"skipping to avoid a double-post"
        )
        return {"skipped": True, "reason": f"slot {slot} already claimed today"}

    post_id = None
    if manual:
        log.info("Step: MANUAL MODE — sending POV Reel to Telegram for manual posting...")
        try:
            notifier = Notifier(cfg)
            trending = get_trending_suggestion(mood)
            notifier.notify_manual_reel_ready(
                reel_path=reel_path,
                cover_path=None,
                caption=quote_data["caption"],
                mood=mood,
                trending_suggestion=trending,
                post_row_id=post_row_id,
            )
            log.info("✅ POV Reel sent to Telegram! Download and post with trending music.")
        except Exception as e:
            log.error(f"Failed to send POV Reel to Telegram: {e}")
        mark_as_posted(EXCEL_PATH, quote_data["row_number"], "PENDING_MANUAL")
        mark_posted(post_row_id, "PENDING_MANUAL", None, str(reel_path) if reel_path else None)
    elif not dry_run and reel_path:
        log.info("Step: Posting POV Reel to Instagram...")
        post_id = post_reel_to_instagram(
            video_path=reel_path,
            caption=quote_data["caption"],
            ig_account_id=cfg.IG_ACCOUNT_ID,
            access_token=access_token,
            cloudinary_config={
                "cloud_name": cfg.CLOUDINARY_CLOUD_NAME,
                "api_key": cfg.CLOUDINARY_API_KEY,
                "api_secret": cfg.CLOUDINARY_API_SECRET,
            },
        )
        log.info(f"✅ Posted! ID: {post_id}")
        mark_as_posted(EXCEL_PATH, quote_data["row_number"], post_id)
        mark_posted(post_row_id, post_id, None, str(reel_path))
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

    record = {
        "timestamp": timestamp,
        "row_number": quote_data["row_number"],
        "audience": quote_data["audience"],
        "mood": mood,
        "quote": quote_data["quote"],
        "caption_preview": quote_data["caption"][:80],
        "image_path": None,
        "reel_path": str(reel_path) if reel_path else None,
        "post_id": post_id,
        "dry_run": dry_run,
        "pov": True,
    }
    save_log(record)
    log.info("▶ POV Pipeline complete")
    return record


def run_pipeline(dry_run: bool = False, reel: bool = False, manual: bool = False, studio: bool = False,
                  carousel: bool = False, pov: bool = False, remotion: bool = False,
                  seed: int | None = None):
    # --remotion is a POV text-reel rendered with the Remotion project (falls
    # back to the ffmpeg POV generator if Node/Remotion isn't available).
    if remotion:
        pov = True
    cfg = Config()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log.info(f"▶ HYBRID Pipeline start | dry_run={dry_run} reel={reel} manual={manual} carousel={carousel}")

    # Initialize SQLite state store
    init_db()

    # Get valid Meta token (auto-refreshes if needed)
    access_token = get_valid_token_with_fallback(cfg)

    # ── Pre-flight guard: skip if this slot already posted today ──────────────
    slot = _current_slot()
    if has_posted_today(slot):
        log.info(f"⏭ Slot {slot} already posted today — skipping")
        return {"skipped": True, "reason": f"slot {slot} already posted today"}

    # ── Content stage: AI Creative Studio (with legacy fallback) ──────────────
    studio_decision = None
    flux_override = ""
    if studio:
        log.info("Step 1: AI Creative Studio...")
        try:
            bundle = _studio_stage(cfg, slot)
        except Exception as e:
            log.warning("[studio] stage crashed (%s: %s) — falling back to legacy",
                        type(e).__name__, e)
            bundle = None
        if bundle is not None:
            quote_data, studio_decision = bundle
            mood = quote_data["mood"]
            controversy = ""
            caption_variant = -1
            flux_override = quote_data.get("flux_prompt", "")
            log.info(f"  [studio] proposal ready — mood={mood}, "
                     f"hook={quote_data.get('hook', '')[:40]!r}")
        else:
            log.info("  [studio] fell back to legacy templated path")

    if studio_decision is None:
        log.info("Step 1: Reading quote + legacy templated content...")
        quote_data, mood, controversy, caption_variant = _legacy_content(cfg)

    # ── Phase 1: Inject viral engagement into caption ───────────────────────────
    bait = CommentBait(audience=quote_data["audience"], mood=mood)
    engagement_block = bait.generate_full_engagement_block(
        quote=quote_data["quote"],
        include_question=True,
        include_cta=True,
        include_booster=False,
    )
    quote_data["caption"] = f"{quote_data['caption']}\n\n{engagement_block}"
    log.info(f"  [viral] Engagement block injected ({len(engagement_block)} chars)")

    # ── POV mode: zero-cost text Reel — bypasses FLUX entirely ────────────────
    if pov:
        renderer = "Remotion (professional animations)" if remotion else "ffmpeg + Pillow"
        log.info(f"Step 2: POV mode — generating text Reel via {renderer}...")
        return _run_pov_reel(cfg, quote_data, mood, slot, timestamp, dry_run, manual,
                             access_token, use_remotion=remotion)

    # ── Phase 1: Build enhanced FLUX prompt ────────────────────────────────────
    flux_override = ""
    if studio:
        flux_override = quote_data.get("flux_prompt", "")
    if not flux_override:
        architect = PromptArchitect(anthropic_api_key=cfg.ANTHROPIC_API_KEY)
        flux_override = architect.build(
            quote=quote_data["quote"],
            mood=mood,
            seed=quote_data.get("row_number", 0),
        )
        log.info(f"  [viral] FLUX prompt enhanced ({len(flux_override)} chars)")

    log.info(f"Quote:    {quote_data['quote'][:60]}...")
    log.info(f"Audience: {quote_data['audience']}")
    log.info(f"Slot: {slot}, Variant: {caption_variant}, Mood: {mood}")

    # ── Step 3: Generate background image via Fal.ai ─────────────────────────
    log.info("Step 3/5: Generating background via Fal.ai...")
    image_path, image_seed = generate_background(
        mood=mood,
        api_key=cfg.FAL_API_KEY,
        output_dir=OUTPUT_DIR,
        quote=quote_data["quote"],
        anthropic_api_key=cfg.ANTHROPIC_API_KEY,
        prompt_override=flux_override,
        seed=seed,
    )
    log.info(f"Background: {image_path}")

    # ── Phase 2: Apply atmospheric overlays ───────────────────────────────────
    try:
        from src.overlays.particles import add_particles_to_image, add_light_rays_to_image
        from PIL import Image
        bg_img = Image.open(image_path)
        bg_with_particles = add_particles_to_image(bg_img, mood=mood, seed=quote_data.get("row_number", 0))
        bg_with_rays = add_light_rays_to_image(bg_with_particles, mood=mood)
        overlay_path = OUTPUT_DIR / f"bg_enhanced_{timestamp}.jpg"
        bg_with_rays.save(overlay_path, quality=95)
        image_path = overlay_path
        log.info(f"  [phase2] Atmospheric overlays applied: particles + light rays")
    except Exception as e:
        log.warning(f"  [phase2] Overlay application failed (non-blocking): {e}")

    # ── Step 4: Compose final post image ──────────────────────────────────────
    carousel_paths = None
    if carousel:
        log.info("Step 4/5: Composing 5-slide carousel...")
        carousel_paths = compose_carousel(
            quote=quote_data["quote"],
            attribution="— Socrates",
            bg_path=image_path,
            output_dir=OUTPUT_DIR,
            timestamp=timestamp,
        )
        final_image_path = carousel_paths[1]  # quote slide — used as cover/log image
        log.info(f"Carousel slides: {len(carousel_paths)} → {final_image_path}")
    else:
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

    # ── Phase 1: Generate Wallpaper Series (save-bait) ────────────────────────
    wallpaper_paths = {}
    try:
        wp_composer = WallpaperComposer(mood=mood)
        from PIL import Image as PILImage
        bg_img = PILImage.open(image_path)
        wallpaper_paths = wp_composer.create_wallpaper_set(
            quote=quote_data["quote"],
            author="Socrates",
            output_dir=OUTPUT_DIR / "wallpapers",
            background_image=bg_img,
            seed=quote_data.get("row_number", 0),
        )
        log.info(f"  [viral] Wallpaper series created: {len(wallpaper_paths)} formats")
    except Exception as e:
        log.warning(f"  [viral] Wallpaper generation failed (non-blocking): {e}")

    # ── Save to SQLite state store ────────────────────────────────────────────
    hook_pick = pick_best_hook(audience=quote_data["audience"], quote_text=quote_data["quote"])
    post_row_id = save_post(
        quote_text=quote_data["quote"],
        audience=quote_data["audience"],
        mood=mood,
        caption_variant=caption_variant,
        posting_slot=slot,
        dry_run=dry_run,
        hook_id=hook_pick["hook_id"],
        seed=image_seed,
    )

    if post_row_id is None:
        log.warning(
            f"  [dedup] slot {slot} already claimed today (concurrent run) — "
            f"skipping to avoid a double-post"
        )
        return {"skipped": True, "reason": f"slot {slot} already claimed today"}

    # ── Step 5: Generate Reel (if reel mode or dry-run) ───────────────────────
    reel_path = None
    if reel or (dry_run and ffmpeg_available()):
        log.info(f"Step 5/6: {'Generating Reel' if reel else 'Testing'} reel generation...")

        # Extract hook text from caption for Scene 1
        # Psychology-driven hook: audience-specific pattern interrupt
        # Research: confrontational/curiosity-gap hooks have highest 3s hold rates
        hook_text = quote_data.get("hook") or _generate_psychology_hook(
            quote_data["audience"], quote_data["row_number"])
        log.info(f"  Hook: {hook_text[:50]}...")

        # Generate 2 backgrounds for visual variety
        log.info("  Generating background 1 (hook scene)...")
        bg_hook_path, _ = generate_background(
            mood=mood,
            api_key=cfg.FAL_API_KEY,
            output_dir=OUTPUT_DIR,
            quote=quote_data["quote"],
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
            prompt_override=flux_override,
        )
        log.info("  Generating background 2 (quote scene)...")
        bg_quote_path, _ = generate_background(
            mood=mood,
            api_key=cfg.FAL_API_KEY,
            output_dir=OUTPUT_DIR,
            quote=quote_data["quote"],
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
            prompt_override=flux_override,
        )
        log.info("  Generating background 3 (CTA scene)...")
        bg_cta_path, _ = generate_background(
            mood=mood,
            api_key=cfg.FAL_API_KEY,
            output_dir=OUTPUT_DIR,
            quote=quote_data["quote"],
            anthropic_api_key=cfg.ANTHROPIC_API_KEY,
            prompt_override=flux_override,
        )

        # Compose 3 vertical scenes
        log.info("  Composing scenes...")

        # ── Phase 1: Pattern Interrupt on Hook Scene ─────────────────────────
        # Apply scroll-stopping visual effect to hook scene background
        from PIL import Image
        hook_bg = Image.open(bg_hook_path)
        interrupter = PatternInterrupter(mode=PatternInterrupter.random_mode(seed=quote_data.get("row_number", 0)))
        hook_bg_interrupted = interrupter.apply(hook_bg, text=hook_text)
        hook_interrupted_path = OUTPUT_DIR / f"hook_scene_interrupted_{timestamp}.jpg"
        hook_bg_interrupted.save(hook_interrupted_path, quality=95)
        log.info(f"  [viral] Pattern interrupt applied: {interrupter.mode}")

        scene_hook = compose_hook_scene(
            background_path=hook_interrupted_path,
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

        # ── Phase 3: Generate voiceover narration with emotion-tagged scripts ──
        voiceover = None
        openai_key = getattr(cfg, "OPENAI_API_KEY", "")
        if openai_key:
            cta_text = _pick_cta(quote_data["row_number"])
            log.info("  Generating enhanced voiceover narration...")
            try:
                voiceover = generate_enhanced_voiceover(
                    hook_text=hook_text,
                    quote=quote_data["quote"],
                    cta_text=cta_text,
                    mood=mood,
                    api_key=openai_key,
                    output_dir=OUTPUT_DIR,
                    timestamp=timestamp,
                    style="intense" if mood in ("epic_warrior", "dark_philosophical") else "calm",
                )
                if voiceover:
                    log.info(f"  [phase3] Enhanced voiceover generated: {len(voiceover)} scenes")
            except Exception as e:
                log.warning(f"  [phase3] Enhanced voiceover failed ({e}) — trying legacy fallback")
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
                except Exception as e2:
                    log.warning(f"  Legacy voiceover also failed: {e2}")
        else:
            log.info("  OPENAI_API_KEY not set — trying edge-tts (free) voiceover")

        if not voiceover and edge_tts_available():
            cta_text = _pick_cta(quote_data["row_number"])
            try:
                voiceover = prepare_reel_voiceover_edge_tts(
                    hook_text=hook_text,
                    quote_text=quote_data["quote"],
                    cta_text=cta_text,
                    mood=mood,
                    output_dir=OUTPUT_DIR,
                    timestamp=timestamp,
                )
                if voiceover:
                    log.info(f"  [edge-tts] Free voiceover generated: {voiceover.get('voice')}")
            except Exception as e3:
                log.warning(f"  edge-tts voiceover also failed: {e3}")
        elif not voiceover:
            log.info("  edge-tts not installed — skipping voiceover entirely")

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
                post_row_id=post_row_id,
            )
            # ── Phase 1: Send wallpaper series too ────────────────────────────
            if wallpaper_paths:
                notifier.notify_wallpapers_ready(
                    wallpaper_paths=wallpaper_paths,
                    quote_preview=quote_data["quote"][:60],
                )
            log.info("✅ Reel + wallpapers sent to Telegram! Download and post to Instagram with trending music.")
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
        elif carousel and carousel_paths:
            log.info("Step 6/6: Posting carousel to Instagram...")
            post_id = post_carousel_to_instagram(
                image_paths=carousel_paths,
                caption=quote_data["caption"],
                ig_account_id=cfg.IG_ACCOUNT_ID,
                access_token=access_token,
                cloudinary_config={
                    "cloud_name": cfg.CLOUDINARY_CLOUD_NAME,
                    "api_key":    cfg.CLOUDINARY_API_KEY,
                    "api_secret": cfg.CLOUDINARY_API_SECRET,
                }
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

    # ── Persist studio proposal (for reconcile + analyst feedback loop) ───────
    if studio_decision is not None:
        try:
            save_proposal(slot, quote_data.get("row_number"), quote_data["audience"],
                          quote_data.get("format", "reel"),
                          json.dumps(studio_decision.to_dict()))
        except Exception as e:
            log.warning(f"[studio] save_proposal failed (non-blocking): {e}")

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
    parser.add_argument("--carousel", action="store_true", help="Post as a 5-slide Carousel instead of a single image")
    parser.add_argument("--manual", action="store_true", help="Generate Reel but do not post. Send video + caption to Telegram for manual upload with trending music.")
    parser.add_argument("--studio", action="store_true", help="Use the AI Creative Studio (reasoning agents); falls back to legacy templates on any failure.")
    parser.add_argument("--pov", action="store_true", help="Generate a zero-cost POV text Reel (ffmpeg + Pillow only, no FLUX) instead of the FLUX-based Reel.")
    parser.add_argument("--remotion", action="store_true", help="Generate a POV text Reel with Remotion (professional physics-driven text animations). Implies --pov; falls back to the ffmpeg POV generator if Node/Remotion isn't installed.")
    parser.add_argument("--batch", action="store_true", help="Generate a week's worth of POV Reels (30) in one run and exit — does not post to Instagram.")
    parser.add_argument("--seed", type=int, default=None, help="Force a FLUX image seed for reproducible backgrounds.")
    args = parser.parse_args()

    if args.batch:
        from src.video.batch_generator import generate_batch
        generate_batch()
    elif args.manual:
        # --manual implies --reel (generate video) but skips API posting
        run_pipeline(dry_run=False, reel=True, manual=True, studio=args.studio,
                     pov=args.pov, remotion=args.remotion, seed=args.seed)
    else:
        run_pipeline(dry_run=args.dry_run, reel=args.reel, studio=args.studio,
                     carousel=args.carousel, pov=args.pov, remotion=args.remotion, seed=args.seed)
