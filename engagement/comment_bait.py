"""
Comment-Bait System — generates engagement-optimized questions and CTAs.

Purpose: Trigger comments, saves, and shares through psychology.
Instagram's algorithm weights comments heavily in reach calculation.

Categories:
  - Direct questions (forces cognitive engagement)
  - Agree/Disagree frames (triggers identity defense)
  - "Tag someone" CTAs (drives shares)
  - "Save this" triggers (algorithmic boost)
  - Controversy bait (respectful but polarizing)
  - Fill-in-the-blank (participation = dopamine)

Usage:
    from engagement.comment_bait import CommentBait
    bait = CommentBait(audience="procrastinator", mood="dark_philosophical")
    question = bait.generate_question(quote="The unexamined life is not worth living.")
    cta = bait.generate_cta(style="save_bait")
"""

import random
from typing import Literal


class CommentBait:
    """Generate engagement-optimized prompts for Instagram captions."""

    # ── Question Templates by Audience Archetype ───────────────────────────────
    # Each audience has 4 question types: direct, reflective, confrontational, supportive

    QUESTIONS = {
        "procrastinator": {
            "direct": [
                "What's the one thing you've been putting off? Say it out loud in the comments.",
                "What's your excuse today? Be honest — no one here judges.",
                "What would you do if you knew you couldn't fail?",
                "What task have you been avoiding for over a month?",
            ],
            "reflective": [
                "What would your future self thank you for starting today?",
                "Think back to 3 years ago. What do you wish you'd started then?",
                "What small action would make tomorrow 1% better?",
            ],
            "confrontational": [
                "Still waiting for the 'right time'? It's not coming. What now?",
                "What's the real reason you're not moving? Fear? Comfort? Something else?",
                "How many more 'tomorrows' are you willing to waste?",
            ],
            "supportive": [
                "Drop a 🔥 if you're starting something today.",
                "Comment DONE if you took one step today. Let's celebrate it.",
                "What's one win you had this week? Big or tiny — doesn't matter.",
            ],
        },
        "doomscroller": {
            "direct": [
                "How many hours did you spend scrolling today? Be real.",
                "What are you actually looking for when you open Instagram?",
                "What's the last thing you learned from social media this week?",
            ],
            "reflective": [
                "If you got your screen time report right now, would you be proud?",
                "What would you create if you spent half your scroll time making things?",
                "What's something real you experienced today that wasn't on a screen?",
            ],
            "confrontational": [
                "The algorithm made you stop scrolling for this. What does that say?",
                "You just consumed 10 seconds of wisdom. Now what? Scroll again?",
                "Is your phone a tool or a leash? Be honest.",
            ],
            "supportive": [
                "Comment the last book you finished. Let's inspire each other.",
                "Drop a 🎯 if you're cutting screen time this week.",
                "Share one thing you're creating instead of consuming.",
            ],
        },
        "stuck": {
            "direct": [
                "What's the smallest possible step you could take right now?",
                "If you had to move in one direction today, which way?",
                "What are you pretending not to know?",
            ],
            "reflective": [
                "What did you used to dream about before life got complicated?",
                "If you could ask your future self one thing, what would it be?",
                "What's the door you're standing in front of? Describe it.",
            ],
            "confrontational": [
                "You're not stuck. You're choosing comfort. What changes if you admit that?",
                "How long are you going to replay the same problem before acting?",
                "What's the real fear — failure, or actually succeeding?",
            ],
            "supportive": [
                "Comment BREAK if you're finally ready to move.",
                "Drop one word describing where you want to be in one year.",
                "What's one thing you're proud of from the past month?",
            ],
        },
        "lazy": {
            "direct": [
                "What's the thing you know you should do but won't?",
                "What would you do with an extra hour of discipline every day?",
                "How do you waste your best energy hours?",
            ],
            "reflective": [
                "What would your life look like with 10% more discipline?",
                "When was the last time you felt proud of your effort?",
                "What's the habit you wish you'd built 5 years ago?",
            ],
            "confrontational": [
                "Comfortable or complacent? There's a difference. Which are you?",
                "You're not lazy. You're avoiding something. What is it?",
                "The couch doesn't judge you. But your future self might.",
            ],
            "supportive": [
                "Comment MOVE if you're getting up after reading this.",
                "What's one thing you're doing today that your future self will thank you for?",
                "Drop a 💪 if you chose discipline over comfort today.",
            ],
        },
        "quitter": {
            "direct": [
                "What made you want to quit? Say it — it loses power when spoken.",
                "What would you do if giving up wasn't an option?",
                "Who would you prove wrong if you kept going?",
            ],
            "reflective": [
                "Think about why you started. Does that reason still matter?",
                "What's the version of you that's still fighting? What do they need?",
                "What would finishing feel like? Picture it.",
            ],
            "confrontational": [
                "The world doesn't need another person who almost made it. Don't be that.",
                "Quitting is easy. Finishing is rare. Which do you want to be?",
                "You didn't come this far to stop now. What's really stopping you?",
            ],
            "supportive": [
                "Comment STAY if you're not giving up today.",
                "Drop one reason you're still in the fight.",
                "What's the win — big or small — that kept you going?",
            ],
        },
        "lost": {
            "direct": [
                "What direction feels right, even if you can't explain why?",
                "If you could do anything for the rest of your life, what would it be?",
                "What question are you afraid to ask yourself?",
            ],
            "reflective": [
                "What did you used to love before you got 'practical'?",
                "If you stripped away everyone's expectations, who are you?",
                "What's the path you secretly want to take?",
            ],
            "confrontational": [
                "You're not lost. You just haven't decided where you want to go.",
                "Waiting for clarity? Clarity comes from motion, not thinking.",
                "The map doesn't exist. Stop looking for it and start walking.",
            ],
            "supportive": [
                "Comment WALK if you're taking one step today, direction unknown.",
                "What's one thing that still excites you? Share it.",
                "Drop a 🧭 if you're searching for your path.",
            ],
        },
        "overwhelmed": {
            "direct": [
                "What's the one thing you need to drop right now?",
                "If you could only do ONE thing today, what matters most?",
                "What's on your plate that shouldn't be?",
            ],
            "reflective": [
                "When did you last feel truly at peace? What was different?",
                "What would your life look like with half the commitments?",
                "Who are you trying to be everything for?",
            ],
            "confrontational": [
                "You can't pour from an empty cup. Why are you still trying?",
                "Overwhelm is a signal, not a sentence. What is it telling you?",
                "You're saying yes to everyone else. When do you say yes to yourself?",
            ],
            "supportive": [
                "Comment BREATHE if you're taking a pause right now.",
                "Drop one thing you're letting go of this week.",
                "What's one boundary you're finally setting?",
            ],
        },
    }

    # ── CTA Templates ─────────────────────────────────────────────────────────

    CTA_TEMPLATES = {
        "save_bait": [
            "Save this for the moment you need it.",
            "Bookmark this. You'll need it later.",
            "Save this before the algorithm hides it.",
            "Screenshot this and read it when you're struggling.",
            "Put this in your saved folder. Future you is grateful.",
        ],
        "share_bait": [
            "Send this to someone who needs to hear it.",
            "Tag someone who's fighting a silent battle.",
            "Share this with the person you thought of while reading.",
            "Someone you know needs this right now. Send it.",
            "This post found you for a reason. Share it with who needs it.",
        ],
        "comment_bait": [
            "Drop a 🔥 if this resonated.",
            "Comment the first word that came to mind.",
            "Agree or disagree? Say it below.",
            "What's your take? The comments need your voice.",
            "Reply with one sentence that describes where you are right now.",
        ],
        "follow_bait": [
            "Follow for daily wisdom that punches you in the gut (in a good way).",
            "This is the kind of content you need in your feed daily. Follow.",
            "If this hit different, you know what to do.",
        ],
        "agree_disagree": [
            "Agree or disagree? There's no wrong answer — just yours.",
            "Some will hate this. Some will feel seen. Which are you?",
            "Controversial take: this is exactly what most people need to hear. Agree?",
            "This won't resonate with everyone. But if it hit you, you know why.",
        ],
        "fill_blank": [
            "Fill in the blank: The hardest part about changing is ________.",
            "Complete this: I feel most alive when ________.",
            "One word that describes your current chapter: ________",
            "The thing I'm avoiding is ________. There. I said it.",
        ],
    }

    # ── Emotional Resonance Boosters ───────────────────────────────────────────

    RESONANCE_BOOSTERS = [
        "If this hit you, you're not alone.",
        "This is for the ones who feel it but don't say it.",
        "Not everyone will get this. But you will.",
        "The right people always find this at the right time.",
        "If your chest tightened reading this, it means something.",
        "This isn't for everyone. It's for you.",
    ]

    def __init__(self, audience: str = "stuck", mood: str = "dark_philosophical"):
        """
        Args:
            audience: One of the 7 archetypes (procrastinator, doomscroller, etc.)
            mood: Visual mood of the content
        """
        self.audience = audience if audience in self.QUESTIONS else "stuck"
        self.mood = mood

    def generate_question(
        self,
        style: Literal["direct", "reflective", "confrontational", "supportive", "random"] = "random",
        quote: str = "",
    ) -> str:
        """
        Generate an engagement question tailored to the audience.
        """
        if style == "random":
            style = random.choice(["direct", "reflective", "confrontational", "supportive"])

        pool = self.QUESTIONS.get(self.audience, self.QUESTIONS["stuck"]).get(style, [])
        if not pool:
            pool = self.QUESTIONS["stuck"]["direct"]

        question = random.choice(pool)

        # 20% chance to add resonance booster
        if random.random() < 0.2:
            booster = random.choice(self.RESONANCE_BOOSTERS)
            question = f"{booster}\n\n{question}"

        return question

    def generate_cta(
        self,
        style: Literal["save_bait", "share_bait", "comment_bait", "follow_bait",
                         "agree_disagree", "fill_blank", "random"] = "random",
    ) -> str:
        """Generate a CTA optimized for a specific engagement type."""
        if style == "random":
            # Weight toward highest-ROI actions
            style = random.choices(
                ["save_bait", "share_bait", "comment_bait", "agree_disagree", "follow_bait", "fill_blank"],
                weights=[30, 25, 20, 15, 7, 3],
                k=1,
            )[0]

        pool = self.CTA_TEMPLATES.get(style, self.CTA_TEMPLATES["comment_bait"])
        return random.choice(pool)

    def generate_full_engagement_block(
        self,
        quote: str = "",
        include_question: bool = True,
        include_cta: bool = True,
        include_booster: bool = False,
    ) -> str:
        """
        Generate a complete engagement block for appending to captions.
        Returns a formatted string ready to append.
        """
        parts = []

        if include_booster or random.random() < 0.15:
            parts.append(random.choice(self.RESONANCE_BOOSTERS))

        if include_question:
            parts.append(self.generate_question(quote=quote))

        if include_cta:
            parts.append(self.generate_cta())

        return "\n\n".join(parts)


# ── Convenience exports ────────────────────────────────────────────────────────

def get_engagement_block(audience: str, quote: str = "", seed: int = 0) -> str:
    """One-shot engagement block generator."""
    if seed:
        random.seed(seed)
    cb = CommentBait(audience=audience)
    return cb.generate_full_engagement_block(quote=quote)
