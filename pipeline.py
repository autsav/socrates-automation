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
import os
from datetime import datetime
from pathlib import Path

from src.core.excel_reader import read_todays_quote, get_mood_prompt, mark_as_posted, _current_slot
from src.visual.image_generator import generate_background
from src.visual.image_composer import compose_post, compose_hook_scene, compose_quote_scene, compose_cta_scene
from src.visual.carousel_composer import compose_carousel
from src.core.instagram_poster import post_to_instagram, post_reel_to_instagram, post_carousel_to_instagram
from src.video.reel_composer import generate_reel, ffmpeg_available
from config import Config
from src.core.data_store import init_db, save_post, mark_posted, release_post, get_ab_results, has_posted_today, save_proposal, record_trigger_keyword, record_arc
from studio.reconcile import reconcile_token
from studio.client import StudioClient
from studio import music_director
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
from src.audio.edge_tts_engine import (
    prepare_reel_voiceover_edge_tts, edge_tts_available,
    generate_scene_voiceover_edge_tts, parse_word_srt,
    REEL_VOICE, REEL_RATE, REEL_PITCH,
)
from src.audio.elevenlabs_engine import (
    prepare_reel_voiceover as prepare_reel_voiceover_elevenlabs,
    elevenlabs_available,
)

# ── Viral Growth: POV text Reels (zero-cost — ffmpeg + Pillow only) ───────────
from src.video.pov_reel_generator import generate_pov_reel

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
LOG_DIR = PROJECT_ROOT / "logs"
OUTPUT_DIR = PROJECT_ROOT / "output"
EXCEL_PATH = PROJECT_ROOT / "quotes.xlsx"


def _rel_path(p):
    """Render a path repo-relative (no absolute local paths in logs/DB).

    In-repo path -> 'output/foo.jpg'; outside-repo -> basename; None -> None.
    Best-effort: never raises."""
    if p is None:
        return None
    try:
        return str(Path(p).resolve().relative_to(PROJECT_ROOT))
    except (ValueError, OSError, TypeError):
        try:
            return Path(str(p)).name
        except Exception:
            return None


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
    # Comment triggers steer to the bio (funnel_worker replies publicly —
    # NEVER promise a DM: nothing sends DMs).
    "Comment 'STOIC' for the full reflection — it's one tap away.",   # comment trigger
    "Comment 'RESET' and I'll point you to the 3-line Stoic reset.",  # comment trigger
]


_ARC_ROTATION = ("classic", "classic", "question", "cold_open")

_QUESTION_HOOKS = [
    "What if the problem was never out there?",
    "Why does no one tell you this?",
    "What are you actually afraid of?",
    "How long will you keep waiting?",
]


def _pick_arc(row_number: int | None) -> str:
    """Deterministic arc per post: 50% classic, 25% question, 25% cold_open.
    Kills pattern fatigue — every reel used to be the same 4-scene shape."""
    return _ARC_ROTATION[(row_number or 0) % len(_ARC_ROTATION)]


def _apply_arc(arc: str, hook_text: str, bridge_text: str, audience: str,
               row_number: int | None) -> tuple[str, str]:
    """Shape (hook, bridge) for the chosen arc. Pure — unit-testable.

    classic   → unchanged (Hook → [Bridge] → Quote → CTA)
    question  → interrogative hook, no bridge (Question → Quote-as-answer → CTA)
    cold_open → no hook, no bridge (Quote hits at 0:00 — hard pattern interrupt)
    """
    if arc == "cold_open":
        return "", ""
    if arc == "question":
        if not hook_text.rstrip().endswith("?"):
            pool = [h for h in _PSYCHOLOGY_HOOKS.get(audience, []) if h.endswith("?")] \
                   or _QUESTION_HOOKS
            hook_text = pool[(row_number or 0) % len(pool)]
        return hook_text, ""
    return hook_text, bridge_text


def _extract_trigger_keyword(cta: str) -> str | None:
    """Return the comment-trigger keyword from a CTA (Comment 'RESET' … -> RESET),
    or None when the CTA has no comment trigger. Used to register the keyword on
    the post row so funnel_worker knows what to match."""
    import re
    m = re.search(r"Comment '([A-Za-z]+)'", cta or "")
    return m.group(1).upper() if m else None

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

_GENERIC_TAGS = {"#fyp", "#viral", "#reels", "#explore", "#foryou", "#trending"}


def _generate_hashtags(audience: str, mood: str, max_tags: int = 5) -> str:
    """Build a 3–5 tag string using performance data when available.

    Tries the hashtag tracker first (data-driven), falls back to
    the static pool + mood tag. Generic/spam tags are always filtered.
    """
    mood = mood or ""
    # Try data-driven hashtag recommendations first
    try:
        from src.analytics.hashtag_tracker import recommend_hashtags, BANNED_HASHTAGS
        recommended = recommend_hashtags(audience=audience, n=max_tags)
        if recommended and len(recommended) >= 3:
            return " ".join(recommended[:max_tags])
    except Exception:
        pass

    # Fallback: static pool
    candidates = list(_BASE_HASHTAGS[:2])
    for t in _HASHTAG_POOL.get(audience, []):
        candidates.append(t)
    candidates.append(f"#{mood.replace('_', '').title()}")
    # Dedupe (case-insensitive), drop generic, preserve order.
    seen, tags = set(), []
    for t in candidates:
        k = t.lower()
        if k in _GENERIC_TAGS or k in seen:
            continue
        seen.add(k)
        tags.append(t)
    tags = tags[:max(3, min(max_tags, 5))]
    # Pad to 3 from the base pool if somehow short.
    for t in _BASE_HASHTAGS:
        if len(tags) >= 3:
            break
        if t.lower() not in seen:
            tags.append(t)
            seen.add(t.lower())
    return " ".join(tags[:5])


def _pick_cta(row_number: int) -> str:
    """Deterministically rotate CTA variants based on row number."""
    return _CTA_VARIANTS[row_number % len(_CTA_VARIANTS)]


def _add_emojis(audience: str, mood: str) -> str:
    """Return 2–3 contextual emojis for the caption."""
    aud_emoji = _AUDIENCE_EMOJIS.get(audience, "💡")
    mood_emoji = _MOOD_EMOJIS.get(mood, "🔥")
    return f"{aud_emoji} {mood_emoji}"


def _enforce_hook_len(hook: str, max_words: int = 12) -> str:
    """Formula rule: hooks are 5–12 words. Trim an over-long hook to its first
    sentence/clause within the word budget (never raises)."""
    if not hook:
        return hook
    words = hook.split()
    if len(words) <= max_words:
        return hook
    # Prefer cutting at the first sentence end within budget.
    trimmed = " ".join(words[:max_words])
    for stop in (".", "?", "!"):
        i = trimmed.find(stop)
        if i != -1:
            return trimmed[: i + 1]
    return trimmed.rstrip(",;:") + "…"


def _enforce_bridge_len(bridge: str, max_words: int = 20) -> str:
    """Formula rule: the Bridge scene is a *pivot into* the Quote, not the payoff
    — keep it to one short sentence (~20 words / ~10s of sage VO). An un-capped
    bridge (e.g. a 44-word trend-scout pivot) balloons the reel past 40s and
    front-loads the resolution the Quote scene is meant to deliver.

    Trims an over-long bridge to the first natural stop within the word budget,
    preferring the ellipsis pivot ('…options… but') that hands off to the Quote.
    Never raises; short/empty bridges pass through untouched."""
    if not bridge:
        return bridge
    words = bridge.split()
    if len(words) <= max_words:
        return bridge
    trimmed = " ".join(words[:max_words])
    # Prefer the earliest natural stop: ellipsis pivot or sentence end.
    cuts = [trimmed.find(s) for s in ("…", "...", ".", "?", "!")]
    cuts = [c for c in cuts if c != -1]
    if cuts:
        i = min(cuts)
        end = i + (3 if trimmed[i:i + 3] == "..." else 1)
        return trimmed[:end]
    return trimmed.rstrip(",;:—- ") + "…"


def _loopify(cta: str, hook: str) -> str:
    """Seamless-loop device: end the CTA with an open connector so it flows back
    into the hook. Idempotent."""
    c = (cta or "").rstrip()
    if not c:
        return c
    if c.endswith(("—", "…")):
        return c
    return c.rstrip(".!?") + " —"




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
        "topic_theme": brief.topic_theme,
        "angle": brief.angle,
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


def _injected_content(path: str, cfg) -> tuple[dict, str]:
    """Load a hand-crafted/external reel content JSON, filling any missing field
    from the existing generators. Bypasses excel + studio. Returns (quote_data, mood)."""
    import json as _json
    data = _json.loads(Path(path).read_text())
    audience = (data.get("audience") or "stuck").strip().lower()
    row_number = data.get("row_number")  # may be None -> excel not marked
    rn_seed = row_number if isinstance(row_number, int) else 0
    mood = data.get("mood") or "dark_philosophical"

    hook = _enforce_hook_len(data.get("hook") or _generate_psychology_hook(audience, rn_seed))
    cta = data.get("cta") or _pick_cta(rn_seed)
    cta = _loopify(cta, hook)

    hashtags = data.get("hashtags")
    if isinstance(hashtags, list) and hashtags:
        tag_str = " ".join(hashtags[:5])
    else:
        tag_str = _generate_hashtags(audience, mood)

    caption = data.get("caption") or data.get("quote", "")
    caption = f"{caption}\n\n{tag_str}"

    quote_data = {
        "quote": data.get("quote", ""),
        "audience": audience,
        "caption": caption,
        "mood": mood,
        "hook": hook,
        "bridge": data.get("bridge", ""),
        "cta": cta,
        "attribution": data.get("attribution", "— Socrates"),
        "row_number": row_number,
        "source": data.get("source", "injected"),
    }
    return quote_data, mood


def _trend_fetch(cfg):
    from src.content import trend_sources
    return trend_sources.fetch_trends(cfg)


def _trend_pick(cfg, candidates, quote_ctx):
    from studio.client import StudioClient
    from studio import trend_scout
    client = StudioClient(cfg.ANTHROPIC_API_KEY)
    if client.over_daily_ceiling():
        return None
    return trend_scout.pick_hook(client, candidates, quote_ctx)


def _apply_trend_scout(cfg, quote_data):
    """Source a trending hook+bridge and set quote_data['hook']/['bridge'] when
    GNEWS_API_KEY + ANTHROPIC_API_KEY are present. Skips injected content (already
    has a bridge). Never raises; unchanged on any failure or used=false."""
    if quote_data.get("bridge"):
        return quote_data
    if not (getattr(cfg, "GNEWS_API_KEY", "") and getattr(cfg, "ANTHROPIC_API_KEY", "")):
        return quote_data
    try:
        candidates = _trend_fetch(cfg)
        if not candidates:
            log.info("  [trend-scout] no trends available — evergreen hook")
            return quote_data
        qctx = {"quote": quote_data.get("quote", ""), "theme": quote_data.get("mood", ""),
                "audience": quote_data.get("audience", "")}
        th = _trend_pick(cfg, candidates, qctx)
        if th and th.used and th.hook:
            # Deterministic safety backstop: even if the agent slips through an
            # unsafe topic/hook, drop it and stay on the evergreen hook.
            from src.content.trend_sources import is_unsafe
            if is_unsafe(th.hook) or is_unsafe(th.topic) or is_unsafe(th.bridge):
                log.warning(f"  [trend-scout] rejected unsafe hook ({th.topic[:40]!r}) "
                            f"— evergreen fallback")
            else:
                quote_data["hook"] = th.hook
                quote_data["bridge"] = th.bridge
                quote_data["trend_topic"] = th.topic   # feeds the FLUX photo subject
                log.info(f"  [trend-scout] {th.source}:{th.topic[:40]!r} -> trending hook set")
        else:
            log.info("  [trend-scout] no safe bridge -> evergreen hook")
    except Exception as e:  # noqa: BLE001 - never crash a reel
        log.warning(f"  [trend-scout] unavailable ({e}) - evergreen")
    return quote_data


def _select_reel_music(cfg, quote_data, hook_text, mood):
    """Pick the reel's music bed. Uses the Music Director agent when both
    JAMENDO_CLIENT_ID and ANTHROPIC_API_KEY are set (studio-aware via any theme/
    angle already on quote_data); otherwise, or on any failure, falls back to the
    mood-based track. Never raises."""
    music_path = None
    if getattr(cfg, "JAMENDO_CLIENT_ID", "") and getattr(cfg, "ANTHROPIC_API_KEY", ""):
        try:
            client = StudioClient(cfg.ANTHROPIC_API_KEY)
            if not client.over_daily_ceiling():
                ctx = {
                    "quote": quote_data.get("quote", ""),
                    "hook": hook_text,
                    "mood": mood,
                    "studio": {"theme": quote_data.get("topic_theme", ""),
                               "angle": quote_data.get("angle", "")},
                }
                music_path = music_director.select_music(
                    client, ctx, cfg.JAMENDO_CLIENT_ID, OUTPUT_DIR)
        except Exception as e:  # noqa: BLE001 - never crash a reel
            log.warning(f"  [music-director] unavailable ({e}) — mood fallback")
    if music_path is None:
        try:
            music_path = download_music_for_mood(mood)
        except Exception as e:  # noqa: BLE001
            log.warning(f"  [remotion] music bed unavailable ({e}) — VO-only reel")
    return music_path


def _reel_background(cfg, quote_data, mood):
    """Best-effort background for a Remotion reel.

    Priority: 1) Real stock footage (Pexels) 2) Stock photo (Pexels) 3) FLUX AI art
    Stock footage avoids Instagram's AI content suppression (2025 algo).
    """
    # Try 1: Real stock footage from Pexels
    pexels_key = getattr(cfg, "PEXELS_API_KEY", "") or os.getenv("PEXELS_API_KEY", "")
    if pexels_key:
        try:
            from src.visual.stock_footage import fetch_stock_background, pexels_available
            if pexels_available(pexels_key):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                stock_path = fetch_stock_background(
                    mood=mood,
                    api_key=pexels_key,
                    output_path=OUTPUT_DIR / f"stock_bg_{ts}.mp4",
                )
                if stock_path:
                    log.info(f"  [reel] Real stock footage background: {_rel_path(stock_path)}")
                    return stock_path
        except Exception as e:
            log.warning(f"  [reel] Stock footage unavailable ({e})")

    # Try 2: Real stock photo from Pexels
    if pexels_key:
        try:
            from src.visual.stock_photo import fetch_stock_photo
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            photo_path = fetch_stock_photo(
                mood=mood,
                api_key=pexels_key,
                output_path=OUTPUT_DIR / f"stock_bg_{ts}.jpg",
            )
            if photo_path:
                log.info(f"  [reel] Real stock photo background: {_rel_path(photo_path)}")
                return photo_path
        except Exception as e:
            log.warning(f"  [reel] Stock photo unavailable ({e})")

    # Try 3: FLUX AI art (fallback — still better than no background)
    try:
        prompt = PromptArchitect().build(
            quote=quote_data.get("quote", ""), mood=mood,
            trend_topic=quote_data.get("trend_topic", ""))
        from src.visual.image_generator import generate_background
        path, _seed = generate_background(
            mood=mood, api_key=cfg.FAL_API_KEY, output_dir=str(OUTPUT_DIR),
            quote=quote_data.get("quote", ""), prompt_override=prompt)
        log.info(f"  [reel] FLUX background generated (fallback): {_rel_path(path)}")
        return path
    except Exception as e:  # noqa: BLE001 - never crash a reel
        log.warning(f"  [reel] FLUX background unavailable ({e}) — particle bg")
        return None


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
    cta_text = quote_data.get("cta") or _pick_cta(quote_data.get("row_number") or 0)

    # Arc variety: shape hook/bridge for this post's arc (classic / question /
    # cold_open) so consecutive reels don't share one predictable structure.
    arc = _pick_arc(quote_data.get("row_number"))
    hook_text, arc_bridge = _apply_arc(
        arc, hook_text, quote_data.get("bridge", ""),
        quote_data.get("audience", ""), quote_data.get("row_number"))
    quote_data["bridge"] = arc_bridge
    quote_data["arc"] = arc
    log.info(f"  [pov] Arc: {arc} | Hook: {hook_text[:50] or '(cold open)'}...")

    reel_path = None

    if use_remotion:
        # Produce full VO (hook/quote/cta) + a music bed for the narrated
        # Remotion reel. Best-effort: any failure → that piece is simply absent
        # (the reel still renders; the ffmpeg fallback below makes zero TTS calls).
        hook_voice = quote_voice = cta_voice = music_path = None
        hook_words = quote_words = cta_words = []
        try:
            # Use ElevenLabs (human-quality) when API key is available,
            # fall back to edge-tts (free but robotic) otherwise.
            el_api_key = getattr(cfg, "ELEVENLABS_API_KEY", "") or os.getenv("ELEVENLABS_API_KEY", "")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if elevenlabs_available(el_api_key):
                log.info("  [voiceover] Using ElevenLabs (human-quality narration)")
                vo = prepare_reel_voiceover_elevenlabs(
                    hook_text=hook_text,
                    quote_text=quote_data["quote"],
                    cta_text=cta_text,
                    mood=mood,
                    output_dir=OUTPUT_DIR,
                    timestamp=ts,
                    api_key=el_api_key,
                )
            elif edge_tts_available():
                log.info("  [voiceover] ElevenLabs unavailable — using edge-tts fallback")
                vo = prepare_reel_voiceover_edge_tts(
                    hook_text=hook_text,
                    quote_text=quote_data["quote"],
                    cta_text=cta_text,
                    mood=mood,
                    output_dir=OUTPUT_DIR,
                    timestamp=ts,
                )
            else:
                vo = {}
            # Resilience: if ElevenLabs came back without the critical quote VO
            # (bad key/scope, quota, outage), redo the whole VO with edge-tts
            # rather than shipping a silent reel. (Seen live: a key missing the
            # text_to_speech permission 401'd every scene.)
            if (not vo or not vo.get("quote_voice")) and edge_tts_available():
                log.warning("  [voiceover] ElevenLabs produced no usable VO — "
                            "falling back to edge-tts")
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

        # Optional Bridge scene VO (Hook -> Bridge -> Quote -> CTA). Best-effort:
        # any failure leaves bridge_voice/bridge_words empty — the Bridge scene
        # still renders (text-only, no narration), it just plays silent.
        # Cap the bridge here — the single chokepoint every source (trend-scout,
        # --content injection, generators) flows through — so no bridge can
        # balloon the reel past ~25s regardless of where it came from.
        bridge_text = _enforce_bridge_len(quote_data.get("bridge", ""))
        bridge_voice = None
        bridge_words = []
        if bridge_text:
            try:
                ts_bridge = datetime.now().strftime("%Y%m%d_%H%M%S")
                bridge_path = OUTPUT_DIR / f"voice_bridge_{ts_bridge}.mp3"
                bridge_ok = False
                # Same engine as the other scenes — a mid-reel voice switch
                # (ElevenLabs hook, edge-tts bridge) is jarring.
                el_key = getattr(cfg, "ELEVENLABS_API_KEY", "") or os.getenv("ELEVENLABS_API_KEY", "")
                if elevenlabs_available(el_key):
                    from src.audio.elevenlabs_engine import (
                        generate_scene_voiceover as _el_scene,
                        REEL_VOICE as _EL_REEL_VOICE,
                    )
                    bridge_ok = _el_scene(bridge_text, _EL_REEL_VOICE, bridge_path, el_key)
                if not bridge_ok and edge_tts_available():
                    from src.audio.edge_tts_engine import SCENE_PROSODY
                    bridge_ok = generate_scene_voiceover_edge_tts(
                        bridge_text, REEL_VOICE, bridge_path, *SCENE_PROSODY["bridge"])
                if bridge_ok:
                    bridge_voice = bridge_path
                    bridge_words = parse_word_srt(bridge_path.with_suffix(".srt"))
            except Exception as e:
                log.warning(f"  [remotion] bridge voiceover unavailable ({e}) — bridge silent")

        music_path = _select_reel_music(cfg, quote_data, hook_text, mood)

        # Finalize hook/CTA with the viral-formula helpers just before render —
        # idempotent for already-finalized (injected) content, and guarantees
        # every renderer sees a formula-compliant hook/CTA regardless of source.
        # Arc already shaped the hook upstream — never resurrect it from
        # quote_data here (a cold_open must stay hook-less).
        hook_text = _enforce_hook_len(hook_text) if hook_text else ""
        cta_text = _loopify(cta_text, hook_text)

        try:
            from src.video.remotion_reel import generate_remotion_reel
            # Auto-numbered output: reel_001.mp4, reel_002.mp4, ...
            counter = 1
            while (OUTPUT_DIR / f"reel_{counter:03d}.mp4").exists():
                counter += 1
            bg_path = _reel_background(cfg, quote_data, mood)
            reel_path = generate_remotion_reel(
                    hook=hook_text,
                    quote=quote_data["quote"],
                    attribution="— Socrates",
                    cta=cta_text,
                    mood=mood,
                    output_path=OUTPUT_DIR / f"reel_{counter:03d}.mp4",
                    hook_voice=hook_voice,
                    quote_voice=quote_voice,
                    cta_voice=cta_voice,
                    music_path=music_path,
                    hook_words=hook_words,
                    quote_words=quote_words,
                    cta_words=cta_words,
                    bridge=bridge_text,
                    bridge_voice=bridge_voice,
                    bridge_words=bridge_words,
                    background=bg_path,
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
    if post_row_id is not None:
        record_trigger_keyword(post_row_id, _extract_trigger_keyword(cta_text))
        record_arc(post_row_id, quote_data.get("arc"))

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
        # post_id is UNIQUE — a bare "PENDING_MANUAL" collides on the 2nd manual
        # post ever. Suffix with the row id so each pending-manual row is unique.
        mark_posted(post_row_id, f"PENDING_MANUAL_{post_row_id}", None, _rel_path(reel_path))
    elif not dry_run and reel_path:
        log.info("Step: Posting POV Reel to Instagram...")
        try:
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
            mark_posted(post_row_id, post_id, None, _rel_path(reel_path))
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
        except Exception as e:
            log.error(f"Publish failed: {e} — releasing slot {slot} for retry")
            release_post(post_row_id)
            raise
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
        "reel_path": _rel_path(reel_path),
        "post_id": post_id,
        "dry_run": dry_run,
        "pov": True,
    }
    save_log(record)
    log.info("▶ POV Pipeline complete")
    return record


def _reels_use_remotion(reel: bool, carousel: bool, remotion: bool, pov: bool) -> bool:
    """Every reel renders via the Remotion path (_run_pov_reel: Remotion+FLUX+
    edge-tts). The ffmpeg generate_reel + OpenAI-TTS reel path is retired.
    Non-reel (image) and carousel posts are unaffected."""
    return pov or remotion or (reel and not carousel)


def run_pipeline(dry_run: bool = False, reel: bool = False, manual: bool = False, studio: bool = False,
                  carousel: bool = False, pov: bool = False, remotion: bool = False,
                  seed: int | None = None, content: str | None = None, team: bool = False):
    # All reels take the Remotion+FLUX path; --remotion still forces it too.
    # Falls back to the ffmpeg POV generator (edge-tts, never OpenAI) only if
    # Node/Remotion is unavailable.
    pov = _reels_use_remotion(reel, carousel, remotion, pov)
    cfg = Config()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log.info(f"▶ HYBRID Pipeline start | dry_run={dry_run} reel={reel} manual={manual} carousel={carousel}")

    # Initialize SQLite state store
    init_db()

    # Get valid Meta token (auto-refreshes if needed)
    access_token = get_valid_token_with_fallback(cfg)

    # ── Pre-flight guard: skip if this slot already posted today ──────────────
    slot = _current_slot()
    # Dry runs publish nothing — never block them on the slot dedup guard.
    if not dry_run and has_posted_today(slot):
        log.info(f"⏭ Slot {slot} already posted today — skipping")
        return {"skipped": True, "reason": f"slot {slot} already posted today"}

    # ── Content stage: injected JSON > AI Creative Studio > legacy fallback ────
    studio_decision = None
    flux_override = ""
    controversy = ""
    caption_variant = -1
    if content:
        log.info(f"Step 1: Injected content from {content}")
        try:
            quote_data, mood = _injected_content(content, cfg)
        except Exception as e:  # noqa: BLE001
            log.error(f"--content unreadable ({e}) — falling back to legacy")
            content = None
        else:
            studio_decision = None
            controversy = ""
            caption_variant = -1
    elif studio:
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

    elif team:
        log.info("Step 1: Team system content...")
        try:
            from team.bridge import load_team_post
            slot_for_team = _current_slot()
            team_quote_data = load_team_post(slot=slot_for_team)
            if team_quote_data is None:
                log.info("  [team] no plan found — falling back to legacy")
                team = False
            else:
                # Team provides the quote_id; fetch the actual quote text from excel
                from src.core.excel_reader import get_quote_by_row
                quote_text = get_quote_by_row(team_quote_data["row_number"])
                if quote_text:
                    team_quote_data["quote"] = quote_text
                else:
                    log.warning("  [team] quote not found in excel — using plan copy")
                    team_quote_data["quote"] = team_quote_data.get("quote", "The only true wisdom is in knowing you know nothing.")
                quote_data = team_quote_data
                mood = quote_data["mood"]
                controversy = ""
                caption_variant = -1
                flux_override = quote_data.get("flux_override", "")
                log.info(f"  [team] content ready — mood={mood}, "
                         f"hook={quote_data.get('hook', '')[:40]!r}")
        except Exception as e:
            log.warning(f"[team] stage failed ({type(e).__name__}: {e}) — falling back to legacy")
            team = False

    if not content and not team and studio_decision is None:
        log.info("Step 1: Reading quote + legacy templated content...")
        quote_data, mood, controversy, caption_variant = _legacy_content(cfg)

    quote_data = _apply_trend_scout(cfg, quote_data)

    # ── Controversy Engine: make the content provocative ────────────────────────
    # Transform safe quotes into bold modern interpretations (roast/verdict/debate)
    # Only runs when studio or AI content is available (needs Claude API)
    if not content and not dry_run and cfg.ANTHROPIC_API_KEY:
        try:
            from src.content.controversy_engine import generate_controversy, pick_mode, DEFAULT_TARGETS
            import random as _rng
            slot_num = _current_slot()
            trend_topic = quote_data.get("trend_topic", "")
            mode = pick_mode(slot_num, trend_available=bool(trend_topic))
            target = _rng.choice(DEFAULT_TARGETS) if not trend_topic else trend_topic

            # Build a lightweight client for the controversy call
            from studio.client import StudioClient
            controversy_client = StudioClient(cfg.ANTHROPIC_API_KEY)

            result = generate_controversy(
                client=controversy_client,
                quote=quote_data["quote"],
                mode=mode,
                target=target,
                trend=trend_topic,
            )
            if result:
                # Override hook and caption with provocative versions
                if result.get("hook"):
                    quote_data["hook"] = _enforce_hook_len(result["hook"])
                if result.get("caption"):
                    quote_data["caption"] = result["caption"]
                if result.get("cta"):
                    quote_data["cta"] = result["cta"]
                if result.get("hashtags"):
                    quote_data["hashtags"] = result["hashtags"]
                quote_data["format"] = mode  # roast/verdict/debate
                log.info(f"  [controversy] {mode} mode: hook={result.get('hook','')[:50]!r}")
        except Exception as e:
            log.warning(f"  [controversy] engine unavailable ({e}) — using standard hooks")

    # ── Phase 1: Inject viral engagement into caption ───────────────────────────
    # Use CTA tracker to pick the best CTA type based on historical performance
    try:
        from src.analytics.cta_tracker import recommend_cta_type
        best_cta = recommend_cta_type(quote_data["audience"])
        bait = CommentBait(audience=quote_data["audience"], mood=mood)
        engagement_block = bait.generate_full_engagement_block(
            quote=quote_data["quote"],
            include_question=True,
            include_cta=True,
            include_booster=False,
        )
    except Exception:
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
    if post_row_id is not None:
        # cta_text isn't built yet on this path — the trigger (if any) lives in
        # the studio cta or the caption's engagement block.
        record_trigger_keyword(post_row_id, _extract_trigger_keyword(
            (quote_data.get("cta") or "") + " " + (quote_data.get("caption") or "")))

    if post_row_id is None:
        log.warning(
            f"  [dedup] slot {slot} already claimed today (concurrent run) — "
            f"skipping to avoid a double-post"
        )
        return {"skipped": True, "reason": f"slot {slot} already claimed today"}

    # Stamp a stable, edit-surviving reconcile marker on caption + proposal.
    if studio_decision is not None and post_row_id is not None:
        _token = reconcile_token(post_row_id)
        quote_data["caption"] = f"{quote_data['caption']}\n{_token}"
        studio_decision.visual_direction["caption_marker"] = _token

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

        # Mark as ready (not fully posted yet). post_id is UNIQUE — a bare
        # "PENDING_MANUAL" collides on the 2nd manual post; suffix with the row id.
        mark_as_posted(EXCEL_PATH, quote_data["row_number"], "PENDING_MANUAL")
        mark_posted(post_row_id, f"PENDING_MANUAL_{post_row_id}", _rel_path(final_image_path), _rel_path(reel_path))

    elif not dry_run:
      try:
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
        mark_posted(post_row_id, post_id, _rel_path(final_image_path), _rel_path(reel_path))

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
      except Exception as e:
        log.error(f"Publish failed: {e} — releasing slot {slot} for retry")
        release_post(post_row_id)
        raise
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
        "image_path":      _rel_path(final_image_path),
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
    parser.add_argument("--content", type=str, default=None,
                        help="Path to a JSON file of hand-crafted reel content "
                             "(hook/bridge/quote/cta/caption/hashtags/mood); bypasses excel+studio.")
    parser.add_argument("--team", action="store_true", help="Use the 8-agent team system's approved plan for today; falls back to legacy if no plan exists.")
    args = parser.parse_args()

    if args.batch:
        from src.video.batch_generator import generate_batch
        generate_batch()
    elif args.manual:
        # --manual implies --reel (generate video) but skips API posting
        run_pipeline(dry_run=False, reel=True, manual=True, studio=args.studio,
                     pov=args.pov, remotion=args.remotion, seed=args.seed, content=args.content,
                     team=args.team)
    else:
        run_pipeline(dry_run=args.dry_run, reel=args.reel, studio=args.studio,
                     carousel=args.carousel, pov=args.pov, remotion=args.remotion, seed=args.seed,
                     content=args.content, team=args.team)
