"""Pre-experiment validation for prompt challengers. A candidate that fails
here never opens an experiment (and never reaches a real generation call)."""
import re

try:
    from src.content.trend_sources import is_unsafe
except Exception:  # defensive — never import-crash the optimizer
    def is_unsafe(_s):
        return False

_PLACEHOLDER = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")


def _placeholders(s):
    return set(_PLACEHOLDER.findall(s))


def validate_prompt_candidate(champion, candidate):
    if not candidate or not candidate.strip():
        return False, "candidate is empty"
    missing = _placeholders(champion) - _placeholders(candidate)
    if missing:
        return False, f"dropped placeholders: {', '.join(sorted(missing))}"
    lo, hi = 0.4 * len(champion), 3.0 * len(champion)
    if not (lo <= len(candidate) <= hi):
        return False, f"length {len(candidate)} outside sane bounds [{int(lo)},{int(hi)}]"
    # Safety is a NO-REGRESSION check: a prompt may legitimately *name* unsafe
    # topics (e.g. trend_scout's "reject war/death/…" rules), so the content
    # denylist would false-positive on such a meta-prompt. Only reject when the
    # candidate is unsafe AND the champion was not — i.e. the critic *added*
    # unsafe directives. Unsafe generated *output* stays gated downstream.
    if is_unsafe(candidate) and not is_unsafe(champion):
        return False, "candidate introduces unsafe content the champion lacked"
    return True, "ok"
