"""Base class for team/ agents — retries the LLM call + response parse with
exponential backoff, wrapping a malformed/missing-key response (or any SDK
failure) in a single domain-specific AgentError instead of letting a bare
KeyError/TypeError escape from inside a dataclass constructor deep in the
call stack (ANALYSIS.md §F)."""
from __future__ import annotations

import logging
import time


class AgentError(RuntimeError):
    """Raised when an agent exhausts its retries. Wraps the last underlying
    exception (KeyError, TypeError, StudioError, a raw SDK error, ...) with
    role/attempt context; the original exception is chained via __cause__."""


class BaseAgent:
    max_retries: int = 3
    retry_delay: float = 1.5
    is_critical: bool = True

    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger(f"team.agent.{self.__class__.__name__}")

    def call_with_retry(self, role, shared_prefix, role_system, user_content,
                        schema, parse_fn):
        """Call self.client.call(...), parse the result via parse_fn(data),
        retrying with exponential backoff on any failure. Raises AgentError
        after max_retries attempts."""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                data = self.client.call(role, shared_prefix, role_system,
                                        user_content, schema)
                return parse_fn(data)
            except Exception as exc:
                last_exc = exc
                self.logger.warning(
                    "%s attempt %d/%d failed: %s: %s",
                    role, attempt, self.max_retries, type(exc).__name__, exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (2 ** (attempt - 1)))
        raise AgentError(
            f"{role} failed after {self.max_retries} attempts: "
            f"{type(last_exc).__name__}: {last_exc}"
        ) from last_exc
