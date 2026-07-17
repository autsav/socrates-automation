"""Bridge: converts team system output artifacts into the quote_data dict
that pipeline.py's run_pipeline() expects.

The team system produces a 7-day ContentPlan with CopySpec, VisualSpec, etc.
This module picks a single day's post from the plan and maps it into the
legacy pipeline's expected format, so pipeline.py can render + publish it
using the same code path as the studio and legacy modes.

Usage in pipeline.py:
    from team.bridge import load_team_post
    quote_data = load_team_post(run_date, slot)
    if quote_data:
        run_pipeline(..., content=quote_data)  # bypass excel+studio
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from team.models import ContentPlan, CopySpec, VisualSpec

log = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent / "output"


def _slot_to_post_number(slot: int) -> int:
    """Map a posting slot (0=morning, 1=afternoon, 2=evening) to the
    post_number in the team plan. The team plan uses 1-based post numbers
    for 7 posts across the week; we pick by slot index."""
    return slot + 1


def load_team_plan(run_date: str | None = None) -> ContentPlan | None:
    """Load the team system's approved plan for a given date.

    Looks for team/output/approved_plan_{date}.json. Returns None if no
    plan exists (caller should fall back to studio/legacy).
    """
    if run_date is None:
        from datetime import date as date_cls
        run_date = date_cls.today().isoformat()

    plan_path = _OUTPUT_DIR / f"approved_plan_{run_date}.json"
    if not plan_path.exists():
        log.info(f"[team-bridge] no plan found for {run_date} at {plan_path}")
        return None

    try:
        data = json.loads(plan_path.read_text())
        return ContentPlan.from_dict(data)
    except Exception as e:
        log.warning(f"[team-bridge] failed to load plan: {e}")
        return None


def load_team_specs(run_date: str, kind: str) -> list:
    """Load copy/visual/audio specs from the team output."""
    path = _OUTPUT_DIR / f"{kind}_{run_date}.json"
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text())
        items = data.get("items", [])
        if kind == "copy":
            return [CopySpec.from_dict(x) for x in items]
        elif kind == "visual_specs":
            return [VisualSpec.from_dict(x) for x in items]
        return items
    except Exception as e:
        log.warning(f"[team-bridge] failed to load {kind}: {e}")
        return []


def team_post_to_quote_data(
    plan: ContentPlan,
    copy_specs: list[CopySpec],
    visual_specs: list[VisualSpec] | None,
    slot: int,
) -> dict | None:
    """Convert a team plan post + copy spec into pipeline.py's quote_data format.

    Returns None if the post_number doesn't exist in the plan/copy specs.
    """
    post_number = _slot_to_post_number(slot)

    # Find the matching post plan
    post_plan = next(
        (p for p in plan.posts if p.post_number == post_number), None
    )
    if post_plan is None:
        log.warning(f"[team-bridge] no post #{post_number} in plan for {plan.date}")
        return None

    # Find the matching copy spec
    copy = next((c for c in copy_specs if c.post_number == post_number), None)
    if copy is None:
        log.warning(f"[team-bridge] no copy spec for post #{post_number}")
        return None

    # Find the matching visual spec (optional)
    visual = None
    if visual_specs:
        visual = next(
            (v for v in visual_specs if v.post_number == post_number), None
        )

    quote_data = {
        "quote": "",  # Will be filled from the quote pool by row_number
        "row_number": post_plan.quote_id,
        "audience": post_plan.audience,
        "caption": copy.caption,
        "hook": copy.hook,
        "mood": post_plan.mood,
        "format": post_plan.format,
        "source": "team",
        "cta": copy.cta,
        "hashtags": copy.hashtags,
    }

    # If the visual spec has a flux_prompt, pass it through
    if visual and visual.flux_prompt:
        quote_data["flux_override"] = visual.flux_prompt

    log.info(
        f"[team-bridge] mapped post #{post_number} (slot {slot}): "
        f"audience={post_plan.audience}, mood={post_plan.mood}, "
        f"hook={copy.hook[:40]}..."
    )
    return quote_data


def load_team_post(run_date: str | None = None, slot: int = 0) -> dict | None:
    """Convenience: load plan + specs and return a single quote_data dict.

    This is the main entry point for pipeline.py to use the team system's
    output. Returns None if no team plan exists (fall back to studio/legacy).
    """
    plan = load_team_plan(run_date)
    if plan is None:
        return None

    copy_specs = load_team_specs(plan.date, "copy")
    visual_specs = load_team_specs(plan.date, "visual_specs")

    if not copy_specs:
        log.warning(f"[team-bridge] no copy specs for {plan.date}")
        return None

    return team_post_to_quote_data(plan, copy_specs, visual_specs, slot)