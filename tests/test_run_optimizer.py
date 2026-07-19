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
