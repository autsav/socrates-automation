"""Tests for the Remotion Reel bridge (src.video.remotion_reel).

Pure-Python logic is tested unconditionally; the actual Remotion render is only
exercised when Node.js + the Remotion project's node_modules are present (so CI
without Node still passes). The core guarantee under test is the graceful
fallback contract: the bridge NEVER raises and returns ``None`` when Remotion is
unavailable, so pipeline.py can fall back to the ffmpeg POV generator.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video import remotion_reel as rr


# ── Static project layout ────────────────────────────────────────────────────

def test_supported_moods_matches_theme_ts():
    """The 7 Python moods must exactly match the palette keys in theme.ts, or the
    bridge would silently send moods Remotion can't render."""
    theme = (rr.REMOTION_DIR / "src" / "styles" / "theme.ts").read_text()
    for mood in rr.SUPPORTED_MOODS:
        assert f"{mood}:" in theme, f"{mood} missing from theme.ts MOOD_PALETTES"
    assert len(rr.SUPPORTED_MOODS) == 7


def test_remotion_project_files_exist():
    for rel in ("package.json", "remotion.config.ts", "src/index.ts",
                "src/Root.tsx", "src/PovReel.tsx"):
        assert (rr.REMOTION_DIR / rel).exists(), f"missing {rel}"


def test_node_and_remotion_availability_are_bools():
    assert isinstance(rr.node_available(), bool)
    assert isinstance(rr.remotion_available(), bool)


# ── Duration clamping ────────────────────────────────────────────────────────

def test_clamp_duration_respects_bounds():
    assert rr._clamp_duration("x", 999) == rr.MAX_DURATION
    assert rr._clamp_duration("x", 1) == rr.MIN_DURATION
    mid = rr._clamp_duration("x", 10.0)
    assert mid == 10.0


def test_clamp_duration_scales_with_quote_length_when_unset():
    short = rr._clamp_duration("short", None)
    long = rr._clamp_duration("q" * 400, None)
    assert rr.MIN_DURATION <= short <= rr.MAX_DURATION
    assert rr.MIN_DURATION <= long <= rr.MAX_DURATION
    assert long >= short


# ── JSON bridge file ─────────────────────────────────────────────────────────

def test_write_bridge_file_roundtrip(tmp_path):
    p = tmp_path / "reel-data.json"
    out = rr.write_bridge_file(
        hook="Hook here",
        quote="A quote.",
        attribution="— Socrates",
        cta="Save this.",
        mood="epic_warrior",
        duration=10.5,
        fps=30,
        bridge_path=p,
    )
    assert out == p
    data = json.loads(p.read_text())
    assert data == {
        "hook": "Hook here",
        "quote": "A quote.",
        "attribution": "— Socrates",
        "cta": "Save this.",
        "mood": "epic_warrior",
        "duration": 10.5,
        "fps": 30,
        "beats": [],
        "voices": {"hook": None, "quote": None, "cta": None},
        "voiceDurations": {"hook": None, "quote": None, "cta": None},
    }


def test_write_bridge_file_falls_back_on_unknown_mood(tmp_path):
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "not_a_mood", 10.0, 30, bridge_path=p)
    data = json.loads(p.read_text())
    assert data["mood"] == rr.SUPPORTED_MOODS[0]


def test_write_bridge_file_preserves_unicode(tmp_path):
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "— Sócrates ✨", "c", "calm_stoic", 10.0, 30, bridge_path=p)
    data = json.loads(p.read_text())
    assert data["attribution"] == "— Sócrates ✨"


# ── Graceful fallback contract ───────────────────────────────────────────────

def test_generate_returns_none_when_remotion_unavailable(tmp_path, monkeypatch):
    """When Remotion isn't installed the generator must return None (never raise),
    so the pipeline can fall back to the ffmpeg POV generator."""
    monkeypatch.setattr(rr, "remotion_available", lambda: False)
    out = tmp_path / "reel.mp4"
    result = rr.generate_remotion_reel(
        hook="h", quote="q", cta="c", output_path=out,
    )
    assert result is None


def test_generate_returns_none_on_render_failure(tmp_path, monkeypatch):
    """A non-zero render exit must degrade to None, not crash the pipeline."""
    monkeypatch.setattr(rr, "remotion_available", lambda: True)

    class _FakeResult:
        returncode = 1
        stderr = "boom"
        stdout = ""

    monkeypatch.setattr(rr.subprocess, "run", lambda *a, **k: _FakeResult())
    out = tmp_path / "reel.mp4"
    result = rr.generate_remotion_reel(
        hook="h", quote="q", cta="c", output_path=out,
    )
    assert result is None


def test_generate_returns_none_on_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "remotion_available", lambda: True)

    def _raise(*a, **k):
        raise rr.subprocess.TimeoutExpired(cmd="npx", timeout=1)

    monkeypatch.setattr(rr.subprocess, "run", _raise)
    result = rr.generate_remotion_reel(
        hook="h", quote="q", cta="c", output_path=tmp_path / "r.mp4",
    )
    assert result is None


# ── Optional real render (only if Node + Remotion installed) ─────────────────

@pytest.mark.skipif(not rr.remotion_available(),
                    reason="Node.js / Remotion project not installed")
def test_real_render_produces_mp4(tmp_path):
    out = tmp_path / "reel.mp4"
    result = rr.generate_remotion_reel(
        hook="Test hook line here.",
        quote="The unexamined life is not worth living.",
        attribution="— Socrates",
        cta="Save this.",
        mood="dark_philosophical",
        output_path=out,
        duration=8.0,
    )
    assert result is not None
    assert out.exists()
    assert out.stat().st_size > 10_000


# ── Voiceover + beat detection ──────────────────────────────────────────────────

def test_bridge_no_audio_has_empty_voices_no_music(tmp_path):
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p)
    data = json.loads(p.read_text())
    assert data["voices"] == {"hook": None, "quote": None, "cta": None}
    assert data["voiceDurations"] == {"hook": None, "quote": None, "cta": None}
    assert data["beats"] == []
    assert "music" not in data


def test_bridge_three_voices_and_music_copied(tmp_path, monkeypatch):
    monkeypatch.setattr(rr.beat_sync, "detect_beats", lambda path, **k: [0.4, 1.1])
    monkeypatch.setattr(rr, "_probe_duration", lambda path: 2.5)
    files = {}
    for key in ("hook", "quote", "cta", "music"):
        f = tmp_path / f"{key}.wav"
        f.write_bytes(b"RIFFfake")
        files[key] = f
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file(
        "h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p,
        hook_voice=files["hook"], quote_voice=files["quote"],
        cta_voice=files["cta"], music_path=files["music"],
    )
    data = json.loads(p.read_text())
    assert data["voices"] == {"hook": "vo-hook.wav", "quote": "vo-quote.wav", "cta": "vo-cta.wav"}
    assert data["music"] == "music.wav"
    assert data["voiceDurations"] == {"hook": 2.5, "quote": 2.5, "cta": 2.5}
    assert data["beats"] == [0.4, 1.1]
    for name in ("vo-hook.wav", "vo-quote.wav", "vo-cta.wav", "music.wav"):
        assert (tmp_path / name).read_bytes() == b"RIFFfake"


def test_bridge_music_copied_from_distinct_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "_probe_duration", lambda path: None)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    music = src_dir / "track.mp3"
    music.write_bytes(b"MUSICBYTES")
    p = tmp_path / "reel-data.json"   # bridge dir = tmp_path, distinct from src_dir
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p, music_path=music)
    data = json.loads(p.read_text())
    assert data["music"] == "music.mp3"
    copied = tmp_path / "music.mp3"
    assert copied.exists() and copied.read_bytes() == b"MUSICBYTES"  # a real copy, distinct path


def test_bridge_copy_failure_degrades(tmp_path, monkeypatch):
    def boom(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(rr.shutil, "copy", boom)
    vo = tmp_path / "q.wav"
    vo.write_bytes(b"x")
    p = tmp_path / "reel-data.json"
    rr.write_bridge_file("h", "q", "a", "c", "calm_stoic", 10.0, 30, bridge_path=p, quote_voice=vo)
    data = json.loads(p.read_text())
    assert data["voices"]["quote"] is None
    assert "music" not in data


def test_generate_forwards_voices_to_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "remotion_available", lambda: True)
    seen = {}

    def fake_write(*a, **k):
        seen.update(k)
        pth = tmp_path / "reel-data.json"
        pth.write_text("{}")
        return pth

    class _Ok:
        returncode = 0
        stderr = ""
        stdout = ""

    out = tmp_path / "reel.mp4"

    def fake_run(*a, **k):
        out.write_bytes(b"mp4")
        return _Ok()

    monkeypatch.setattr(rr, "write_bridge_file", fake_write)
    monkeypatch.setattr(rr.subprocess, "run", fake_run)
    monkeypatch.setattr(rr.shutil, "which", lambda name: None)  # skip loudnorm
    q = tmp_path / "q.wav"; q.write_bytes(b"x")
    rr.generate_remotion_reel(hook="h", quote="q", cta="c", output_path=out, quote_voice=q)
    assert seen.get("quote_voice") == q
