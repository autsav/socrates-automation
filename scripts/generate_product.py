#!/usr/bin/env python
"""Generate 'The Stoic Reset Journal' — the £12 Gumroad product.

One-shot: Claude writes the journal content (schema-validated JSON) → branded
HTML (scripts/product_template.html, gold-on-dark reels brand) → PDF via
headless Chrome → sent to Telegram for approval. Content JSON + HTML are kept
next to the PDF so it can be re-rendered/edited without re-paying for tokens.

Run:  .venv/bin/python scripts/generate_product.py            # full run
      .venv/bin/python scripts/generate_product.py --render-only  # re-render from saved JSON

Then (manual, one-time): upload output/product/stoic_reset_journal.pdf to
Gumroad at £12, set the IG bio link to the Gumroad URL.
"""

from src.utils.logger import get_logger
logger = get_logger(__name__)

import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT_DIR = Path(__file__).parent.parent / "output" / "product"
TEMPLATE = Path(__file__).parent / "product_template.html"

CONTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "intro": {"type": "array", "items": {"type": "string"}},
        "protocol": {"type": "array", "items": {"type": "string"}},
        "protocol_explainer": {"type": "array", "items": {"type": "string"}},
        "daily_pages": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "quote": {"type": "string"},
                    "attribution": {"type": "string"},
                    "prompts": {"type": "array", "items": {"type": "string"}},
                    "micro_action": {"type": "string"},
                },
                "required": ["quote", "attribution", "prompts", "micro_action"],
            },
        },
        "seven_day": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"theme": {"type": "string"}, "instruction": {"type": "string"}},
                "required": ["theme", "instruction"],
            },
        },
        "closing": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "subtitle", "intro", "protocol", "protocol_explainer",
                 "daily_pages", "seven_day", "closing"],
}


def validate_content(content: dict) -> tuple[bool, str]:
    """Minimal structural validation against CONTENT_SCHEMA (no jsonschema dep)."""
    try:
        for key in CONTENT_SCHEMA["required"]:
            if key not in content:
                return False, f"missing key: {key}"
        if len(content["protocol"]) != 3:
            return False, "protocol must be exactly 3 lines"
        if len(content["daily_pages"]) != 21:
            return False, f"daily_pages must be 21, got {len(content['daily_pages'])}"
        for i, d in enumerate(content["daily_pages"]):
            for k in ("quote", "attribution", "prompts", "micro_action"):
                if not d.get(k):
                    return False, f"daily_pages[{i}] missing {k}"
            if len(d["prompts"]) != 3:
                return False, f"daily_pages[{i}] needs 3 prompts"
        if len(content["seven_day"]) != 7:
            return False, "seven_day must be 7 entries"
        return True, "ok"
    except (TypeError, KeyError) as e:
        return False, f"malformed: {e}"


def _e(s: str) -> str:
    # Strip stray markdown emphasis the model sometimes adds, then escape.
    return html.escape((s or "").strip().strip("*_"))


def render_html(content: dict) -> str:
    """Content JSON → full HTML document in the reels' gold-on-dark brand."""
    pages = []
    # Cover
    pages.append(
        f'<div class="page cover"><div class="mark">✦</div>'
        f'<h1>{_e(content["title"])}</h1>'
        f'<div class="sub">{_e(content["subtitle"])}</div></div>')
    # Intro
    intro = "".join(f"<p>{_e(p)}</p>" for p in content["intro"])
    pages.append(f'<div class="page"><div class="eyebrow">Why resets fail</div>'
                 f'<h2>Read this first</h2><div class="body-text">{intro}</div></div>')
    # Protocol
    lines = "".join(f'<div class="protocol-line">{_e(l)}</div>' for l in content["protocol"])
    expl = "".join(f"<p>{_e(p)}</p>" for p in content["protocol_explainer"])
    pages.append(f'<div class="page"><div class="eyebrow">The 3-line reset</div>'
                 f'<h2>The Protocol</h2>{lines}'
                 f'<div class="body-text" style="margin-top:8mm">{expl}</div></div>')
    # 21 daily pages
    for i, d in enumerate(content["daily_pages"], 1):
        prompts = "".join(
            f'<div class="prompt">{_e(p)}</div><div class="lines"></div><div class="lines"></div>'
            for p in d["prompts"])
        pages.append(
            f'<div class="page"><div class="daynum">DAY {i:02d} / 21</div>'
            f'<div class="quote">“{_e(d["quote"])}”</div>'
            f'<div class="attr">{_e(d["attribution"])}</div>'
            f'{prompts}'
            f'<div class="micro"><b>Micro-action:</b> {_e(d["micro_action"])}</div></div>')
    # 7-day program
    days = "".join(
        f'<div class="prompt"><b style="color:#d8b25c">Day {i}. {_e(s["theme"])}</b><br>'
        f'{_e(s["instruction"])}</div>'
        for i, s in enumerate(content["seven_day"], 1))
    pages.append(f'<div class="page"><div class="eyebrow">When it all slips</div>'
                 f'<h2>The 7-Day Reset</h2><div class="body-text">{days}</div></div>')
    # Closing
    closing = "".join(f"<p>{_e(p)}</p>" for p in content["closing"])
    pages.append(f'<div class="page"><div class="eyebrow">Keep going</div>'
                 f'<h2>A last word</h2><div class="body-text">{closing}</div></div>')

    tpl = TEMPLATE.read_text()
    return tpl.replace("{title}", _e(content["title"])).replace("{pages}", "\n".join(pages))


_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "chromium", "chromium-browser",
]


def _find_chrome() -> str | None:
    for c in _CHROME_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    return None


def html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Render HTML → PDF via headless Chrome. False (no raise) when unavailable."""
    chrome = _find_chrome()
    if not chrome:
        logger.warning("[product] no Chrome/Chromium found — PDF step skipped")
        return False
    try:
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf_path}", str(html_path)],
            check=True, capture_output=True, timeout=120)
        return pdf_path.exists()
    except Exception as e:
        logger.info(f"[product] Chrome PDF render failed: {e}")
        return False


_GEN_PROMPT = """You are writing a premium paid product: "The Stoic Reset Journal" — a £12 PDF
for people who keep falling off track (procrastinators, doomscrollers, the overwhelmed)
sold from a Stoic-philosophy Instagram account.

Voice: a thoughtful, slightly stern Stoic mentor. Direct, warm, zero fluff, no
academic tone, no clichés ("dwell in the present moment" is banned). Modern
situations (phones, deadlines, 2am scrolling), ancient spine (Socrates, Epictetus,
Marcus Aurelius, Seneca — real quotes only, correctly attributed).

Produce JSON with EXACTLY this shape:
- title: "The Stoic Reset Journal"
- subtitle: one italic line that sells the promise
- intro: 3-4 short paragraphs on why resets fail (willpower myth) and how this journal works
- protocol: EXACTLY 3 lines — the 3-line Stoic Reset (memorable, imperative, ~8 words each)
- protocol_explainer: 2-3 paragraphs on how/when to run the 3 lines
- daily_pages: EXACTLY 21 items, each {quote, attribution, prompts (EXACTLY 3 short
  reflective questions tied to that quote), micro_action (one concrete <=2-minute act)}
  — 21 DIFFERENT real Stoic quotes, no repeats, arc from awareness (days 1-7) to
  discipline (8-14) to equanimity (15-21)
- seven_day: EXACTLY 7 items {theme, instruction} — an emergency reset week for
  when someone has completely fallen off
- closing: 1-2 paragraphs, ending warm but unsentimental

Output ONLY the JSON object."""


def generate_content(api_key: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": _GEN_PROMPT}],
        output_config={"format": {"type": "json_schema", "schema": CONTENT_SCHEMA}},
    )
    return json.loads(resp.content[0].text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-only", action="store_true",
                    help="Re-render HTML/PDF from the saved content JSON (no LLM call).")
    ap.add_argument("--no-telegram", action="store_true", help="Skip the Telegram send.")
    args = ap.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    content_path = OUT_DIR / "journal_content.json"
    html_path = OUT_DIR / "stoic_reset_journal.html"
    pdf_path = OUT_DIR / "stoic_reset_journal.pdf"

    if args.render_only:
        content = json.loads(content_path.read_text())
    else:
        from config import Config
        content = generate_content(Config().ANTHROPIC_API_KEY)
        ok, reason = validate_content(content)
        if not ok:
            logger.info(f"[product] generated content failed validation: {reason}")
            return 1
        content_path.write_text(json.dumps(content, ensure_ascii=False, indent=2))

    html_path.write_text(render_html(content))
    logger.info(f"[product] HTML: {html_path}")
    if html_to_pdf(html_path, pdf_path):
        logger.info(f"[product] PDF:  {pdf_path} ({pdf_path.stat().st_size // 1024} KB)")
        if not args.no_telegram:
            try:
                from config import Config
                from src.core.notifier import Notifier
                Notifier(Config()).send_document(
                    pdf_path,
                    caption="📓 The Stoic Reset Journal — review it. If it's good: "
                            "upload to Gumroad at £12 and set the bio link.")
                logger.info("[product] sent to Telegram for review")
            except Exception as e:
                logger.info(f"[product] Telegram send failed (PDF is on disk): {e}")
    logger.info("\nNext (manual): 1) review PDF  2) Gumroad upload £12  3) set IG bio link")
    return 0


if __name__ == "__main__":
    sys.exit(main())
