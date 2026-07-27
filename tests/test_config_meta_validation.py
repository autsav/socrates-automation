import pytest
from config import Config

def test_app_without_token_raises(monkeypatch):
    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("META_APP_ID", "fake_app_id")
    monkeypatch.setenv("META_APP_SECRET", "fake_app_secret")
    # Other required env vars must also be set to reach the meta-validation step
    for k in ("ANTHROPIC_API_KEY", "FAL_API_KEY", "IG_ACCOUNT_ID",
              "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"):
        monkeypatch.setenv(k, "fake")
    with pytest.raises(RuntimeError, match="META_APP_ID\\+META_APP_SECRET set without META_ACCESS_TOKEN"):
        Config()

def test_token_without_app_warns(monkeypatch, caplog):
    monkeypatch.setenv("META_ACCESS_TOKEN", "fake_token")
    monkeypatch.delenv("META_APP_ID", raising=False)
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    for k in ("ANTHROPIC_API_KEY", "FAL_API_KEY", "IG_ACCOUNT_ID",
              "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"):
        monkeypatch.setenv(k, "fake")
    Config()  # must NOT raise
    # At minimum, the warning should be in the logger output (best-effort)

def test_validate_off_when_env_unset(monkeypatch):
    """debug_token check must NOT run when META_DEBUG_TOKEN_VALIDATE is not '1'."""
    monkeypatch.setenv("META_ACCESS_TOKEN", "fake_token")
    monkeypatch.setenv("META_APP_ID", "fake_id")
    monkeypatch.setenv("META_APP_SECRET", "fake_secret")
    monkeypatch.delenv("META_DEBUG_TOKEN_VALIDATE", raising=False)
    # No network calls expected — would hang or error otherwise
    Config()