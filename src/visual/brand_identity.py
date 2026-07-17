"""Brand identity system — consistent visual identity for all content.

Creates a recognizable, ownable visual brand that makes the account
instantly identifiable in the feed. Without a face, the VISUAL IDENTITY
is what builds recognition.

Identity: "The Socratic Method"
- Consistent color palette (deep teal + amber + black)
- Consistent typography (Playfair Display + Inter)
- Consistent frame style (cinematic letterbox bars)
- Consistent opening (every Reel opens with the same 1-second brand sting)
- Recurring visual motif: a marble bust / Greek statue silhouette overlay

This module provides the constants + helpers that Remotion components
and image compositors use to enforce visual consistency.
"""

# ── Color Palette ────────────────────────────────────────────────────────────
# Deep, cinematic, premium-feeling. Inspired by Caravaggio lighting.
PALETTE = {
    "background":   "#0A0A12",  # Near-black with blue tint
    "primary":      "#1A3A4A",  # Deep teal
    "accent":       "#D4A24C",  # Amber/gold (Socratic warmth)
    "text_primary": "#F5F0E1",  # Warm white (not pure white)
    "text_secondary": "#8B8B9A",  # Muted grey-blue
    "danger":       "#C44536",  # Terracotta red (for confrontational content)
    "success":      "#7B9E89",  # Muted sage (for hopeful content)
}

# ── Typography ───────────────────────────────────────────────────────────────
# Playfair Display = serif, classical, philosophical
# Inter = sans-serif, modern, readable for body text
FONTS = {
    "display": "Playfair Display",     # Quotes, hooks (serif, elegant)
    "body":    "Inter",                # Captions, CTAs (clean, modern)
    "mono":    "JetBrains Mono",       # Stats, timestamps
}

# ── Frame Style ──────────────────────────────────────────────────────────────
# Cinematic letterbox bars top + bottom (like a film still)
LETTERBOX_HEIGHT_PCT = 0.08  # 8% of frame height for each bar

# ── Brand Sting ──────────────────────────────────────────────────────────────
# Every Reel opens with a 1-second brand sting before the hook
BRAND_STING_DURATION = 1.0  # seconds
BRAND_STING_TEXT = "THE SOCRATIC METHOD"
BRAND_STING_SUBTEXT = "Philosophy that punches back"

# ── Visual Motif ─────────────────────────────────────────────────────────────
# Marble bust / Greek statue silhouette overlay (subtle, in corner or faded)
MOTIF_ENABLED = True
MOTIF_OPACITY = 0.15  # Very subtle, doesn't distract from text
MOTIF_POSITION = "bottom_right"  # Where the motif sits in the frame

# ── Reel Structure ────────────────────────────────────────────────────────────
# Consistent scene structure for every Reel
REEL_STRUCTURE = {
    "sting":    {"duration": 1.0, "description": "Brand sting: logo text on black"},
    "hook":     {"duration": 3.0, "description": "Provocative hook text, large, center screen"},
    "bridge":   {"duration": 2.0, "description": "Optional: trend-to-philosophy bridge"},
    "quote":    {"duration": 5.0, "description": "The quote, elegant serif, slow reveal"},
    "attribution": {"duration": 1.5, "description": "— Socrates"},
    "cta":      {"duration": 2.5, "description": "Engagement trigger + brand watermark"},
}

# Total target Reel duration: 12-15 seconds (optimal for Instagram watch time)

# ── Format Identity ───────────────────────────────────────────────────────────
# Each format has its own visual signature
FORMAT_STYLES = {
    "roast": {
        "color_accent": PALETTE["danger"],    # Terracotta red
        "hook_prefix": "ROAST:",              # Shown briefly before hook text
        "emoji": "🔥",
    },
    "verdict": {
        "color_accent": PALETTE["accent"],    # Amber/gold
        "hook_prefix": "VERDICT:",
        "emoji": "⚖️",
    },
    "debate": {
        "color_accent": PALETTE["primary"],  # Deep teal
        "hook_prefix": "DEBATE:",
        "emoji": "⚔️",
    },
    "quote": {
        "color_accent": PALETTE["accent"],   # Amber/gold (classic)
        "hook_prefix": None,                  # No prefix for classic quotes
        "emoji": "🏛️",
    },
}


def get_format_style(format_type: str = "quote") -> dict:
    """Return the visual style for a given content format."""
    return FORMAT_STYLES.get(format_type, FORMAT_STYLES["quote"])


def get_reel_colors(format_type: str = "quote") -> dict:
    """Return the color scheme for a Reel based on its format."""
    style = get_format_style(format_type)
    return {
        "bg": PALETTE["background"],
        "text": PALETTE["text_primary"],
        "accent": style["color_accent"],
        "secondary": PALETTE["text_secondary"],
    }