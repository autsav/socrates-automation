"""
Analytics package for Socrates Pipeline Phase 4.

Modules:
- cohort_analysis: Point 41 — cohort performance, time-slot ranking
- hook_tracker: Point 42 — hook template A/B testing with Thompson Sampling
- weekly_brief: Auto-generated performance reports
- save_rate: Point 44 — save rate as primary KPI
- competitor: Point 43 — competitor benchmarking
- sentiment: Point 45 — comment sentiment analysis
"""

from .save_rate import calculate_save_rate, get_save_rate_report, print_save_rate_report
from .sentiment import classify_comment, analyse_comments, sentiment_report
from .competitor import get_competitor_report, save_competitor_snapshot, generate_benchmark_prompt
from .metrics import fetch_post_metrics, ingest_all_pending

__all__ = [
    "calculate_save_rate", "get_save_rate_report", "print_save_rate_report",
    "classify_comment", "analyse_comments", "sentiment_report",
    "get_competitor_report", "save_competitor_snapshot", "generate_benchmark_prompt",
    "fetch_post_metrics", "ingest_all_pending",
]
