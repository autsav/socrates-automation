from src.audio import trending_audio


def test_fallback_tracks_have_non_empty_urls():
    for key, entry in trending_audio.FALLBACK_TRACKS.items():
        assert entry.get("url"), f"FALLBACK_TRACKS[{key!r}].url is empty"


def test_fallback_tracks_have_required_keys():
    for key, entry in trending_audio.FALLBACK_TRACKS.items():
        assert "title" in entry, f"FALLBACK_TRACKS[{key!r}] missing 'title'"
        assert "artist" in entry, f"FALLBACK_TRACKS[{key!r}] missing 'artist'"