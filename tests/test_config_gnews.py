import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_exposes_gnews_key(monkeypatch):
    monkeypatch.setenv("GNEWS_API_KEY", "abc123")
    from config import Config
    assert Config().GNEWS_API_KEY == "abc123"


def test_trend_scout_role_registered():
    from studio import settings
    assert settings.ROLE_MODELS["trend_scout"]
    assert settings.ROLE_EFFORT["trend_scout"]
