"""
Image Generator — uses Fal.ai FLUX model to generate cinematic backgrounds.
Cost: ~$0.003 per image. 30 posts/month ≈ £0.07.
"""

import os
import time
import random
import requests
import httpx
from pathlib import Path

# ── Mood → image prompt map ───────────────────────────────────────────────────
MOOD_PROMPTS = {
    "dark_philosophical": (
        "Ancient Greek marble temple ruins at twilight, dramatic storm clouds parting, "
        "single golden shaft of light illuminating cracked stone columns, dark moody atmosphere, "
        "cinematic composition, hyper-detailed texture, 4k, vertical composition, tall frame"
    ),
    "dramatic_ancient": (
        "Ancient Athens at night, torches casting flickering light on wet stone streets, "
        "temple columns carved with weathered Greek key patterns, shadow of a philosopher, "
        "epic chiaroscuro lighting, oil painting texture, highly detailed, 4k, vertical composition"
    ),
    "cinematic_hopeful": (
        "Greek cliffside overlooking Aegean sea at golden hour, warm amber light rays "
        "piercing through mist, ancient marble columns silhouetted against the sun, "
        "wildflowers growing between stone cracks, hopeful cinematic mood, "
        "ultra detailed, atmospheric, 4k, vertical composition"
    ),
    "stark_minimal": (
        "Stark white marble surface with textural veining, single ancient Greek bronze urn, "
        "harsh dramatic side lighting from one window, deep black shadows on the opposite side, "
        "minimalist composition, high contrast studio photography style, 4k, vertical composition"
    ),
    "epic_warrior": (
        "Ancient Greek Spartan warrior standing on rocky mountain peak at sunrise, "
        "dramatic crimson and amber sky, spear silhouetted against the sun, "
        "epic scale, mist in the valley below, heroic composition, "
        "cinematic lighting, textured oil painting, 4k, vertical composition"
    ),
    "mystical_greek": (
        "Mystical ancient Greek ruins reflected in still midnight water, full moon illuminating "
        "marble columns, ethereal fog drifting across the surface, deep indigo and violet tones, "
        "fireflies in the foreground, fantasy atmosphere, ultra detailed, 4k, vertical composition"
    ),
    "calm_stoic": (
        "Peaceful ancient Greek garden at dawn, olive trees with silver-green leaves, "
        "weathered stone path leading to a distant temple, soft golden morning light "
        "filtering through branches, calm serene mood, impressionist painting style, "
        "gentle color palette, highly detailed, 4k, vertical composition"
    ),
}

FAL_API_URL = "https://fal.run/fal-ai/flux/schnell"

# ── Negative prompt to suppress common artifacts ──────────────────────────────
NEGATIVE_PROMPT = (
    "modern objects, text, watermark, blurry, low quality, people, faces, hands, "
    "cartoon, anime, oversaturated, oversharpened, deformed architecture"
)

# ── Dynamic prompt enhancement ───────────────────────────────────────────────
def enhance_prompt(mood: str, quote: str, api_key: str = "") -> str:
    """
    Ask Claude Haiku to rewrite the base mood prompt with 1–2 specific visual
    elements drawn from the quote's themes. Returns the enhanced prompt.
    Falls back to the base prompt on any error or if no API key.
    """
    base_prompt = MOOD_PROMPTS.get(mood, MOOD_PROMPTS["dark_philosophical"])
    if not api_key:
        return base_prompt

    system = (
        "You are a cinematic art director. Rewrite the given image prompt by weaving "
        "in ONE specific visual metaphor or scene detail inspired by the quote. "
        "Keep the output under 80 words. Return ONLY the rewritten prompt. No preamble."
    )
    user = f"Quote: {quote[:200]}\nBase prompt: {base_prompt}"

    try:
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        with httpx.Client(transport=transport) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 150,
                    "temperature": 0.7,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=15,
            )
            resp.raise_for_status()
            enhanced = resp.json()["content"][0]["text"].strip()
            # Strip markdown fences if present
            if enhanced.startswith("```"):
                enhanced = enhanced.split("\n", 1)[1]
            if enhanced.endswith("```"):
                enhanced = enhanced.rsplit("\n", 1)[0]
            enhanced = enhanced.strip()
            if enhanced and len(enhanced) > 40:
                print(f"  [image] Claude-enhanced prompt ({len(enhanced)} chars)")
                return enhanced
    except Exception as e:
        print(f"  [image] Prompt enhancement failed ({e}) — using base prompt")

    return base_prompt


def _generate_with_retry(headers, payload, max_retries=2):
    """Post to Fal.ai with retry on transient failures."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(FAL_API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"  [fal] Connection error, retrying in {wait}s...")
                time.sleep(wait)
            continue
        except requests.HTTPError as e:
            # Don't retry 4xx errors (bad request, auth failure)
            if e.response and 400 <= e.response.status_code < 500:
                raise
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                code = e.response.status_code if e.response is not None else "?"
                print(f"  [fal] HTTP {code}, retrying in {wait}s...")
                time.sleep(wait)
            continue
    raise last_error


def generate_background(
    mood: str,
    api_key: str,
    output_dir: str = "output",
    quote: str = "",
    anthropic_api_key: str = "",
) -> Path:
    """
    Generate background image via Fal.ai FLUX schnell.
    Uses native vertical aspect ratio, seed for reproducibility, negative prompt,
    and 6 inference steps for sharper detail. Optionally enhances prompt via Claude.
    Returns path to saved JPEG.
    """
    prompt = enhance_prompt(mood, quote, anthropic_api_key)

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }

    # Seed for reproducibility + variety
    seed = random.randint(0, 999999)

    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "image_size": "portrait_16_9",   # 576×1024 native vertical (9:16)
        "num_inference_steps": 6,          # sharper detail than 4
        "guidance_scale": 3.5,             # stronger prompt adherence
        "num_images": 1,
        "enable_safety_checker": True,
        "seed": seed,
    }

    print(f"  [image] Generating {mood} background (seed={seed}, steps=6)...")
    data = _generate_with_retry(headers, payload)

    # Extract image URL from response
    images = data.get("images", [])
    if not images:
        raise ValueError(f"Fal.ai returned no images. Response: {data}")

    image_url = images[0]["url"]

    # Download image
    img_response = requests.get(image_url, timeout=30)
    img_response.raise_for_status()

    raw_bytes = img_response.content
    if len(raw_bytes) < 10:
        raise ValueError(f"Downloaded image too small ({len(raw_bytes)} bytes) — likely corrupt")

    # Save to output dir
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    filename = output_path / f"bg_{mood}_{timestamp}.jpg"

    with open(filename, "wb") as f:
        f.write(raw_bytes)

    return filename


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    path = generate_background(
        "dark_philosophical",
        os.getenv("FAL_API_KEY"),
        quote="The unexamined life is not worth living.",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    )
    print(f"Saved: {path}")
