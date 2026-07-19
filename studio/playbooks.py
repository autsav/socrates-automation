"""Distilled domain-expert playbooks embedded in agent prompts (spec 1.1).
Module constants so tests can assert coverage and agents can compose them."""

STORY_CRAFT = (
    "NARRATIVE CRAFT (non-negotiable):\n"
    "- Open a curiosity gap in beat one and don't close it until the quote: the "
    "viewer must NEED the resolution.\n"
    "- Escalation ladder: every 1-2 sentences raise the stakes or the strangeness. "
    "Never repeat a beat at the same intensity.\n"
    "- Concrete-image rule: no abstraction where an image works. 'He ate stale "
    "bread on a marble floor' beats 'he practiced discomfort'.\n"
    "- The earned twist: the quote only lands if the story built its exact need. "
    "Pick the quote FIRST, then engineer the story toward it.\n"
    "- Send-psychology: the viewer shares to say something about THEMSELVES or "
    "their friend. End on a line that gives them those words.\n"
    "- Rhythm: short punchy sentences, a new mini-revelation every ~8 seconds."
)

COPY_CRAFT = (
    "COPY CRAFT (non-negotiable):\n"
    "- Statement hooks beat questions: assert something that sounds wrong, then "
    "prove it.\n"
    "- PAS captions: Problem (their words) -> Agitate (the cost tonight) -> Solve "
    "(the Stoic reframe).\n"
    "- First line <=8 words, curiosity gap, no hashtags — it is the only line "
    "shown before the fold.\n"
    "- Weave SEO keywords (discipline, stoic mindset, stop procrastinating) so "
    "naturally a reader never notices them.\n"
    "- One-reader rule: write to a single person at 2am, not an audience."
)

TREND_CRAFT = (
    "NEWSJACKING CRAFT (non-negotiable):\n"
    "- Recency beats importance: a 6-hour-old mid story outranks a 3-day-old big "
    "one.\n"
    "- The philosophy-bridge test: can a Stoic quote GENUINELY reframe this? If "
    "the bridge needs forcing, reject the trend — a forced bridge reads as spam.\n"
    "- Emotional charge beats scale: pick the story people are ARGUING about, "
    "not the biggest headline.\n"
    "- Specific numbers from the headline go in the hook verbatim."
)

MUSIC_CRAFT = (
    "SYNC SUPERVISION CRAFT (non-negotiable):\n"
    "- Energy-arc matching: the track's build must peak where the quote lands — "
    "search for builds, swells, drops; avoid flat loops.\n"
    "- Mood->instrument mapping: dark_philosophical = low strings/drones; "
    "cinematic_hopeful = piano+swell; epic_warrior = percussion.\n"
    "- Never vocal tracks under narration; melody fights the voice.\n"
    "- Under 90s reels, prefer tracks whose first 60s carry the full arc."
)

STRATEGY_CRAFT = (
    "POSITIONING CRAFT (non-negotiable):\n"
    "- The account promise: 'Short resets for people rebuilding discipline.' "
    "Every brief serves one of 3 pillars: trend/debate stories with a Stoic "
    "twist; weird philosophy history; the 3-line reset (funnel).\n"
    "- Audience-fatigue rotation: never brief the same audience twice in a row; "
    "check recent posts before choosing.\n"
    "- Specificity of pain: brief the 2am symptom ('reopened the app you just "
    "closed'), not the category ('procrastination')."
)
