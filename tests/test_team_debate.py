import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.debate import run_debate
from team.models import AnalyticsReport, ContentPlan, DebateResult, PostPlan


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
    return PostPlan(
        post_number=n,
        posting_time="07:00",
        quote_id=n,
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


def _plan(date="2026-07-09"):
    return ContentPlan(date=date, posts=[_post(n) for n in range(1, 8)])


class _FakePlanner:
    """Returns plans (or a single plan) from a queue, records calls."""

    def __init__(self, plans):
        self._plans = list(plans)
        self.calls = []

    def run(self, analytics_report, quotes_pool, *, feedback=None, now=None):
        self.calls.append({
            "analytics_report": analytics_report,
            "quotes_pool": quotes_pool,
            "feedback": feedback,
            "now": now,
        })
        if len(self._plans) > 1:
            return self._plans.pop(0)
        return self._plans[0]


class _FakeReviewer:
    """Returns review dicts from a queue, records calls."""

    def __init__(self, reviews):
        self._reviews = list(reviews)
        self.calls = []

    def run(self, plan, analytics_report):
        self.calls.append({"plan": plan, "analytics_report": analytics_report})
        if len(self._reviews) > 1:
            return self._reviews.pop(0)
        return self._reviews[0]


def _review(score, approved=None, critique="meh", weaknesses=None, suggestions=None):
    return {
        "score": score,
        "approved": approved if approved is not None else (score >= 8.0),
        "critique": critique,
        "strengths": ["good hook"],
        "weaknesses": weaknesses or ["weak cta"],
        "improvement_suggestions": suggestions or ["sharpen cta"],
    }


def test_approved_round_1():
    plan = _plan()
    planner = _FakePlanner([plan])
    reviewer = _FakeReviewer([_review(9.0)])

    final_plan, history = run_debate(planner, reviewer, _analytics(), _pool())

    assert len(history) == 1
    assert history[0].approved is True
    assert history[0].round_number == 1
    assert history[0].reviewer_score == 9.0
    assert final_plan is plan
    assert len(planner.calls) == 1
    assert planner.calls[0]["feedback"] is None


def test_not_approved_round_1_approved_round_2():
    plan1 = _plan()
    plan2 = _plan()
    planner = _FakePlanner([plan1, plan2])
    review1 = _review(6.0, critique="Too generic hooks.", weaknesses=["hook is flat"],
                       suggestions=["make hook contrarian"])
    review2 = _review(8.5)
    reviewer = _FakeReviewer([review1, review2])

    final_plan, history = run_debate(planner, reviewer, _analytics(), _pool())

    assert len(history) == 2
    assert history[0].approved is False
    assert history[1].approved is True
    assert final_plan is plan2

    assert len(planner.calls) == 2
    assert planner.calls[0]["feedback"] is None
    second_feedback = planner.calls[1]["feedback"]
    assert second_feedback is not None
    assert "Too generic hooks." in second_feedback
    assert "hook is flat" in second_feedback
    assert "make hook contrarian" in second_feedback


def test_never_approved_stops_after_max_rounds():
    plans = [_plan(), _plan(), _plan()]
    planner = _FakePlanner(plans)
    reviewer = _FakeReviewer([_review(5.0), _review(5.0), _review(5.0)])

    final_plan, history = run_debate(planner, reviewer, _analytics(), _pool())

    assert len(history) == 3
    assert history[-1].approved is False
    assert final_plan is plans[2]
    assert len(planner.calls) == 3
    assert len(reviewer.calls) == 3


def test_computed_approval_overrides_reviewer_self_reported_flag():
    plan = _plan()
    planner = _FakePlanner([plan])
    # Reviewer contradicts itself: high score but says not approved.
    reviewer = _FakeReviewer([_review(9.0, approved=False)])

    final_plan, history = run_debate(planner, reviewer, _analytics(), _pool())

    assert len(history) == 1
    assert history[0].approved is True


def test_custom_max_rounds_stops_early():
    plan = _plan()
    planner = _FakePlanner([plan])
    reviewer = _FakeReviewer([_review(5.0)])

    final_plan, history = run_debate(planner, reviewer, _analytics(), _pool(), max_rounds=1)

    assert len(history) == 1
    assert history[0].approved is False
    assert final_plan is plan


def test_custom_approval_threshold_approves_lower_score():
    plan = _plan()
    planner = _FakePlanner([plan])
    reviewer = _FakeReviewer([_review(6.0, approved=False)])

    final_plan, history = run_debate(
        planner, reviewer, _analytics(), _pool(), approval_threshold=5.0
    )

    assert len(history) == 1
    assert history[0].approved is True


def test_now_passed_through_to_every_planner_call():
    plan1 = _plan()
    plan2 = _plan()
    planner = _FakePlanner([plan1, plan2])
    reviewer = _FakeReviewer([_review(6.0), _review(9.0)])
    fixed_now = datetime(2026, 7, 9, 12, 0, 0)

    run_debate(planner, reviewer, _analytics(), _pool(), now=fixed_now)

    assert all(call["now"] == fixed_now for call in planner.calls)


def test_history_entries_hold_expected_fields():
    plan = _plan()
    planner = _FakePlanner([plan])
    reviewer = _FakeReviewer([_review(9.0)])

    _, history = run_debate(planner, reviewer, _analytics(), _pool())

    entry = history[0]
    assert isinstance(entry, DebateResult)
    assert entry.planner_output == __import__("json").dumps(plan.to_dict())
    assert entry.final_plan is plan
