"""
Content Format Generators — Points 23, 24.

Point 23: Quote vs Modern Context — bridge ancient → modern.
  "Socrates said this in 400 BC. It's about your Instagram addiction."

Point 24: Character Personification — first-person philosopher voice.
  "If Socrates had a podcast, here's episode 1..."
"""

import random
from typing import Literal


# ── Point 23: Modern Context Bridges ─────────────────────────────────────────

_MODERN_ANCHORS = [
    ("your Instagram addiction", "scrolling through Reels"),
    ("your inability to start", "procrastinating on that project"),
    ("your relationship with your phone", "checking notifications every 5 minutes"),
    ("your career anxiety", "doom-applying for jobs you don't really want"),
    ("your fear of judgment", "not posting because of what people might think"),
    ("your morning routine", "hitting snooze for the fifth time"),
    ("your need for validation", "checking likes before you've had coffee"),
    ("your overthinking", "that decision you've been putting off for months"),
    ("your comparison trap", "feeling behind everyone else on LinkedIn"),
    ("your distraction problem", "the 47 browser tabs you'll never close"),
]

_PHILOSOPHER_DATES = {
    "Socrates": "470 BC",
    "Plato": "428 BC",
    "Aristotle": "384 BC",
    "Marcus Aurelius": "121 AD",
    "Epictetus": "50 AD",
    "Seneca": "4 BC",
    "Diogenes": "412 BC",
    "Heraclitus": "535 BC",
}


def generate_modern_context(
    quote: str,
    philosopher: str = "Socrates",
    seed: int = 0,
) -> str:
    """
    Point 23: Generate a caption line bridging ancient quote to modern context.
    Returns a 1-2 sentence bridge for use in captions.
    """
    if seed:
        random.seed(seed)

    year = _PHILOSOPHER_DATES.get(philosopher, "2,400 years ago")
    modern_topic, modern_behaviour = random.choice(_MODERN_ANCHORS)

    templates = [
        f"{philosopher} wrote this in {year}. He was talking about {modern_topic}.",
        f"This was written in {year}. It describes {modern_behaviour} perfectly.",
        f"{philosopher} said this in {year}. We've had 2,000 years to listen. We haven't.",
        f"Ancient Greek. Totally about {modern_topic}.",
        f"Written in {year}. Still 100% about {modern_behaviour}.",
    ]
    return random.choice(templates)


def generate_modern_context_caption(
    quote: str,
    philosopher: str = "Socrates",
    engagement_question: str = "",
    seed: int = 0,
) -> str:
    """
    Full modern-context caption: hook + bridge + quote + question.
    """
    bridge = generate_modern_context(quote, philosopher, seed)
    parts = [
        f'"{quote}"',
        f"— {philosopher}",
        "",
        bridge,
    ]
    if engagement_question:
        parts.extend(["", engagement_question])
    return "\n".join(parts)


# ── Point 24: Character Personification ──────────────────────────────────────

_PERSONIFICATION_INTROS = {
    "Socrates": [
        "If Socrates had a podcast, here's episode 1:",
        "Imagine Socrates DMing you this at midnight:",
        "If Socrates left you a voicemail:",
        "Socrates, if he had a Twitter account, would have posted:",
        "If Socrates were your therapist, he'd start with:",
    ],
    "Marcus Aurelius": [
        "Marcus Aurelius wrote to himself every morning. Imagine he wrote to you:",
        "If Marcus Aurelius was your morning alarm notification:",
        "Emperor of Rome. Also would have had the most humbling newsletter.",
        "If Marcus Aurelius texted you at 5am:",
    ],
    "Epictetus": [
        "Epictetus was a former slave. He understood freedom better than anyone. Here's what he'd tell you:",
        "If Epictetus were your life coach:",
        "A man who owned nothing had everything figured out. He'd say:",
    ],
    "Seneca": [
        "Seneca wrote this to a friend who was wasting his life. He could have been writing to you:",
        "If Seneca saw your screen time report:",
        "Seneca on your busyness addiction:",
    ],
}

_PERSONIFICATION_CLOSERS = [
    "He asked this. 2,400 years of humans haven't answered it.",
    "He died for asking questions like this.",
    "The man died for this idea. What's your excuse for ignoring it?",
    "2,400 years old. Still waiting for your answer.",
    "He had no WiFi. No algorithm. Just this question.",
]


def generate_personification(
    quote: str,
    philosopher: str = "Socrates",
    seed: int = 0,
) -> str:
    """
    Point 24: Generate a personified first-person caption.
    Frames the quote as if the philosopher is speaking directly to the reader.
    """
    if seed:
        random.seed(seed)

    intros = _PERSONIFICATION_INTROS.get(philosopher, _PERSONIFICATION_INTROS["Socrates"])
    intro = random.choice(intros)
    closer = random.choice(_PERSONIFICATION_CLOSERS)

    # First-person reframe of the quote (simplified — keep quote but frame it)
    parts = [
        intro,
        "",
        f'"{quote}"',
        "",
        closer,
    ]
    return "\n".join(parts)


# ── Convenience: unified content format selector ──────────────────────────────

# ── Point 26: Behind-the-Scenes Content ──────────────────────────────────────

def generate_bts_caption(
    quote: str,
    philosopher: str = "Socrates",
    flux_prompt: str = "",
    mood: str = "",
) -> str:
    """
    Point 26: Generate a 'How this Reel was made' BTS caption.
    Surfaces the creative process for transparency + viral curiosity.
    """
    parts = [
        "Behind the scenes: how this post was made 👇",
        "",
        "1/ The quote was sourced from ancient philosophy texts",
        f'   📖 "{quote[:60]}{"..." if len(quote) > 60 else ""}"',
        f"   — {philosopher}",
        "",
        "2/ AI generated the background image",
    ]
    if flux_prompt:
        parts.append(f"   🎨 Prompt: \"{flux_prompt[:80]}\"")
    if mood:
        parts.append(f"   🎭 Mood: {mood}")
    parts.extend([
        "",
        "3/ Pillow + Python composed the typography",
        "4/ ffmpeg assembled the 15-second Reel",
        "",
        "Entire pipeline runs automatically. Zero editing.",
        "",
        "The question still hits the same. That's philosophy.",
    ])
    return "\n".join(parts)


# ── Point 27: Poll/Quiz Interactions ─────────────────────────────────────────

_QUIZ_TEMPLATES = [
    {
        "format": "poll",
        "question": "Which hits harder?",
        "options": ["A: The quote", "B: The question after it"],
        "cta": "Vote below 👇",
    },
    {
        "format": "quiz",
        "question": "What was Socrates actually famous for?",
        "options": ["A: Wisdom", "B: Asking questions he knew the answer to", "C: Annoying everyone"],
        "cta": "Comment your answer.",
    },
    {
        "format": "would_you_rather",
        "question": "Would you rather:",
        "options": [
            "A: Know everything but never grow",
            "B: Know nothing but grow every day",
        ],
        "cta": "Drop A or B.",
    },
    {
        "format": "this_or_that",
        "question": "This or that:",
        "options": ["A: Discipline > Motivation", "B: Motivation > Discipline"],
        "cta": "Which are you? Comment below.",
    },
]


def generate_poll_caption(quote: str = "", seed: int = 0) -> str:
    """
    Point 27: Generate a poll/quiz interaction caption.
    Use with Instagram's Poll or Quiz sticker in Stories.
    """
    if seed:
        random.seed(seed)
    template = random.choice(_QUIZ_TEMPLATES)
    lines = [
        template["question"],
        "",
    ]
    for opt in template["options"]:
        lines.append(f"  {opt}")
    lines.extend(["", template["cta"]])
    if quote:
        lines.extend(["", f'Context: "{quote[:60]}"'])
    return "\n".join(lines)


ContentFormat = Literal["standard", "modern_context", "personification", "myth_busting", "wwxs"]


def generate_caption_for_format(
    fmt: ContentFormat,
    quote: str,
    philosopher: str = "Socrates",
    engagement_question: str = "",
    seed: int = 0,
) -> str:
    """
    Return a caption in the requested format.
    Falls back to standard quote block.
    """
    if fmt == "modern_context":
        return generate_modern_context_caption(quote, philosopher, engagement_question, seed)
    elif fmt == "personification":
        text = generate_personification(quote, philosopher, seed)
        if engagement_question:
            text += f"\n\n{engagement_question}"
        return text
    elif fmt == "myth_busting":
        from src.hooks.pattern_interrupt import get_myth_busting_hook
        hook = get_myth_busting_hook(seed=seed)
        parts = [hook, "", f'"{quote}"', f"— {philosopher}"]
        if engagement_question:
            parts += ["", engagement_question]
        return "\n".join(parts)
    elif fmt == "wwxs":
        from src.hooks.pattern_interrupt import get_wwxs_hook
        wwxs = get_wwxs_hook(philosopher=philosopher, seed=seed)
        parts = [wwxs, "", f'"{quote}"', f"— {philosopher}"]
        if engagement_question:
            parts += ["", engagement_question]
        return "\n".join(parts)
    else:
        # Standard
        parts = [f'"{quote}"', f"— {philosopher}"]
        if engagement_question:
            parts += ["", engagement_question]
        return "\n".join(parts)
