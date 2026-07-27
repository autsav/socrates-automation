"""Task 2 — dry_run must thread through the orchestrator so that no
side-effecting writes (artifact JSON, checkpoint JSON) happen when
dry_run=True. This test stubs every heavy stage so the only thing that
could write is the orchestrator's own artifact/checkpoint loops.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import team.orchestrator as orch
from team.models import DebateResult


def test_dry_run_does_not_write_artifacts(monkeypatch):
    """dry_run=True must skip the artifact-file write loop AND checkpoint
    writes — no Path.write_text calls at all."""
    written = []
    monkeypatch.setattr(orch.Path, "write_text",
                        lambda self, *a, **kw: written.append(str(self)))

    # Force a minimal successful pipeline by bypassing the heavy stages
    monkeypatch.setattr(orch, "_load_checkpoint", lambda run_date: None)
    monkeypatch.setattr(orch.data_store, "init_db", lambda: None)

    # Stub every stage to a no-op returning a serializable object
    def fake_stage(name, fn, summarize, *, on_stage_start=None,
                   on_stage_done=None, on_stage_failed=None,
                   on_cost_update=None):
        if on_stage_start:
            on_stage_start(name)
        result = fn()
        if on_stage_done:
            on_stage_done(name, summarize(result))
        return result

    monkeypatch.setattr(orch, "_stage", fake_stage)

    class _A:
        date = "2026-07-27"
        avg_engagement_rate = 0.1
        top_performing_hooks = []
        total_posts = 0
        hashtags = []
        sounds = []

        def to_dict(self):
            return {"a": 1}

    monkeypatch.setattr(orch, "AnalyticsAnalystAgent",
                        lambda c: MagicMock(run=lambda now=None: _A()))
    monkeypatch.setattr(orch, "TrendScraperAgent",
                        lambda: MagicMock(run=lambda: _A()))
    monkeypatch.setattr(orch, "_build_pool", lambda x: [])
    monkeypatch.setattr(orch, "PlannerAgent", lambda c: MagicMock())
    monkeypatch.setattr(orch, "ReviewerAgent", lambda c: MagicMock())
    monkeypatch.setattr(orch, "ContentWriterAgent",
                        lambda c: MagicMock(run=lambda p: [_A()]))
    monkeypatch.setattr(orch, "VisualDesignerAgent",
                        lambda c: MagicMock(run=lambda p, s: [_A()]))
    monkeypatch.setattr(orch, "AudioEngineerAgent",
                        lambda c: MagicMock(run=lambda p, s: [_A()]))
    monkeypatch.setattr(orch, "VideoEditorAgent",
                        lambda c: MagicMock(run=lambda p, v, a: [_A()]))

    class _VQR:
        @staticmethod
        def needs_regeneration(scores):
            return []

        def __init__(self, c):
            self.run = lambda v, cc: [_A()]

    monkeypatch.setattr(orch, "VideoQualityReviewerAgent", _VQR)
    monkeypatch.setattr(orch, "EngagementStrategistAgent",
                        lambda c: MagicMock(run=lambda p, c: [_A()]))
    monkeypatch.setattr(orch, "run_debate",
                        lambda p, r, *a, **kw: (_A(), [
                            DebateResult(round_number=1, planner_output="",
                                          reviewer_output="",
                                          reviewer_score=8.5, approved=True,
                                          final_plan=_A())
                        ]))

    orch.run_team_pipeline(dry_run=True, client=MagicMock())

    assert written == [], f"dry_run=True wrote artifacts: {written}"