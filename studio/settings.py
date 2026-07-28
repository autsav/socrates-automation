"""Studio configuration constants (non-secret). Models / effort / budget dials."""
import os
from pathlib import Path

from src.core.excel_reader import AUDIENCE_TO_MOOD

AUDIENCES = list(AUDIENCE_TO_MOOD.keys())

ROLE_MODELS = {
    "analyst":    "claude-sonnet-4-6",
    "strategist": "claude-sonnet-4-6",
    "copywriter": "claude-opus-4-8",
    "director":   "claude-sonnet-4-6",  # legacy — retired (spec 1.4)
    "planner":               "claude-sonnet-4-6",
    "reviewer":               "claude-sonnet-4-6",
    "content_writer":         "claude-opus-4-8",
    "visual_designer":        "claude-sonnet-4-6",
    "audio_engineer":         "claude-sonnet-4-6",
    "video_editor":           "claude-sonnet-4-6",
    "engagement_strategist":  "claude-sonnet-4-6",
    "analytics_analyst":      "claude-haiku-4-5",
    "music_director":         "claude-sonnet-4-6",
    "trend_scout":            "claude-sonnet-4-6",
    "prompt_critic":          "claude-sonnet-4-6",
    "social_strategist":      os.getenv("STRATEGIST_MODEL", "claude-opus-4-7"),
    "story_writer":           "claude-opus-4-8",
    "hook_specialist":        "claude-sonnet-4-6",
}
ROLE_EFFORT = {
    "analyst":    "medium",
    "strategist": "medium",
    "copywriter": "high",
    "director":   "medium",  # legacy — retired (spec 1.4)
    "planner":               "medium",
    "reviewer":               "medium",
    "content_writer":         "high",
    "visual_designer":        "medium",
    "audio_engineer":         "medium",
    "video_editor":           "medium",
    "engagement_strategist":  "medium",
    "analytics_analyst":      "low",
    "music_director":         "medium",
    "trend_scout":            "medium",
    "prompt_critic":          "medium",
    "social_strategist":      "high",
    "story_writer":           "high",
    "hook_specialist":        "medium",
}
N_CONCEPTS = 4
DAILY_SPEND_CEILING_USD = 5.0  # raised for 2-draft + critique passes (spec 1.5)

_DATA = Path(__file__).resolve().parent.parent / "data"
PERF_BRIEF_PATH = _DATA / "perf_brief.json"
PERF_BRIEF_TTL_HOURS = 24
SPEND_LOG_PATH = _DATA / "studio_spend.json"

STRATEGY_AUDIENCE = os.getenv("STRATEGY_AUDIENCE",
                              "procrastinators and doomscrollers who feel stuck")
