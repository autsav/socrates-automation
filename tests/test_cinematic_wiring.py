"""Bridge-file payload: multi-clip backgrounds + silence drop, back-compatible."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.remotion_reel import write_bridge_file
from src.audio.elevenlabs_engine import prepare_reel_voiceover
from src.audio.voice_director import delivery_profile


def _write(tmp_path, **kw):
    p = tmp_path / "reel-data.json"
    write_bridge_file(hook="h", quote="q", attribution="— S", cta="c",
                      mood="dark_philosophical", duration=10, fps=30,
                      bridge_path=p, **kw)
    return json.loads(p.read_text())


def test_single_clip_payload_unchanged(tmp_path):
    clip = tmp_path / "one.mp4"; clip.write_bytes(b"x")
    d = _write(tmp_path, background=clip)
    assert "backgrounds" not in d and d["background"] == "bg.mp4"
    assert "silenceDropSec" not in d


def test_multi_clip_payload(tmp_path):
    clips = []
    for i in range(3):
        c = tmp_path / f"c{i}.mp4"; c.write_bytes(b"x"); clips.append(c)
    d = _write(tmp_path, backgrounds=clips, silence_drop_sec=0.8)
    assert len(d["backgrounds"]) == 3
    assert "background" not in d
    assert len(d["backgroundDurationsSec"]) == 3
    assert d["silenceDropSec"] == 0.8


def test_quote_voice_duration_absorbs_silence_drop(tmp_path, monkeypatch):
    import src.video.remotion_reel as remotion_reel
    monkeypatch.setattr(remotion_reel, "_probe_duration", lambda p: 4.0)
    qv = tmp_path / "quote.mp3"
    qv.write_bytes(b"x")
    d = _write(tmp_path, quote_voice=qv, silence_drop_sec=0.8)
    assert d["voiceDurations"]["quote"] == 4.0 + 0.8


def test_quote_voice_duration_unchanged_without_drop(tmp_path, monkeypatch):
    import src.video.remotion_reel as remotion_reel
    monkeypatch.setattr(remotion_reel, "_probe_duration", lambda p: 4.0)
    qv = tmp_path / "quote.mp3"
    qv.write_bytes(b"x")
    d = _write(tmp_path, quote_voice=qv)
    assert d["voiceDurations"]["quote"] == 4.0


def test_sfx_set_includes_riser_and_sub_impact(tmp_path):
    d = _write(tmp_path)
    if d.get("sfx"):                      # ffmpeg present in env
        assert "riser" in d["sfx"] and "sub_impact" in d["sfx"]


def test_reel_voiceover_applies_per_scene_delivery_profiles(tmp_path, monkeypatch):
    """hook/quote/cta must each get their own voice_settings — not one flat
    read for the whole reel (Important review finding: only bridge got
    per-scene direction; combined prepare_reel_voiceover ignored it)."""
    captured = []

    def _fake_generate_voiceover(text, api_key, voice, output_path, settings=None):
        from src.audio.elevenlabs_engine import DEFAULT_SETTINGS
        captured.append({**DEFAULT_SETTINGS, **(settings or {})})
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"x")
        return output_path

    import src.audio.elevenlabs_engine as el_engine
    monkeypatch.setattr(el_engine, "generate_voiceover", _fake_generate_voiceover)
    monkeypatch.setattr(el_engine, "_get_audio_duration", lambda p: 1.0)

    prepare_reel_voiceover(
        hook_text="Hook line.",
        quote_text="Quote line.",
        cta_text="CTA line.",
        mood="dark_philosophical",
        output_dir=tmp_path,
        timestamp="20260101_000000",
        api_key="fake-key",
        scene_settings={
            "hook": delivery_profile("hook"),
            "quote": delivery_profile("quote"),
            "cta": delivery_profile("cta"),
        },
    )

    assert len(captured) == 3
    hook_settings, quote_settings, cta_settings = captured
    # Hook attacks faster (lower stability 0.22 -> 0.18, +speed); the quote
    # slows for gravitas (0.70 -> 0.72, -speed). Stability still differs per scene.
    assert hook_settings["stability"] == 0.18
    assert quote_settings["stability"] == 0.72
    assert hook_settings["stability"] != quote_settings["stability"]
    assert hook_settings.get("speed") == 1.12
    assert quote_settings.get("speed") == 0.92


def test_reel_voiceover_scene_settings_default_none_is_unchanged(tmp_path, monkeypatch):
    """scene_settings=None (omitted) must reproduce current behavior exactly —
    no overrides, plain DEFAULT_SETTINGS for every scene."""
    captured = []

    def _fake_generate_voiceover(text, api_key, voice, output_path, settings=None):
        from src.audio.elevenlabs_engine import DEFAULT_SETTINGS
        captured.append(settings)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"x")
        return output_path

    import src.audio.elevenlabs_engine as el_engine
    monkeypatch.setattr(el_engine, "generate_voiceover", _fake_generate_voiceover)
    monkeypatch.setattr(el_engine, "_get_audio_duration", lambda p: 1.0)

    prepare_reel_voiceover(
        hook_text="Hook line.",
        quote_text="Quote line.",
        cta_text="CTA line.",
        mood="dark_philosophical",
        output_dir=tmp_path,
        timestamp="20260101_000001",
        api_key="fake-key",
    )

    assert captured == [None, None, None]
