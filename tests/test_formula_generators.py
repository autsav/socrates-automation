import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def test_enforce_hook_len_trims_over_12_words():
    long = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
    out = pipeline._enforce_hook_len(long)
    assert len(out.split()) <= 12


def test_enforce_hook_len_leaves_short_hook():
    h = "Stop scrolling. Start living."
    assert pipeline._enforce_hook_len(h) == h


def test_enforce_bridge_len_trims_over_budget():
    # The 44-word/25s bridge that ballooned reel_013 to 45s.
    long = ("We're racing to find the perfect AI tool for every task, chasing "
            "control through more options… but 2,400 years ago Socrates already "
            "knew: real freedom isn't found in more power over the outside world "
            "— it comes from wanting only what you can actually control yourself.")
    out = pipeline._enforce_bridge_len(long)
    assert len(out.split()) <= 20
    # Prefers cutting at the natural ellipsis pivot into the Quote scene.
    assert out.rstrip().endswith("…")


def test_enforce_bridge_len_leaves_short_bridge():
    b = "But Socrates saw it 2,400 years ago…"
    assert pipeline._enforce_bridge_len(b) == b


def test_enforce_bridge_len_empty_is_safe():
    assert pipeline._enforce_bridge_len("") == ""
    assert pipeline._enforce_bridge_len(None) is None


def test_cta_variants_have_no_follow_or_like():
    joined = " ".join(pipeline._CTA_VARIANTS).lower()
    assert "follow for more" not in joined
    assert "like if" not in joined


def test_cta_variants_include_dm_trigger():
    assert any("dm you" in c.lower() or "comment '" in c.lower() for c in pipeline._CTA_VARIANTS)


def test_generate_hashtags_count_between_3_and_5():
    for aud in ("procrastinator", "unknown_aud"):
        tags = pipeline._generate_hashtags(aud, "dark_philosophical").split()
        assert 3 <= len(tags) <= 5


def test_generate_hashtags_no_generic():
    tags = pipeline._generate_hashtags("stuck", "calm_stoic").lower()
    for bad in ("#fyp", "#viral", "#reels", "#explore"):
        assert bad not in tags


def test_loopify_cta_ends_with_open_connector():
    out = pipeline._loopify("Save this for later.", "Stop wasting your evenings.")
    assert out.rstrip().endswith("—")


def test_generate_hashtags_none_mood_does_not_raise():
    tags = pipeline._generate_hashtags("stuck", None).split()
    assert 3 <= len(tags) <= 5
