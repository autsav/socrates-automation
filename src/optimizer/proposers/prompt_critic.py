"""Critic agent: rewrite an agent's system prompt to be more viral, given the
champion text + performance context. Returns a challenger candidate + rationale
+ predicted improvement. Best-effort — never raises."""
import logging

log = logging.getLogger(__name__)

_PREFIX = (
    "You are a Prompt Optimization Critic for a viral Stoic-philosophy Instagram "
    "account. You improve the SYSTEM PROMPTS that instruct the account's content "
    "agents, to drive saves/comments/shares."
)
_ROLE = (
    "Here is the CURRENT champion prompt for the agent '{key}':\n"
    "<<<\n{champion}\n>>>\n\n"
    "Performance context (what is winning/dying):\n{perf}\n\n"
    "Rewrite the prompt to more reliably produce scroll-stopping, save-worthy "
    "output. HARD RULES: keep every {{placeholder}} exactly as-is; keep it a "
    "system prompt (instructions, not content); do not add unsafe directives; "
    "stay concise. Output JSON with: candidate (the full rewritten prompt), "
    "rationale (one sentence on what you changed and why), predicted_delta "
    "(your estimate of fractional engagement-rate improvement, e.g. 0.1 = +10%)."
)

CRITIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidate": {"type": "string"},
        "rationale": {"type": "string"},
        "predicted_delta": {"type": "number"},
    },
    "required": ["candidate", "rationale", "predicted_delta"],
}


def propose(client, key, champion_text, perf_context):
    try:
        if client.over_daily_ceiling():
            log.info("[optimizer] critic skipped — over daily ceiling")
            return None
        role = _ROLE.format(key=key, champion=champion_text, perf=perf_context)
        d = client.call("prompt_critic", _PREFIX, role,
                        "Rewrite the prompt now.", CRITIC_SCHEMA)
        if not d or "candidate" not in d:
            return None
        return {
            "candidate": d["candidate"],
            "rationale": d.get("rationale", ""),
            "predicted_delta": float(d.get("predicted_delta", 0.0) or 0.0),
        }
    except Exception as e:
        log.warning(f"[optimizer] critic.propose failed ({e})")
        return None
