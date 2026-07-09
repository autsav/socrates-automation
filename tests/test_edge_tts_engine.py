from pathlib import Path
from unittest.mock import patch, MagicMock

from src.audio.edge_tts_engine import (
    get_voice_for_mood,
    generate_scene_voiceover_edge_tts,
    prepare_reel_voiceover_edge_tts,
    edge_tts_available,
    VOICE_MAP,
    DEFAULT_VOICE,
)


def test_get_voice_for_mood_known():
    for mood, voice in VOICE_MAP.items():
        assert get_voice_for_mood(mood) == voice


def test_get_voice_for_mood_unknown_falls_back_to_default():
    assert get_voice_for_mood("nonexistent_mood") == DEFAULT_VOICE


def test_generate_scene_voiceover_edge_tts_success(tmp_path):
    output_path = tmp_path / "voice.mp3"

    def fake_run(cmd, **kwargs):
        output_path.write_bytes(b"fake-mp3-bytes")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    with patch("subprocess.run", side_effect=fake_run):
        ok = generate_scene_voiceover_edge_tts("Know thyself.", "en-US-ChristopherNeural", output_path)

    assert ok is True
    assert output_path.exists()


def test_generate_scene_voiceover_edge_tts_cli_failure(tmp_path):
    output_path = tmp_path / "voice.mp3"
    result = MagicMock()
    result.returncode = 1
    result.stderr = "some tts error"

    with patch("subprocess.run", return_value=result):
        ok = generate_scene_voiceover_edge_tts("Know thyself.", "en-US-ChristopherNeural", output_path)

    assert ok is False
    assert not output_path.exists()


def test_generate_scene_voiceover_edge_tts_not_installed(tmp_path):
    output_path = tmp_path / "voice.mp3"

    with patch("subprocess.run", side_effect=FileNotFoundError):
        ok = generate_scene_voiceover_edge_tts("Know thyself.", "en-US-ChristopherNeural", output_path)

    assert ok is False


def test_generate_scene_voiceover_edge_tts_trims_long_text(tmp_path):
    output_path = tmp_path / "voice.mp3"
    long_text = "a" * 500
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["text"] = cmd[cmd.index("--text") + 1]
        output_path.write_bytes(b"fake")
        result = MagicMock()
        result.returncode = 0
        return result

    with patch("subprocess.run", side_effect=fake_run):
        generate_scene_voiceover_edge_tts(long_text, "en-US-ChristopherNeural", output_path)

    assert len(captured["text"]) <= 300


def test_prepare_reel_voiceover_edge_tts_all_success(tmp_path):
    def fake_run(cmd, **kwargs):
        out = Path(cmd[cmd.index("--write-media") + 1])
        out.write_bytes(b"fake")
        result = MagicMock()
        result.returncode = 0
        return result

    with patch("subprocess.run", side_effect=fake_run):
        result = prepare_reel_voiceover_edge_tts(
            hook_text="This will change everything.",
            quote_text="Know thyself.",
            cta_text="Follow for more.",
            mood="dark_philosophical",
            output_dir=tmp_path,
            timestamp="20260101",
        )

    assert result["voice"] == "en-US-ChristopherNeural"
    assert result["hook_voice"] is not None
    assert result["quote_voice"] is not None
    assert result["cta_voice"] is not None
    assert Path(result["hook_voice"]).exists()


def test_prepare_reel_voiceover_edge_tts_partial_failure(tmp_path):
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        result = MagicMock()
        if calls["n"] == 2:
            result.returncode = 1
            result.stderr = "failed"
        else:
            out = Path(cmd[cmd.index("--write-media") + 1])
            out.write_bytes(b"fake")
            result.returncode = 0
        return result

    with patch("subprocess.run", side_effect=fake_run):
        result = prepare_reel_voiceover_edge_tts(
            hook_text="hook", quote_text="quote", cta_text="cta",
            mood="calm_stoic", output_dir=tmp_path, timestamp="ts",
        )

    assert result["hook_voice"] is not None
    assert result["quote_voice"] is None
    assert result["cta_voice"] is not None


def test_edge_tts_available_true():
    result = MagicMock()
    result.returncode = 0
    with patch("subprocess.run", return_value=result):
        assert edge_tts_available() is True


def test_edge_tts_available_false_when_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert edge_tts_available() is False
