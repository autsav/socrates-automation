import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.reviewer import ReviewerAgent, build_prompt, parse_response
from team.models import AnalyticsReport, ContentPlan, PostPlan


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def call(self, role, shared_prefix, role_system, user_content, schema):
        self.calls.append({
            "role": role,
            "shared_prefix": shared_prefix,
            "role_system": role_system,
            "user_content": user_content,
            "schema": schema,
        })
        return self.payload


def _analytics():
    return AnalyticsReport(
        date="2026-07-08",
        total_posts=10,
        avg_engagement_rate=0.05,
        top_performing_hooks=["hook_a"],
        top_performing_moods=["dark_philosophical"],
        best_posting_times=["07:00"],
        worst_performing_content=["hook_z"],
        recommendations=["Post more at 07:00"],
        follower_growth=100,
        save_rate=0.02,
    )


def _plan():
    post = PostPlan(
        post_number=1,
        posting_time="07:00",
        quote_id=3,
        audience="stuck",
        mood="dark_philosophical",
        format="reel",
        hook_strategy="contrarian",
        visual_style="cinematic",
        audio_strategy="lofi build",
        engagement_strategy="seed comment",
        controversy_question="Is discipline overrated?",
        cta="save this",
        hashtags=["#stoic"],
        estimated_viral_potential=7.5,
        rationale="ties to top_performing_hooks",
    )
    return ContentPlan(date="2026-07-09", posts=[post])


def _critique_payload():
    return {
        "score": 6.5,
        "approved": False,
        "critique": "needs work",
        "strengths": ["good hook"],
        "weaknesses": ["controversy question doesn't fit"],
        "improvement_suggestions": ["sharpen post 1's controversy_question"],
    }


def test_build_prompt_contains_plan_and_analytics_content():
    prefix = build_prompt(_plan(), _analytics())
    assert "Is discipline overrated?" in prefix  # from the plan
    assert "Post more at 07:00" in prefix  # from the analytics report


def test_parse_response_is_a_passthrough():
    payload = _critique_payload()
    assert parse_response(payload) == payload
    assert parse_response(payload) is payload


def test_run_returns_dict_unchanged_and_uses_reviewer_role():
    client = _FakeClient(_critique_payload())
    agent = ReviewerAgent(client)

    result = agent.run(_plan(), _analytics())

    assert result == _critique_payload()
    assert len(client.calls) == 1
    assert client.calls[0]["role"] == "reviewer"


def test_run_prompt_includes_plan_and_analytics_context():
    client = _FakeClient(_critique_payload())
    agent = ReviewerAgent(client)

    agent.run(_plan(), _analytics())

    prefix = client.calls[0]["shared_prefix"]
    assert "Is discipline overrated?" in prefix
    assert "quote_id" in prefix
    assert "Post more at 07:00" in prefix
