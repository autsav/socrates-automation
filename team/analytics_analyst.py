"""Analytics Analyst agent — turns raw performance metrics into an AnalyticsReport."""
from __future__ import annotations

import json
from datetime import datetime

from studio.client import StudioClient
from team.models import AnalyticsReport, ANALYTICS_REPORT_SCHEMA
from team.prompt_loader import load_prompt
from src.core import data_store
from src.analytics import hook_tracker

_PREFIX = (
    "Account performance stats for the analytics report (as of {date}):\n{stats}"
)


class AnalyticsAnalystAgent:
    def __init__(self, client: StudioClient):
        self.client = client
        self.system_prompt = load_prompt("analytics_analyst")

    def run(self, window_days: int = 90, now: datetime | None = None) -> AnalyticsReport:
        now = now or datetime.utcnow()
        hook_window = min(window_days, 30)

        performance = data_store.aggregate_performance(window_days)
        hook_rankings = hook_tracker.get_all_hook_rankings(window_days=hook_window)
        hook_leaderboard = hook_tracker.get_hook_leaderboard(window_days=hook_window)

        date_str = now.date().isoformat()
        stats = {
            "date": date_str,
            "window_days": window_days,
            "performance": performance,
            "hook_rankings": hook_rankings,
            "hook_leaderboard": hook_leaderboard,
        }
        shared_prefix = _PREFIX.format(date=date_str, stats=json.dumps(stats, indent=2))

        data = self.client.call(
            "analytics_analyst",
            shared_prefix,
            self.system_prompt,
            "Generate the AnalyticsReport now.",
            ANALYTICS_REPORT_SCHEMA,
        )
        return AnalyticsReport.from_dict(data)
