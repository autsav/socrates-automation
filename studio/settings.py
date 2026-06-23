"""Studio configuration constants (non-secret). Models / effort / budget dials."""
from pathlib import Path

from excel_reader import AUDIENCE_TO_MOOD

AUDIENCES = list(AUDIENCE_TO_MOOD.keys())

ROLE_MODELS = {
    "analyst":    "claude-sonnet-4-6",
    "strategist": "claude-sonnet-4-6",
    "copywriter": "claude-opus-4-8",
    "director":   "claude-opus-4-8",
}
ROLE_EFFORT = {
    "analyst":    "medium",
    "strategist": "medium",
    "copywriter": "high",
    "director":   "high",
}
N_CONCEPTS = 4
DAILY_SPEND_CEILING_USD = 2.0

_DATA = Path(__file__).resolve().parent.parent / "data"
PERF_BRIEF_PATH = _DATA / "perf_brief.json"
PERF_BRIEF_TTL_HOURS = 24
SPEND_LOG_PATH = _DATA / "studio_spend.json"
