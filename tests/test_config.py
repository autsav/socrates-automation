import pytest
from pathlib import Path

# Ensure we import from the parent package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config


def test_config_loads_from_env(monkeypatch):
    """Config dataclass should pull values from environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("FAL_API_KEY", "fal-test-456")
    monkeypatch.setenv("META_ACCESS_TOKEN", "meta-test-789")
    monkeypatch.setenv("IG_ACCOUNT_ID", "123456789")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "cloud-key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "cloud-secret")

    cfg = Config()
    assert cfg.ANTHROPIC_API_KEY == "sk-test-123"
    assert cfg.FAL_API_KEY == "fal-test-456"
    assert cfg.META_ACCESS_TOKEN == "meta-test-789"
    assert cfg.IG_ACCOUNT_ID == "123456789"
    assert cfg.CLOUDINARY_CLOUD_NAME == "test-cloud"
    assert cfg.CLOUDINARY_API_KEY == "cloud-key"
    assert cfg.CLOUDINARY_API_SECRET == "cloud-secret"


def test_config_raises_on_missing_env(monkeypatch):
    """Config should fail fast when required env vars are missing."""
    for key in [
        "ANTHROPIC_API_KEY", "FAL_API_KEY", "META_ACCESS_TOKEN",
        "IG_ACCOUNT_ID", "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variable"):
        Config()
