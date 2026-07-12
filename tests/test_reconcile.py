from studio import reconcile
from studio.reconcile import reconcile_token, match, _match_by_time


def _media(id_, caption, ts):
    return {"id": id_, "caption": caption, "timestamp": ts}


def test_match_token_present():
    tok = reconcile_token(5)
    media = [_media("A", "hello world", "t"), _media("B", f"deep quote {tok}", "t")]
    assert match({"caption_marker": tok}, media) == "B"


def test_match_survives_caption_edit():
    # Human rewrote the whole caption but kept the trailing hashtag.
    tok = reconcile_token(5)
    media = [_media("B", f"totally different words the human typed {tok}", "t")]
    assert match({"caption_marker": tok}, media) == "B"


def test_time_fallback_picks_nearest_in_window():
    created = "2026-07-12T12:00:00+0000"
    media = [
        _media("far", "no token", "2026-07-12T20:00:00+0000"),   # 8h -> out of window
        _media("near", "no token", "2026-07-12T13:30:00+0000"),  # 1.5h -> in window
    ]
    assert _match_by_time(created, media, claimed=set()) == "near"


def test_time_fallback_none_when_all_out_of_window():
    created = "2026-07-12T12:00:00+0000"
    media = [_media("far", "no token", "2026-07-13T12:00:00+0000")]  # 24h
    assert _match_by_time(created, media, claimed=set()) is None


def test_time_fallback_skips_claimed():
    created = "2026-07-12T12:00:00+0000"
    media = [_media("near", "no token", "2026-07-12T12:30:00+0000")]
    assert _match_by_time(created, media, claimed={"near"}) is None


def test_time_fallback_never_raises_on_bad_timestamp():
    assert _match_by_time("garbage", [_media("x", "c", "also-garbage")], claimed=set()) is None


def test_time_fallback_naive_created_at_vs_aware_media():
    # PRODUCTION shape: sqlite created_at is naive; IG media timestamp is tz-aware.
    created = "2026-07-12 12:00:00"  # naive, sqlite CURRENT_TIMESTAMP format
    media = [_media("near", "no token", "2026-07-12T13:30:00+0000")]  # aware, 1.5h
    assert _match_by_time(created, media, claimed=set()) == "near"
