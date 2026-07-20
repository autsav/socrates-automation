"""Per-word animation classes for the Remotion animation director (spec 2).
Pure and boring on purpose: classification lives in Python so the render
layer stays dumb and deterministic."""
import re

_NUM_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight",
              "nine", "ten", "hundred", "thousand", "million"}
_NEG = {"no", "not", "never", "nobody", "nothing", "stop", "wrong", "dead",
        "can't", "won't", "don't", "refuse", "refused", "quit"}
_POWER = {"fear", "afraid", "broke", "alone", "rich", "poor", "die", "death",
          "truth", "lie", "pain", "lost", "win", "fail", "weak", "strong",
          "enemy", "storm", "power", "control", "trapped", "free", "hunger",
          "silence", "empty", "brutal", "savage", "terrified", "coward"}
_HAS_DIGIT = re.compile(r"\d")


def _bare(w) -> str:
    return re.sub(r"[^\w']", "", str(w or "")).lower()


def classify_words(words: list) -> list:
    """Add a `cls` to every word dict. Priority: num > neg > power > end >
    stress > plain. Stress = longest bare word of each sentence. Never raises."""
    try:
        out = []
        # Sentence segmentation over word indices (terminal punctuation).
        sentence, sentences = [], []
        for i, wd in enumerate(words):
            sentence.append(i)
            if str(wd.get("w") or "").rstrip().endswith((".", "!", "?")):
                sentences.append(sentence)
                sentence = []
        if sentence:
            sentences.append(sentence)
        stress_idx = set()
        for sent in sentences:
            if sent:
                # Only consider words with non-empty bare forms for stress
                valid_sent = [i for i in sent if len(_bare(words[i].get("w")))]
                if valid_sent:
                    stress_idx.add(max(valid_sent, key=lambda i: len(_bare(words[i].get("w")))))
        for i, wd in enumerate(words):
            raw = str(wd.get("w") or "")
            bare = _bare(raw)
            if _HAS_DIGIT.search(raw) or bare in _NUM_WORDS:
                cls = "num"
            elif bare in _NEG:
                cls = "neg"
            elif bare in _POWER:
                cls = "power"
            elif raw.rstrip().endswith((".", "!", "?")):
                cls = "end"
            elif i in stress_idx:
                cls = "stress"
            else:
                cls = "plain"
            out.append({**wd, "cls": cls})
        return out
    except Exception:  # noqa: BLE001 - garbage in -> all plain
        return [{**(w if isinstance(w, dict) else {}), "cls": "plain"}
                for w in (words or [])]
