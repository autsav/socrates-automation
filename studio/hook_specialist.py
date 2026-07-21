"""8-angle hook variant pass (spec 4). Hooks decide retention; the writer's
single hook attempt becomes 8 psychological angles with a coded judge."""
import re

from studio.types import _obj
from studio.rubric import score_hook

HOOK_ANGLES = ("fear", "curiosity", "status", "absurdity", "loss",
               "time-urgency", "secret", "challenge")

_HOOKS_SCHEMA = _obj({"hooks": {"type": "array", "items": {"type": "string"}}},
                     ["hooks"])
_VIEWER = {"you", "your", "you're", "you've", "you'll", "you'd", "yourself"}
_RESOLUTION = ("that's why", "the answer", "here's how", "the lesson")

_PREFIX = (
    "You write scroll-stopping first lines for 60-second Stoic story reels. "
    "A hook is ONE statement, <=15 words, addressed to the viewer (you/your), "
    "opening a loop it never resolves.")


def generate_hooks(client, story: dict, n: int = 8) -> list[str]:
    """One call, one hook per angle. [] on any failure (never raises)."""
    try:
        role = (
            "The finished story:\n"
            f"{story.get('beat_reframe', '')}\n\n"
            f"Current hook: {story.get('beat_hook', '')}\n\n"
            "Write EXACTLY one hook per angle, in this order: "
            + ", ".join(HOOK_ANGLES[:n]) + ". Each <=15 words, a STATEMENT, "
            "second person, planting a mystery the story pays off. Output JSON.")
        d = client.call("hook_specialist", _PREFIX, role,
                        "Write the hooks now.", _HOOKS_SCHEMA)
        hooks = [h for h in (d or {}).get("hooks", []) if isinstance(h, str)]
        return hooks[:n]
    except Exception:  # noqa: BLE001 - the story's own hook is the fallback
        return []


def _valid(hook: str) -> bool:
    hl = hook.lower()
    toks = set(re.findall(r"[a-z']+", hl))
    if not (toks & _VIEWER):
        return False
    if len(hook.split()) > 15 or hook.rstrip().endswith("?"):
        return False
    return not any(p in hl for p in _RESOLUTION)


def pick_hook(candidates: list[str], fallback: str) -> str:
    """Best valid candidate by score_hook, else the fallback."""
    try:
        valid = [c for c in candidates if c and _valid(c)]
        if not valid:
            return fallback
        return max(valid, key=score_hook)
    except Exception:  # noqa: BLE001
        return fallback
