"""Content safety guards beyond the topic denylist.

mentions_named_person() — the "contrarian about culture, never about people"
rule. Debate/story/weird copy may reference ancient philosophers (that's the
brand) and words that merely start sentences, but any take aimed at a living,
named individual is blocked. Heuristic, deliberately conservative: a false
positive costs one arc-downgrade; a false negative risks the account.
"""
from __future__ import annotations

import re

# Ancient/classical figures the brand legitimately discusses.
ALLOWED_FIGURES = {
    "socrates", "plato", "aristotle", "diogenes", "zeno", "seneca", "epictetus",
    "marcus", "aurelius", "marcus aurelius", "chrysippus", "pythagoras",
    "heraclitus", "thales", "cato", "cicero", "crito", "xenophon", "plutarch",
    "anaxagoras", "aristippus", "epicurus", "alexander",  # Alexander the Great in the Diogenes story
    "laertius", "iamblichus", "origen", "lucilius", "athens", "rome", "greece",
    "stoicism", "stoic", "stoics",
}

# Common sentence-lead words that capitalize without naming anyone.
_SENTENCE_LEADS = {
    "the", "a", "an", "if", "when", "what", "why", "how", "your", "you", "this",
    "that", "these", "those", "most", "every", "nobody", "everyone", "imagine",
    "suppose", "send", "comment", "agree", "stop", "start", "here", "there",
    "it", "its", "in", "on", "at", "and", "but", "or", "not", "no", "yes",
    "one", "two", "ancient", "modern", "real", "true",
}

_HONORIFICS = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|President|Senator|CEO|Coach|Judge|Prof|Professor|Sir|Elon|Kanye|Taylor|Drake|Trump|Biden|Musk|Bezos|Zuckerberg|Ronaldo|Messi|LeBron|Oprah|Kardashian)\.?\s+[A-Z][a-z]+",
    re.UNICODE,
)

# Capitalized bigram mid-sentence: "Firstname Lastname" pattern.
_NAME_BIGRAM = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b")


def _allowed(word: str) -> bool:
    return word.lower() in ALLOWED_FIGURES or word.lower() in _SENTENCE_LEADS


def mentions_named_person(text: str) -> bool:
    """True when the text appears to reference a named (modern) individual."""
    if not text:
        return False
    if _HONORIFICS.search(text):
        return True
    for m in _NAME_BIGRAM.finditer(text):
        first, second = m.group(1), m.group(2)
        if _allowed(first) or _allowed(second):
            continue
        return True
    return False
