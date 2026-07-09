"""Pydantic validation schemas for team/ agent I/O.

The JSON schemas in team/models.py (used as Anthropic structured-output
constraints) have no enum constraints on closed-vocabulary fields (audience,
mood, format) and no minItems/maxItems on the "one entry per day of a 7-day
plan" arrays (ANALYSIS.md §B) — a structured-output-conformant response can
still pick a nonsense audience/mood/format string or omit/duplicate posts.

These models re-validate the already-parsed response dict before it's handed
to a team/models.py dataclass's from_dict(), so a violation surfaces as a
pydantic.ValidationError — caught and retried by team/base_agent.py's
BaseAgent.call_with_retry() — instead of silently shipping a plan with an
invalid mood or a gap where post 4 should be.

hook_strategy is deliberately NOT enum-constrained: the planner prompt
(team/prompts/planner.md) describes it as free-form descriptive text picked
from named viral patterns, not a fixed set of literal tokens the model must
reproduce verbatim.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.core.excel_reader import VALID_MOODS
from studio.settings import AUDIENCES

_Audience = Literal[tuple(AUDIENCES)]
_Mood = Literal[tuple(VALID_MOODS)]
_Format = Literal["reel", "carousel", "single"]

_WEEK_SIZE = 7


def _validate_post_numbers_are_one_through_seven(items: list) -> list:
    """Every per-post spec list must have exactly one entry per plan day,
    numbered 1..7 with no gaps or duplicates (ANALYSIS.md §B)."""
    numbers = sorted(item.post_number for item in items)
    if numbers != list(range(1, _WEEK_SIZE + 1)):
        raise ValueError(
            f"post_number values must be exactly 1..{_WEEK_SIZE} with no "
            f"gaps/duplicates, got {numbers}"
        )
    return items


class PostPlanSchema(BaseModel):
    post_number: int = Field(ge=1, le=_WEEK_SIZE)
    posting_time: str
    quote_id: int
    audience: _Audience
    mood: _Mood
    format: _Format
    hook_strategy: str = Field(min_length=1)
    visual_style: str
    audio_strategy: str
    engagement_strategy: str
    controversy_question: str
    cta: str
    hashtags: list[str]
    estimated_viral_potential: float = Field(ge=0, le=10)
    rationale: str


class ContentPlanSchema(BaseModel):
    date: str
    posts: list[PostPlanSchema] = Field(min_length=_WEEK_SIZE, max_length=_WEEK_SIZE)

    @field_validator("posts")
    @classmethod
    def _posts_numbered_one_through_seven(cls, v):
        return _validate_post_numbers_are_one_through_seven(v)


class ReviewerOutputSchema(BaseModel):
    score: float = Field(ge=0, le=10)
    approved: bool
    critique: str
    strengths: list[str]
    weaknesses: list[str]
    improvement_suggestions: list[str]


class CopySpecSchema(BaseModel):
    post_number: int = Field(ge=1, le=_WEEK_SIZE)
    hook: str
    caption: str
    cta: str
    controversy_question: str
    hashtags: list[str]
    carousel_slides: list[str]
    story_teaser: str


class CopySpecsSchema(BaseModel):
    items: list[CopySpecSchema] = Field(min_length=_WEEK_SIZE, max_length=_WEEK_SIZE)

    @field_validator("items")
    @classmethod
    def _items_numbered_one_through_seven(cls, v):
        return _validate_post_numbers_are_one_through_seven(v)


class VisualSpecSchema(BaseModel):
    post_number: int = Field(ge=1, le=_WEEK_SIZE)
    flux_prompt: str
    composition_params: dict
    wallpaper_design: dict
    carousel_design: list[dict]
    color_palette: dict
    font_choice: dict


class VisualSpecsSchema(BaseModel):
    items: list[VisualSpecSchema] = Field(min_length=_WEEK_SIZE, max_length=_WEEK_SIZE)

    @field_validator("items")
    @classmethod
    def _items_numbered_one_through_seven(cls, v):
        return _validate_post_numbers_are_one_through_seven(v)


class AudioSpecSchema(BaseModel):
    post_number: int = Field(ge=1, le=_WEEK_SIZE)
    music_track: str
    voiceover_text: str
    voiceover_emotion: str
    beat_markers: list[float]
    mix_levels: dict
    jingle: bool


class AudioSpecsSchema(BaseModel):
    items: list[AudioSpecSchema] = Field(min_length=_WEEK_SIZE, max_length=_WEEK_SIZE)

    @field_validator("items")
    @classmethod
    def _items_numbered_one_through_seven(cls, v):
        return _validate_post_numbers_are_one_through_seven(v)


class VideoSpecSchema(BaseModel):
    post_number: int = Field(ge=1, le=_WEEK_SIZE)
    scenes: list[dict]
    total_duration: float = Field(ge=0)
    transitions: list[str]
    motion_effects: list[str]
    text_overlays: list[dict]
    aspect_ratio: str


class VideoSpecsSchema(BaseModel):
    items: list[VideoSpecSchema] = Field(min_length=_WEEK_SIZE, max_length=_WEEK_SIZE)

    @field_validator("items")
    @classmethod
    def _items_numbered_one_through_seven(cls, v):
        return _validate_post_numbers_are_one_through_seven(v)


class EngagementSpecSchema(BaseModel):
    post_number: int = Field(ge=1, le=_WEEK_SIZE)
    seed_comments: list[str]
    reply_templates: list[str]
    dm_trigger: str
    save_bait_frame: str
    story_teaser: str
    highlight_category: str


class EngagementSpecsSchema(BaseModel):
    items: list[EngagementSpecSchema] = Field(min_length=_WEEK_SIZE, max_length=_WEEK_SIZE)

    @field_validator("items")
    @classmethod
    def _items_numbered_one_through_seven(cls, v):
        return _validate_post_numbers_are_one_through_seven(v)


class AnalyticsReportSchema(BaseModel):
    date: str
    total_posts: int = Field(ge=0)
    avg_engagement_rate: float
    top_performing_hooks: list[str]
    top_performing_moods: list[str]
    best_posting_times: list[str]
    worst_performing_content: list[str]
    recommendations: list[str]
    follower_growth: int
    save_rate: float


class VideoQualityScoreSchema(BaseModel):
    post_number: int = Field(ge=1, le=_WEEK_SIZE)
    visual_appeal: int = Field(ge=1, le=10)
    text_readability: int = Field(ge=1, le=10)
    content_relevance: int = Field(ge=1, le=10)
    production_quality: int = Field(ge=1, le=10)
    overall_score: float = Field(ge=0, le=10)
    is_acceptable: bool
    feedback: str
    suggestions: str


class VideoQualityScoresSchema(BaseModel):
    items: list[VideoQualityScoreSchema] = Field(min_length=_WEEK_SIZE, max_length=_WEEK_SIZE)

    @field_validator("items")
    @classmethod
    def _items_numbered_one_through_seven(cls, v):
        return _validate_post_numbers_are_one_through_seven(v)
