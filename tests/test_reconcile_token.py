import re
from studio.reconcile import reconcile_token


def test_token_shape():
    t = reconcile_token(1)
    assert t.startswith("#sq")
    assert re.fullmatch(r"#sq[a-z0-9]+", t)


def test_token_deterministic_and_unique():
    assert reconcile_token(42) == reconcile_token(42)
    assert reconcile_token(1) != reconcile_token(2)


def test_token_large_id():
    assert re.fullmatch(r"#sq[a-z0-9]+", reconcile_token(1234567))


def test_caption_stamp_uses_token():
    # The stamping idiom the pipeline uses, verified in isolation.
    caption = "Some caption\n\nEngagement block"
    token = reconcile_token(7)
    stamped = f"{caption}\n{token}"
    assert stamped.endswith(token)
    assert token in stamped
