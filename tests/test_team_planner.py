import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.planner import PlannerAgent, build_prompt, parse_response
from team.models import AnalyticsReport, ContentPlan


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


def _pool():
    return [
        {"row_number": 1, "quote": "Know thyself", "audience": "stuck"},
        {"row_number": 2, "quote": "Memento mori", "audience": "doomscroller"},
    ]


def _post(n):
    return {
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


def _plan_payload():
    return {"date": "2026-07-09", "posts": [_post(n) for n in range(1, 8)]}


def test_build_prompt_lists_pool_and_analytics():
    prefix = build_prompt(_analytics(), _pool(), "2026-07-09")
    assert "Know thyself" in prefix
    assert "Post more at 07:00" in prefix
    assert "2026-07-09" in prefix


def test_build_prompt_first_round_has_no_revision_marker():
    prefix = build_prompt(_analytics(), _pool(), "2026-07-09")
    assert "REVISION" not in prefix


def test_build_prompt_revision_round_contains_feedback():
    prefix = build_prompt(_analytics(), _pool(), "2026-07-09",
                          feedback="Post 3's hook is weak")
    assert "Post 3's hook is weak" in prefix
    assert "REVISION" in prefix


def test_parse_response_returns_content_plan_with_seven_posts():
    plan = parse_response(_plan_payload())
    assert isinstance(plan, ContentPlan)
    assert len(plan.posts) == 7
    assert plan.posts[0].post_number == 1


def test_run_first_round_uses_planner_role_and_no_feedback():
    client = _FakeClient(_plan_payload())
    agent = PlannerAgent(client)

    plan = agent.run(_analytics(), _pool())

    assert isinstance(plan, ContentPlan)
    assert len(plan.posts) == 7
    assert len(client.calls) == 1
    assert client.calls[0]["role"] == "planner"
    assert "REVISION" not in client.calls[0]["shared_prefix"]


def test_run_revision_round_includes_feedback_text_and_role():
    client = _FakeClient(_plan_payload())
    agent = PlannerAgent(client)

    plan = agent.run(_analytics(), _pool(), feedback="Post 3's hook is weak")

    assert client.calls[0]["role"] == "planner"
    assert "Post 3's hook is weak" in client.calls[0]["shared_prefix"]
    assert isinstance(plan, ContentPlan)


def test_run_uses_fixed_now_to_produce_tomorrows_date():
    client = _FakeClient(_plan_payload())
    agent = PlannerAgent(client)
    fixed_now = datetime(2026, 1, 15, 12, 0, 0)

    plan = agent.run(_analytics(), _pool(), now=fixed_now)

    assert plan.date == "2026-01-16"
