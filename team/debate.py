"""Planner <-> reviewer debate loop.

Drives up to `max_rounds` rounds of planner.run / reviewer.run. The approval
decision is computed here (score >= approval_threshold) rather than trusted
from the reviewer's own self-reported "approved" flag — this is the one
authoritative gate in the system. Deterministic: given the same mocked
planner/reviewer behavior, the same round count and approved outcome always
result.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

from team.models import ContentPlan, DebateResult
from team.planner import PlannerAgent
from team.reviewer import ReviewerAgent


def _build_feedback(review: dict) -> str:
    lines = [review["critique"], "", "Specific weaknesses:"]
    lines += [f"- {w}" for w in review["weaknesses"]]
    lines += ["", "Required improvements:"]
    lines += [f"- {s}" for s in review["improvement_suggestions"]]
    return "\n".join(lines)


def run_debate(
    planner: PlannerAgent,
    reviewer: ReviewerAgent,
    analytics_report,
    quotes_pool: list[dict],
    *,
    max_rounds: int = 3,
    approval_threshold: float = 8.0,
    now: datetime | None = None,
    on_round: Callable[[int, str, str, float, bool], None] | None = None,
) -> tuple[ContentPlan, list[DebateResult]]:
    history: list[DebateResult] = []
    feedback: str | None = None
    round_number = 0

    while True:
        round_number += 1
        plan = planner.run(analytics_report, quotes_pool, feedback=feedback, now=now)
        review = reviewer.run(plan, analytics_report)
        approved = review["score"] >= approval_threshold
        planner_output = json.dumps(plan.to_dict())
        reviewer_output = json.dumps(review)

        history.append(DebateResult(
            round_number=round_number,
            planner_output=planner_output,
            reviewer_output=reviewer_output,
            reviewer_score=review["score"],
            approved=approved,
            final_plan=plan,
        ))

        if on_round is not None:
            on_round(round_number, planner_output, reviewer_output, review["score"], approved)

        if approved or round_number == max_rounds:
            return plan, history

        feedback = _build_feedback(review)
