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
        if self.over_daily_ceiling():
            raise StudioError(f"{role} call blocked: daily spend ceiling reached")
        model = settings.ROLE_MODELS[role]
        effort = settings.ROLE_EFFORT[role]
        is_haiku = "haiku" in model
        kwargs = dict(
            model=model,
            max_tokens=8000,
            system=[
                {"type": "text", "text": shared_prefix,
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": role_system},
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        if not is_haiku:
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": effort,
                                        "format": {"type": "json_schema", "schema": schema}}
        else:
            # Haiku doesn't support thinking or effort; use simple JSON mode
            from anthropic.types import TextBlock
            kwargs["system"] = [
                {"type": "text", "text": shared_prefix + "\n\n" + role_system +
                 "\n\nIMPORTANT: Respond with ONLY valid JSON matching this schema. No markdown, no commentary:\n" +
                 json.dumps(schema, indent=2)},
            ]
        resp = self._sdk.messages.create(**kwargs)
        self._record_usage(model, resp.usage)
        if getattr(resp, "stop_reason", None) == "refusal":
            raise StudioError(f"{role} refused")
        # Extract text — handle thinking blocks (skip them) and empty responses
        text = ""
        for block in resp.content:
            if hasattr(block, "text") and block.type == "text":
                text = block.text
                break
        if not text:
            # Fallback: try to get text from any block that has text attr
            text = getattr(resp, "output_text", "") or ""
        if not text:
            raise StudioError(f"{role} produced empty response (stop={resp.stop_reason}, content_types={[b.type for b in resp.content]})")
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            return json.loads(text)
        except (ValueError, TypeError) as e:
            raise StudioError(f"{role} produced non-JSON: {e}\nText was: {text[:200]}") from e

    # ── spend tracking ────────────────────────────────────────────────────
    def _record_usage(self, model, usage):
        cin, cout = _PRICING.get(model, (5.0, 25.0))
        # Include cache token fields so ceiling math matches the invoice.
        # Cache reads are billed at full input rate; cache writes at 1.25x.
        input_tokens = getattr(usage, "input_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cost = (input_tokens * cin
                + cache_read * cin
                + cache_write * cin * 1.25
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
