import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import loop, registry
import optimize


def _good(client, key, champ, perf):
    return {"candidate": champ + " x", "rationale": "r", "predicted_delta": 0.2}


def test_format_proposal_message_has_key_and_delta():
    msg = loop.format_proposal_message({
        "key": "prompt.strategist.role", "rationale": "tighter hooks",
        "predicted_delta": 0.15, "candidate": "X" * 500,
    })
    assert "prompt.strategist.role" in msg
    assert "15" in msg              # 0.15 → +15%
    assert "tighter hooks" in msg
    assert len(msg) < 1200


def test_dry_run_sends_nothing(tmp_path, capsys):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    sent = []
    rc = optimize.main(
        ["--dry-run"], client=None, notify=lambda m: sent.append(m),
        db_path=db, propose_fn=_good,
    )
    assert rc == 0
    assert sent == []
    assert "prompt." in capsys.readouterr().out


def test_run_notifies_each_proposal(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    sent = []
    rc = optimize.main(
        ["--run"], client=None, notify=lambda m: sent.append(m),
        db_path=db, propose_fn=_good,
    )
    assert rc == 0
    assert len(sent) >= 1
