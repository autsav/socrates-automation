import subprocess


def _tracked(path):
    out = subprocess.run(["git", "ls-files", path], capture_output=True, text=True).stdout
    return bool(out.strip())


def test_junk_is_untracked():
    assert not _tracked("logs/posts.jsonl")
    assert not _tracked("server.log")
    assert not _tracked(".DS_Store")
    # no output jpgs tracked
    out = subprocess.run(["git", "ls-files", "output/"], capture_output=True, text=True).stdout
    assert ".jpg" not in out


def test_mood_beds_stay_tracked():
    for mood in ["calm_stoic", "cinematic_hopeful", "dark_philosophical",
                 "dramatic_ancient", "epic_warrior", "mystical_greek", "stark_minimal"]:
        assert _tracked(f"audio/{mood}.mp3"), f"mood bed {mood} must stay tracked"
