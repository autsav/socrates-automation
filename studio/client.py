"""Thin anthropic-SDK wrapper for studio agents: structured output, prompt
caching of the shared prefix, refusal detection, and a daily spend ceiling."""
import json
from datetime import date

from studio import settings


class StudioError(Exception):
    """Raised on refusal, malformed output, or any unrecoverable agent failure."""


# USD per 1M tokens (input, output)
_PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


class StudioClient:
    def __init__(self, api_key, *, sdk=None):
        if sdk is None:
            import anthropic
            sdk = anthropic.Anthropic(api_key=api_key, max_retries=3)
        self._sdk = sdk

    def call(self, role, shared_prefix, role_system, user_content, schema):
        model = settings.ROLE_MODELS[role]
        effort = settings.ROLE_EFFORT[role]
        resp = self._sdk.messages.create(
            model=model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": effort,
                           "format": {"type": "json_schema", "schema": schema}},
            system=[
                {"type": "text", "text": shared_prefix,
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": role_system},
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        self._record_usage(model, resp.usage)
        if getattr(resp, "stop_reason", None) == "refusal":
            raise StudioError(f"{role} refused")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except (ValueError, TypeError) as e:
            raise StudioError(f"{role} produced non-JSON: {e}") from e

    # ── spend tracking ────────────────────────────────────────────────────
    def _record_usage(self, model, usage):
        cin, cout = _PRICING.get(model, (5.0, 25.0))
        cost = (getattr(usage, "input_tokens", 0) * cin
                + getattr(usage, "output_tokens", 0) * cout) / 1_000_000
        log = self._load_spend()
        today = date.today().isoformat()
        log[today] = round(log.get(today, 0.0) + cost, 6)
        settings.SPEND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings.SPEND_LOG_PATH.write_text(json.dumps(log))

    def _load_spend(self):
        try:
            return json.loads(settings.SPEND_LOG_PATH.read_text())
        except (FileNotFoundError, ValueError):
            return {}

    def over_daily_ceiling(self):
        spent = self._load_spend().get(date.today().isoformat(), 0.0)
        return spent >= settings.DAILY_SPEND_CEILING_USD
