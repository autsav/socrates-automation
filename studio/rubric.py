"""Deterministic quality scoring — the coded judge (spec 1.2).
Pure functions; higher is better; malformed input scores 0.0, never raises."""
import re

_ABSTRACTIONS = {
    "success", "mindset", "growth", "potential", "journey", "purpose",
    "greatness", "value", "energy", "abundance", "transformation",
}
_CONCRETE_HINTS = re.compile(
    r"\d|marble|bread|floor|barrel|rain|shoes|coin|cup|dirt|cloak|storm|2am|phone")
_SPECIFIC_CTA = re.compile(
    r"send this to (the|your|someone|a) ", re.I)


def _words(s):
    return re.findall(r"[A-Za-z']+", s or "")


def _sentence_lengths(text):
    parts = [p for p in re.split(r"[.!?]+", text or "") if p.strip()]
    return [len(_words(p)) for p in parts] or [0]


def score_story(d: dict) -> float:
    try:
        hook = d.get("beat_hook") or ""
        reframe = d.get("beat_reframe") or ""
        cta = d.get("beat_cta") or ""
        if not (hook and reframe and cta):
            return 0.0
        score = 0.0
        # Hook concreteness: images/numbers up, abstractions down.
        score += 2.0 * len(_CONCRETE_HINTS.findall(hook.lower()))
        score -= 1.5 * sum(w.lower() in _ABSTRACTIONS for w in _words(hook))
        if not hook.rstrip().endswith("?"):
            score += 1.0
        # Escalation rhythm: short mean sentence length in the story body.
        lens = _sentence_lengths(reframe)
        mean = sum(lens) / len(lens)
        score += max(0.0, 3.0 - (mean / 8.0))       # <=8-word sentences ideal
        score -= 1.0 * sum(w.lower() in _ABSTRACTIONS for w in _words(reframe)) / 10
        # CTA specificity: naming the receiver beats generic shares.
        if _SPECIFIC_CTA.search(cta):
            score += 2.0
        elif "send" in cta.lower():
            score += 0.5
        # Simplicity: penalize long words.
        all_words = _words(hook) + _words(reframe) + _words(cta)
        if all_words:
            long_frac = sum(len(w) > 8 for w in all_words) / len(all_words)
            score -= 3.0 * long_frac
        return round(score, 4)
    except Exception:  # noqa: BLE001 - judge must never crash the reel
        return 0.0


def score_concept(hook: str, caption: str) -> float:
    try:
        score = 0.0
        hook = hook or ""
        caption = caption or ""
        if hook and not hook.rstrip().endswith("?"):
            score += 1.0
        if len(_words(hook)) <= 12:
            score += 1.0
        score += 1.5 * len(_CONCRETE_HINTS.findall(hook.lower()))
        score -= 1.5 * sum(w.lower() in _ABSTRACTIONS for w in _words(hook))
        first = (caption.split("\n") or [""])[0]
        if 0 < len(_words(first)) <= 8:
            score += 1.0
        return round(score, 4)
    except Exception:  # noqa: BLE001
        return 0.0
