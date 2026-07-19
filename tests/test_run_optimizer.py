"""Weekly cadence entrypoint wires digest -> critic (spec 2.4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import run_optimizer


def test_main_passes_digest_as_perf_context(monkeypatch):
    captured = {}
    monkeypatch.setattr(run_optimizer, "_digest", lambda: "DIGEST BLOCK")
    monkeypatch.setattr(run_optimizer.loop, "evaluate_experiments", lambda: [])
    monkeypatch.setattr(run_optimizer.loop, "run_once",
                        lambda client, perf_context, **kw:
                        captured.setdefault("ctx", perf_context) or [])
    monkeypatch.setattr(run_optimizer, "_client", lambda: object())
    run_optimizer.main(dry_run=True)
    assert captured["ctx"] == "DIGEST BLOCK"


def test_main_surfaces_each_proposal_to_telegram(monkeypatch):
    surfaced = []
    eval_proposal = {"key": "story_writer", "challenger_version_id": 1}
    run_proposal = {"key": "hook_writer", "challenger_version_id": 2}
    monkeypatch.setattr(run_optimizer, "_digest", lambda: "DIGEST BLOCK")
    monkeypatch.setattr(run_optimizer.loop, "evaluate_experiments", lambda: [eval_proposal])
    monkeypatch.setattr(run_optimizer.loop, "run_once",
                        lambda client, perf_context, **kw: [run_proposal])
    monkeypatch.setattr(run_optimizer, "_client", lambda: object())
    monkeypatch.setattr(run_optimizer, "_surface",
                        lambda proposal, msg: surfaced.append(proposal))

    run_optimizer.main(dry_run=False)

    assert surfaced == [eval_proposal, run_proposal]


def test_main_dry_run_never_surfaces(monkeypatch):
    surfaced = []
    proposal = {"key": "story_writer", "challenger_version_id": 1}
    monkeypatch.setattr(run_optimizer, "_digest", lambda: "DIGEST BLOCK")
    monkeypatch.setattr(run_optimizer.loop, "evaluate_experiments", lambda: [proposal])
    monkeypatch.setattr(run_optimizer.loop, "run_once",
                        lambda client, perf_context, **kw: [proposal])
    monkeypatch.setattr(run_optimizer, "_client", lambda: object())
    monkeypatch.setattr(run_optimizer, "_surface",
                        lambda proposal, msg: surfaced.append(proposal))

    run_optimizer.main(dry_run=True)

    assert surfaced == []


def test_surface_failure_never_raises(monkeypatch):
    monkeypatch.setattr(run_optimizer, "_digest", lambda: "DIGEST BLOCK")
    monkeypatch.setattr(run_optimizer.loop, "evaluate_experiments", lambda: [])
    monkeypatch.setattr(run_optimizer.loop, "run_once",
                        lambda client, perf_context, **kw:
                        [{"key": "story_writer", "challenger_version_id": 1}])
    monkeypatch.setattr(run_optimizer, "_client", lambda: object())

    class _Boom:
        def _default_surface(self, proposal, msg):
            raise RuntimeError("telegram down")

    monkeypatch.setitem(sys.modules, "optimize", _Boom())

    # Must not raise even though the real surfacing mechanism blows up.
    run_optimizer.main(dry_run=False)
