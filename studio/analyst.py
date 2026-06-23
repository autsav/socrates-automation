"""Data Analyst agent — mines SQLite metrics into a cached PerformanceBrief."""
import json
from datetime import datetime

from studio import settings
from studio.client import StudioError
from studio.types import PerformanceBrief, PERFORMANCE_BRIEF_SCHEMA
import data_store

_PREFIX = (
    "You are the Data Analyst for a stoic-philosophy Instagram account. "
    "You mine real post performance to tell the creative team what is working "
    "and what is dying. Account performance stats (last 90 days):\n{stats}"
)
_ROLE = (
    "Produce a PerformanceBrief. Identify which moods, audiences, slots, hooks, "
    "and topics over-perform the median (report lift), and list dying patterns to "
    "stop. Keep `headline` to 1-2 plain sentences. Output JSON only."
)


def build_prompt(stats):
    return _PREFIX.format(stats=json.dumps(stats, indent=2)), _ROLE


def parse_response(d):
    return PerformanceBrief.from_dict(d)


def build_brief(client, stats):
    prefix, role = build_prompt(stats)
    data = client.call("analyst", prefix, role,
                       "Generate the PerformanceBrief now.",
                       PERFORMANCE_BRIEF_SCHEMA)
    return parse_response(data)


def _load_cache():
    try:
        return PerformanceBrief.from_dict(
            json.loads(settings.PERF_BRIEF_PATH.read_text()))
    except (FileNotFoundError, ValueError, TypeError):
        return None


def _is_fresh(brief, now):
    try:
        gen = datetime.fromisoformat(brief.generated_at)
    except (ValueError, TypeError):
        return False
    return (now - gen).total_seconds() < settings.PERF_BRIEF_TTL_HOURS * 3600


def get_or_build_brief(client, *, now=None):
    now = now or datetime.utcnow()
    cached = _load_cache()
    if cached and _is_fresh(cached, now):
        return cached
    try:
        stats = data_store.aggregate_performance()
        brief = build_brief(client, stats)
        settings.PERF_BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings.PERF_BRIEF_PATH.write_text(json.dumps(brief.to_dict()))
        return brief
    except StudioError:
        if cached:
            return cached  # reuse last good brief
        raise
