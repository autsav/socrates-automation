import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_exposes_jamendo_client_id(monkeypatch):
    monkeypatch.setenv("JAMENDO_CLIENT_ID", "abc123")
    # Config reads os.environ via _get_opt; construct fresh.
    from config import Config
    cfg = Config()
    assert cfg.JAMENDO_CLIENT_ID == "abc123"


def test_config_jamendo_defaults_empty(monkeypatch):
    monkeypatch.delenv("JAMENDO_CLIENT_ID", raising=False)
    from config import Config
    cfg = Config()
    assert cfg.JAMENDO_CLIENT_ID == ""
