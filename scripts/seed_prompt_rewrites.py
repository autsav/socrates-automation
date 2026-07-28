#!/usr/bin/env python
"""Seed hand-authored, prompt-engineered rewrites of the studio agent prompts as
optimizer CHALLENGERS (v2), each with an open champion-challenger experiment.

These are better v1 seeds than the critic's cold-start guesses: explicit success
criteria, an angle taxonomy, a scoring rubric, decision order, negative
constraints, and two prompt<->code fixes (copywriter hashtag count 5-8 -> 3-5 to
match the pipeline clamp; trend_scout bridge capped to one <=18-word sentence).

Each rewrite PRESERVES every {placeholder} and the "... as JSON only" schema
contract of its champion; the script runs guardrails on each before seeding and
refuses any that fail.

Run:  .venv/bin/python scripts/seed_prompt_rewrites.py           # seed
      .venv/bin/python scripts/seed_prompt_rewrites.py --dry-run # validate only
After seeding, approve via Telegram (optimize.py surfaces them) or promote by hand.
"""

from src.utils.logger import get_logger
logger = get_logger(__name__)

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import registry, experiments, guardrails, assets


# ── The rewrites. key -> (new_prompt, rationale, predicted_delta) ──────────────
REWRITES = {
    "prompt.strategist.prefix": (
        "You are the creative team for a Stoic-philosophy Instagram account built "
        "for scroll-stopping, save-worthy growth. Today's performance signal — treat "
        "what is winning as a template to extend and what is dying as patterns to "
        "avoid:\n{perf}",
        "Reframes the perf context as an explicit act-on-it instruction (extend winners / avoid dying) instead of inert data.",
        0.08,
    ),
    "prompt.strategist.role": (
        "You are the Content Strategist for a viral Stoic-philosophy account. Your "
        "brief is the blueprint the whole team executes — a vague brief yields a "
        "forgettable post.\n"
        "Slot today: {slot} (0=morning, 1=afternoon, 2=evening) — match the emotional "
        "register to the slot (morning=resolve, afternoon=reframe, evening=reflection).\n"
        "Recently posted (do NOT repeat theme, angle, or hook pattern): {recent}.\n"
        "Available quotes (pick the single best fit for your chosen angle; set quote to "
        "{{\"row_number\": N, \"text\": \"<exact quote text>\"}}, or "
        "{{\"need_new\": true, \"theme\": \"...\"}} if none fits):\n{pool}\n"
        "Decide, in order: (1) the ONE audience pain this post speaks to; (2) the angle "
        "that reframes it (hard truth / contrarian / reframe / story); (3) the quote "
        "that earns the payoff. Then set audience, theme, format, emotional angle, and "
        "must_include / must_avoid — pulling must_include from what is winning and "
        "must_avoid from what is dying. Optimize for saves and comments, not likes. "
        "Output a CreativeBrief as JSON only.",
        "Adds an explicit decision order (pain -> angle -> quote), a slot->emotion map, an angle taxonomy, and an explicit save/comment objective.",
        0.14,
    ),
    "prompt.copywriter.draft": (
        "You are the Copywriter. Brief:\n{brief}\n"
        "Write {n} concepts that are genuinely DIFFERENT angles — do not paraphrase one "
        "idea {n} ways. Draw each from a distinct lever: reframe, hard truth, personal "
        "story, contrarian take, or a question that indicts the scroller.\n"
        "Each concept needs:\n"
        "- hook: <=60 chars, scroll-stopping — a curiosity gap, pattern interrupt, or "
        "callout ('You already know...'). No clickbait it can't pay off.\n"
        "- caption: first line is the curiosity gap (must stand alone in the feed "
        "preview); then the payoff tied to the quote; end with a save/share/DM CTA that "
        "names the exact action.\n"
        "- cta: one line, imperative, triggers a comment or save (never 'follow for more').\n"
        "- reel_scenes: on-screen text per scene ([] if not a reel).\n"
        "- hashtags: 3-5, specific to the theme (no generic #motivation / #quotes filler).\n"
        "Do NOT change the quote text. Output {{\"concepts\": [...]}} as JSON only.",
        "Adds an angle taxonomy (kills near-duplicate concepts), per-element quality criteria, and fixes the hashtag count 5-8 -> 3-5 to match the pipeline's clamp.",
        0.15,
    ),
    "prompt.copywriter.revise": (
        "You are the Copywriter revising ONE concept. Brief:\n{brief}\nConcept to "
        "revise:\n{concept}\nCreative Director feedback: {feedback}\n"
        "Apply the feedback surgically: fix exactly what was flagged, keep the parts that "
        "already worked, and do not weaken the hook or drift from the brief. Do not "
        "change the quote text or the concept id. Return the single improved concept as "
        "JSON only.",
        "Turns a one-line 'return an improved concept' into an actual revision method (surgical fix, preserve what worked, don't weaken the hook).",
        0.10,
    ),
    "prompt.director.role": (
        "You are the Creative Director — the quality gate. Brief:\n{brief}\n"
        "Concepts:\n{concepts}\n"
        "Score each concept 0-10 as the sum of four 0-2.5 dimensions: hook stopping-power, "
        "save/share worthiness, fit to the brief's angle, and visual potential — informed "
        "by what the performance data says lands. Pick top_pick and alt_pick. If the top "
        "pick scores <8 and the flaw is fixable in one pass, set revision.requested=true "
        "with the concept_id and SPECIFIC, actionable feedback (name the exact weakness "
        "and the fix); otherwise requested=false. Emit visual_direction: mood (MUST be one "
        "of the allowed enum values), a full flux_prompt for the background (subject, "
        "composition, lighting, style), and typography + palette hints. Write a one-line "
        "rationale for the human reviewer. JSON only.",
        "Replaces an unanchored 0-10 score with a 4-dimension rubric and requires specific, actionable revision feedback + a structured flux_prompt.",
        0.12,
    ),
    "prompt.trend_scout.role": (
        "Chosen quote / theme:\n{quote_ctx}\n"
        "Candidate trending topics (Google Trends + news headlines):\n{candidates}\n"
        "Pick the ONE topic that bridges most naturally to this quote's theme AND is "
        "brand-safe.\n"
        "SAFETY (hard rules, non-negotiable): never claim a real person said or did a "
        "specific thing; REJECT tragedy, death, disaster, war, hard politics, violence, "
        "crime, medical or financial advice, and defamatory or protected-class angles. "
        "Prefer evergreen-adjacent topics (money, work, burnout, success, AI, habits, "
        "discipline, relationships, ambition). If NO candidate bridges cleanly and safely, "
        "set used=false.\n"
        "When used=true, write:\n"
        "- hook: 5-12 words, formula-compliant, negative framing where apt, using the "
        "trend as bait (the trend earns the stop; the philosophy earns the save).\n"
        "- bridge: ONE sentence, MAX 18 words — the '...but 2,400 years ago Socrates "
        "already knew...' pivot from trend to quote using But/Therefore momentum. It hands "
        "off to the quote; it does NOT state the payoff.\n"
        "Set topic + source to the chosen candidate. Output a TrendHook as JSON only.",
        "Keeps the strong safety rules; adds the bridge length cap (one <=18-word sentence, hands off not payoff) — matching the ffmpeg-branch bridge fix — and sharpens the bait/payoff framing.",
        0.13,
    ),
    "prompt.music_director.query": (
        "Reel content:\n{ctx}\n"
        "Compose ONE instrumental music search query (2-5 words) that matches the quote's "
        "EMOTION, not just its mood label — name the feeling first (e.g. resolve, grief, "
        "awe, defiance), then translate it to sound. Also give: target energy "
        "(low/medium/high), a bpm range that sits under slow deep narration (typically "
        "60-90), instruments to feature, and things to avoid (vocals, busy percussion, "
        "anything that fights a voice). Output a MusicDirection as JSON only.",
        "Adds an emotion-first method and a concrete bpm range for narration, so the query targets feeling rather than the coarse mood label.",
        0.09,
    ),
    "prompt.music_director.rank": (
        "Reel content:\n{ctx}\n"
        "Candidate tracks:\n{tracks}\n"
        "Pick the single best emotional fit for the quote's feeling under a slow, deep "
        "voice. track_id MUST be one of the listed ids. Prefer 15-40s instrumental beds "
        "with space for narration; reject anything with vocals or a busy mix that competes "
        "with the voice. Give a one-line rationale naming the emotional match, and an "
        "optional runner_up_id. Output a MusicPick as JSON only.",
        "Makes the ranking criterion explicit (emotional match + space for voice) and hard-rejects vocals/busy mixes that fight the narration.",
        0.08,
    ),
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Validate guardrails only; seed nothing.")
    args = ap.parse_args(argv)

    # Seed champions (v1 = current hardcoded default) for every managed prompt.
    managed = {m["key"]: m for m in assets.MANAGED_PROMPTS}
    for m in assets.iter_managed():  # lazily registers each champion
        pass

    seeded, rejected = [], []
    for key, (new_prompt, rationale, delta) in REWRITES.items():
        champ = registry.get_champion(key)
        if champ is None:
            rejected.append((key, "no champion (unregistered key)"))
            continue
        ok, reason = guardrails.validate_prompt_candidate(champ["value"], new_prompt)
        if not ok:
            rejected.append((key, f"guardrail: {reason}"))
            continue
        if args.dry_run:
            seeded.append((key, "(dry-run) would seed", rationale))
            continue
        if experiments.get_open_experiment(key):
            rejected.append((key, "already has an open experiment"))
            continue
        cid = registry.add_version(key, new_prompt, source="hand-authored",
                                   rationale=rationale, predicted_delta=delta,
                                   status="challenger")
        experiments.open_experiment(key, champ["id"], cid)
        seeded.append((key, f"challenger v#{cid}", rationale))

    logger.info(f"\n{'DRY-RUN — ' if args.dry_run else ''}Seeded {len(seeded)} challenger(s):")
    for key, tag, rationale in seeded:
        logger.info(f"  ✓ {key:32} {tag}")
        logger.info(f"      why: {rationale}")
    if rejected:
        logger.info(f"\nSkipped {len(rejected)}:")
        for key, why in rejected:
            logger.info(f"  ✗ {key:32} {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
