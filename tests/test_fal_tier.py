import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.visual import image_generator as ig


def test_resolve_tier_defaults_to_pro(monkeypatch):
    monkeypatch.delenv("FAL_TIER", raising=False)
    assert ig._resolve_tier() == "pro"


def test_resolve_tier_reads_env_and_rejects_unknown(monkeypatch):
    monkeypatch.setenv("FAL_TIER", "dev")
    assert ig._resolve_tier() == "dev"
    monkeypatch.setenv("FAL_TIER", "bogus")
    assert ig._resolve_tier() == "pro"


def test_fal_url_maps_tiers():
    assert ig._fal_url("pro").endswith("flux-pro/v1.1")
    assert ig._fal_url("dev").endswith("flux/dev")
    assert ig._fal_url("schnell").endswith("flux/schnell")


def test_payload_pro_omits_steps_has_safety():
    p = ig._build_payload("pro", "a prompt", 123)
    assert "num_inference_steps" not in p and "guidance_scale" not in p
    assert p.get("safety_tolerance")
    assert p["seed"] == 123 and p["image_size"] == "portrait_16_9" and p["num_images"] == 1


def test_payload_schnell_has_steps_and_guidance():
    p = ig._build_payload("schnell", "a prompt", 7)
    assert p["num_inference_steps"] and p["guidance_scale"]
    assert p["seed"] == 7
