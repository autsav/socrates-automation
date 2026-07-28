import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_social_strategist_model_registered():
    """Opus 4-7 by default; env STRATEGIST_MODEL overrides."""
    import os
    from studio import settings

    saved = os.environ.pop("STRATEGIST_MODEL", None)
    try:
        import importlib
        importlib.reload(settings)
        assert settings.ROLE_MODELS["social_strategist"] == "claude-opus-4-7"
    finally:
        if saved is not None:
            os.environ["STRATEGIST_MODEL"] = saved
        importlib.reload(settings)


def test_social_strategist_model_env_override(monkeypatch):
    monkeypatch.setenv("STRATEGIST_MODEL", "claude-opus-4-8")
    from studio import settings
    import importlib
    importlib.reload(settings)
    assert settings.ROLE_MODELS["social_strategist"] == "claude-opus-4-8"
    importlib.reload(settings)  # restore


def test_social_strategist_effort_high():
    from studio import settings
    assert settings.ROLE_EFFORT["social_strategist"] == "high"


def test_strategy_audience_default():
    import os
    from studio import settings

    saved = os.environ.pop("STRATEGY_AUDIENCE", None)
    try:
        import importlib
        importlib.reload(settings)
        assert settings.STRATEGY_AUDIENCE == "procrastinators and doomscrollers who feel stuck"
    finally:
        if saved is not None:
            os.environ["STRATEGY_AUDIENCE"] = saved
        importlib.reload(settings)
