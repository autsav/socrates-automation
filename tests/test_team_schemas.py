import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from pydantic import ValidationError

from team.base_agent import AgentError
from team.planner import PlannerAgent
from team.schemas import ContentPlanSchema, CopySpecsSchema


def _valid_post(n, **overrides):
    post = {
        "post_number": n,
        "posting_time": "07:00",
        "quote_id": n,
        "audience": "stuck",
        "mood": "dark_philosophical",
        "format": "reel",
        "hook_strategy": "contrarian",
        "visual_style": "cinematic",
        "audio_strategy": "lofi build",
        "engagement_strategy": "seed comment",
        "controversy_question": "Is discipline overrated?",
        "cta": "save this",
        "hashtags": ["#stoic"],
        "estimated_viral_potential": 7.5,
        "rationale": "ties to top_performing_hooks",
    }
    post.update(overrides)
    return post


def _valid_plan(**post_overrides):
    return {"date": "2026-07-09",
            "posts": [_valid_post(n, **post_overrides) for n in range(1, 8)]}


def test_valid_plan_passes():
    ContentPlanSchema.model_validate(_valid_plan())


def test_rejects_invalid_audience():
    plan = _valid_plan()
    plan["posts"][0]["audience"] = "not-a-real-audience"
    with pytest.raises(ValidationError):
        ContentPlanSchema.model_validate(plan)


def test_rejects_invalid_mood():
    plan = _valid_plan()
    plan["posts"][0]["mood"] = "not-a-real-mood"
    with pytest.raises(ValidationError):
        ContentPlanSchema.model_validate(plan)


def test_rejects_invalid_format():
    plan = _valid_plan()
    plan["posts"][0]["format"] = "story"
    with pytest.raises(ValidationError):
        ContentPlanSchema.model_validate(plan)


def test_accepts_free_form_hook_strategy():
    """hook_strategy is deliberately NOT enum-constrained — it's descriptive
    text per team/prompts/planner.md, not a fixed token set."""
    plan = _valid_plan(hook_strategy="an open loop about mortality")
    ContentPlanSchema.model_validate(plan)


def test_rejects_fewer_than_seven_posts():
    plan = _valid_plan()
    plan["posts"] = plan["posts"][:6]
    with pytest.raises(ValidationError):
        ContentPlanSchema.model_validate(plan)


def test_rejects_more_than_seven_posts():
    plan = _valid_plan()
    plan["posts"].append(_valid_post(8))
    with pytest.raises(ValidationError):
        ContentPlanSchema.model_validate(plan)


def test_rejects_duplicate_post_numbers_even_at_seven_items():
    plan = _valid_plan()
    plan["posts"][6]["post_number"] = 1  # duplicate of post 1, post 7 missing
    with pytest.raises(ValidationError):
        ContentPlanSchema.model_validate(plan)


def test_copy_specs_schema_rejects_gap_in_post_numbers():
    items = [{"post_number": n, "hook": "h", "caption": "c", "cta": "cta",
              "controversy_question": "q?", "hashtags": [], "carousel_slides": [],
              "story_teaser": "t"} for n in range(1, 8)]
    items[3]["post_number"] = 3  # duplicate post 3, no post 4
    with pytest.raises(ValidationError):
        CopySpecsSchema.model_validate({"items": items})


class _FakeClient:
    """Always returns a plan with an invalid audience — simulates a
    structured-output-conformant but semantically invalid LLM response."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def call(self, role, shared_prefix, role_system, user_content, schema):
        self.calls += 1
        return self.payload


def test_planner_agent_raises_agent_error_on_invalid_audience(monkeypatch):
    monkeypatch.setattr("team.base_agent.time.sleep", lambda s: None)
    from team.models import AnalyticsReport

    bad_plan = _valid_plan()
    bad_plan["posts"][0]["audience"] = "not-a-real-audience"
    client = _FakeClient(bad_plan)
    agent = PlannerAgent(client)
    agent.max_retries = 2

    analytics = AnalyticsReport(
        date="2026-07-08", total_posts=10, avg_engagement_rate=0.05,
        top_performing_hooks=["hook_a"], top_performing_moods=["dark_philosophical"],
        best_posting_times=["07:00"], worst_performing_content=["hook_z"],
        recommendations=["Post more"], follower_growth=100, save_rate=0.02,
    )

    with pytest.raises(AgentError):
        agent.run(analytics, [{"row_number": 1, "quote": "q", "audience": "stuck"}])

    assert client.calls == 2  # retried, never silently accepted the bad plan
