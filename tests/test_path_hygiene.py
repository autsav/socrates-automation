from pathlib import Path
import pipeline


def test_rel_path_none_returns_none():
    assert pipeline._rel_path(None) is None


def test_rel_path_in_repo_is_relative():
    p = pipeline.PROJECT_ROOT / "output" / "post_x.jpg"
    assert pipeline._rel_path(p) == "output/post_x.jpg"


def test_rel_path_outside_repo_is_basename():
    assert pipeline._rel_path("/Users/someone/secret/post_x.jpg") == "post_x.jpg"


def test_rel_path_never_raises_on_junk():
    # non-path-like input must not raise and must yield a string or None
    result = pipeline._rel_path(12345)
    assert result is None or isinstance(result, str)
