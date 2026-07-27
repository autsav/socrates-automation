"""
Prompt Architect — cinematic prompt engineering for FLUX image generation.

Enhances base mood prompts with:
  - Quote-derived visual metaphors (Claude-powered)
  - Cinematic composition directives
  - Style references (photography, painting, digital art)
  - Depth and atmosphere cues
  - Seasonal / timely variations

Usage:
    from src.prompts.architect import PromptArchitect
    architect = PromptArchitect(anthropic_api_key="...")
    prompt = architect.build(quote="Know thyself.", mood="mystical_greek")
"""

import random
import re
from typing import Literal

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PromptArchitect:
    """
    Build production-grade FLUX prompts that generate scroll-stopping backgrounds.
    """

    # Cinematic composition templates (appended for visual structure)
    COMPOSITIONS = [
        "rule of thirds, subject positioned at lower-left intersection",
        "symmetrical centered composition with vanishing point depth",
        "dramatic low angle looking upward, heroic scale",
        "foreground framing with out-of-focus stone ruins leading to distant subject",
        "aerial perspective, layers of atmospheric depth receding to mist",
        "extreme close-up texture detail with shallow depth of field",
        "diagonal leading lines from bottom-left to upper-right creating motion",
        "golden ratio spiral composition, focal point at terminus",
    ]

    # Lighting condition templates
    LIGHTING = [
        "volumetric god rays piercing through clouds, dust particles catching light",
        "chiaroscuro, single harsh light source creating deep shadows",
        "soft diffused overcast light with subtle rim lighting",
        "magic hour warm amber and violet sky gradient",
        "moonlight cool blue-white with warm torchlight contrast",
        "dramatic backlighting creating strong silhouettes",
        "dappled light filtering through ancient columns",
        "cinematic three-point lighting, key light warm, fill cool",
    ]

    # Texture and material quality boosters (photographic, not digital art)
    TEXTURE_BOOSTERS = [
        "photorealistic marble texture, natural weathering, real stone",
        "35mm film grain, Kodak Portra 800 color science, natural color",
        "photorealistic, subtle lens distortion, shallow depth of field",
        "real weathered bronze patina, oxidation patterns, natural metal",
        "real stone surface, natural water reflections, not rendered",
        "natural lighting, no studio lights, real-world atmosphere",
    ]

    # Atmosphere and mood enhancers
    ATMOSPHERE = [
        "heavy atmospheric haze creating depth separation",
        "mist rolling between ancient pillars, ethereal",
        "dust motes floating in shafts of light",
        "storm clouds parting dramatically overhead",
        "calm still water reflecting the scene perfectly",
        "wind-whipped fabric or leaves adding motion",
        "fire embers drifting upward in slow motion",
        "rain streaking diagonally across the frame",
    ]

    # Style references (rotated for variety)
    # Prioritize photographic realism over digital art to avoid AI-art suppression
    STYLE_REFS = [
        "cinematic film still, anamorphic lens, shot on Arri Alexa, natural color grading",
        "documentary photography, natural lighting, 35mm film grain, no retouching",
        "modern architectural photography, Phase One IQ4, realistic materials",
        "National Geographic travel photography, real-world composition",
        "cinematic color grading, muted teal and amber, Roger Deakins style",
        "black and white fine art photography, high contrast, Ansel Adams zone system",
        "golden hour landscape photography, natural sun flare, atmospheric perspective",
        "minimalist real-world photography, concrete and stone textures, natural light",
    ]

    # Seasonal variations (can be overridden)
    SEASONAL_CUES = {
        "spring": "wildflowers blooming between stone cracks, fresh green growth",
        "summer": "harsh bright sunlight, deep shadows, dry golden grass",
        "autumn": "falling amber leaves, warm copper tones, crisp air",
        "winter": "frost on marble surfaces, bare branches, pale blue light",
    }

    def __init__(self, anthropic_api_key: str = ""):
        self.api_key = anthropic_api_key

    def build(
        self,
        quote: str,
        mood: str,
        base_prompt: str = "",
        style: Literal["photorealistic", "painterly", "digital_art", "cinematic", "mixed"] = "mixed",
        season: str = "",
        seed: int = 0,
        trend_topic: str = "",
    ) -> str:
        """
        Build a full cinematic prompt from a quote and mood.

        Args:
            quote: The Socrates quote to draw visual metaphors from
            mood: Visual mood key
            base_prompt: Optional base prompt (if provided, enhancement is additive)
            style: Visual rendering style preference
            season: Optional seasonal cue (spring/summer/autumn/winter)
            seed: For reproducible random choices
        """
        if seed:
            random.seed(seed)

        # Start with base or generate from quote
        if base_prompt:
            core = base_prompt
        else:
            core = self._derive_visual_metaphor(quote, mood)

        # Weave a trending-topic subject in when supplied (mood still drives style).
        if trend_topic:
            core = f"a cinematic scene evoking {trend_topic}, {core}"

        # Build enhancement layers
        enhancements = []

        # Composition
        enhancements.append(random.choice(self.COMPOSITIONS))

        # Lighting
        enhancements.append(random.choice(self.LIGHTING))

        # Texture
        enhancements.append(random.choice(self.TEXTURE_BOOSTERS))

        # Atmosphere
        enhancements.append(random.choice(self.ATMOSPHERE))

        # Style reference (only if mixed or explicitly chosen)
        if style == "mixed":
            enhancements.append(random.choice(self.STYLE_REFS))
        elif style == "photorealistic":
            enhancements.append("photorealistic, shot on Phase One IQ4, 80mm lens")
        elif style == "painterly":
            enhancements.append(random.choice([
                "classical oil painting, visible brushstrokes, rich pigment",
                "Renaissance masterwork, sfumato technique, warm undertones",
            ]))
        elif style == "digital_art":
            enhancements.append("digital matte painting, concept art, ArtStation trending")
        elif style == "cinematic":
            enhancements.append("cinematic color grading, anamorphic lens characteristics, film grain")

        # Seasonal
        if season and season in self.SEASONAL_CUES:
            enhancements.append(self.SEASONAL_CUES[season])

        # Final quality boosters (always included)
        enhancements.append("8k resolution, hyper-detailed, trending on ArtStation")

        # Combine
        prompt = f"{core}, {', '.join(enhancements)}"

        # Clean up: remove duplicates, ensure proper punctuation
        prompt = self._clean_prompt(prompt)

        return prompt

    def _derive_visual_metaphor(self, quote: str, mood: str) -> str:
        """
        Derive a visual scene from quote themes using keyword mapping.
        Falls back to mood-based defaults if no specific match.
        """
        quote_lower = quote.lower()

        # Theme keyword → visual metaphor mapping
        theme_visuals = {
            "know thyself": (
                "ancient Greek reflecting pool at twilight, mirror-perfect water "
                "reflecting weathered marble columns and a solitary figure's silhouette"
            ),
            "unexamined": (
                "dusty ancient library with shafts of light illuminating forgotten scrolls, "
                "a single open book casting long shadows"
            ),
            "wisdom": (
                "ancient olive tree with gnarled roots gripping marble ruins, "
                "golden light filtering through silver-green leaves"
            ),
            "discipline": (
                "Spartan training ground at dawn, worn stone steps leading upward, "
                "mist clinging to the ground, a single spear standing upright"
            ),
            "fear": (
                "darkened ancient passage with a single torch casting flickering light, "
                "shadows stretching long on wet stone walls"
            ),
            "death": (
                "weathered Greek tomb at sunset, wildflowers growing between cracked stone, "
                "warm amber light on weathered inscription"
            ),
            "truth": (
                "broken marble statue revealing a golden core beneath, "
                "light streaming through cracks in the stone"
            ),
            "patience": (
                "ancient sundial in overgrown garden, moss-covered but perfectly aligned, "
                "soft morning light showing the passage of time"
            ),
            "courage": (
                "lone warrior silhouette on cliff edge facing a storm, "
                "lightning illuminating ancient ruins in the valley below"
            ),
        }

        # Check for keyword matches
        for keyword, visual in theme_visuals.items():
            if keyword in quote_lower:
                return visual

        # Fallback: use mood-specific archetype scene
        return self._mood_fallback(mood, quote)

    def _mood_fallback(self, mood: str, quote: str) -> str:
        """Return a mood-appropriate fallback scene description."""
        fallbacks = {
            "dark_philosophical": (
                "ancient Greek temple ruins under a stormy twilight sky, "
                "single golden light beam illuminating cracked marble columns"
            ),
            "dramatic_ancient": (
                "ancient Athens street at night, torchlight flickering on wet cobblestones, "
                "shadow of a robed philosopher cast long on temple walls"
            ),
            "cinematic_hopeful": (
                "Greek cliffside overlooking Aegean sea at golden hour, "
                "warm light piercing through mist, ancient columns silhouetted against sun"
            ),
            "stark_minimal": (
                "stark white marble surface with dramatic single light source, "
                "deep black shadows, single ancient Greek bronze artifact"
            ),
            "epic_warrior": (
                "Spartan warrior standing on rocky peak at sunrise, "
                "dramatic crimson sky, spear silhouetted against blazing sun"
            ),
            "mystical_greek": (
                "mystical Greek ruins reflected in still midnight water, "
                "full moon illuminating marble columns, ethereal fog drifting"
            ),
            "calm_stoic": (
                "peaceful ancient Greek garden at dawn, olive trees, stone path "
                "leading to distant temple, soft golden morning light"
            ),
        }
        return fallbacks.get(mood, fallbacks["dark_philosophical"])

    def _clean_prompt(self, prompt: str) -> str:
        """Clean up prompt for FLUX ingestion."""
        # Remove excessive commas
        prompt = re.sub(r",\s*,", ",", prompt)
        # Remove duplicate phrases (simple check)
        prompt = re.sub(r"\b(\w+(?:\s+\w+){0,3})\s+\1\b", r"\1", prompt, flags=re.IGNORECASE)
        # Ensure ends with period or none (FLUX prefers no trailing punctuation)
        prompt = prompt.strip().rstrip(".,")
        return prompt

    def enhance_with_claude(self, base_prompt: str, quote: str) -> str:
        """Use Claude Haiku 4.5 to enrich a FLUX prompt with quote-derived metaphor.
        Falls back to base_prompt on any error. Never raises."""
        if not self.api_key or not _ANTHROPIC_AVAILABLE:
            return base_prompt

        system = (
            "You are a cinematic art director for ancient Greek philosophical content. "
            "Given a quote and a base image prompt, rewrite the prompt by weaving in "
            "ONE powerful visual metaphor inspired by the quote's meaning. "
            "Keep the output under 60 words. Return ONLY the rewritten prompt. No preamble."
        )
        user = f"Quote: {quote[:200]}\nBase prompt: {base_prompt}"

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=150,
                temperature=0.7,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            enhanced = resp.content[0].text.strip()
            # Strip fences
            if enhanced.startswith("```"):
                enhanced = enhanced.split("\n", 1)[1]
            if enhanced.endswith("```"):
                enhanced = enhanced.rsplit("\n", 1)[0]
            enhanced = enhanced.strip()
            if enhanced and len(enhanced) > 40:
                return enhanced
        except (anthropic.APIError, anthropic.APIConnectionError) as e:
            logger.info(f"  [prompt-architect] SDK error, fallback to base: {e}")
        except Exception as e:  # noqa: BLE001
            logger.info(f"  [prompt-architect] unexpected error: {e}")

        return base_prompt


# ── Convenience exports ────────────────────────────────────────────────────────

def build_prompt(quote: str, mood: str, **kwargs) -> str:
    """One-shot prompt builder."""
    architect = PromptArchitect()
    return architect.build(quote=quote, mood=mood, **kwargs)
