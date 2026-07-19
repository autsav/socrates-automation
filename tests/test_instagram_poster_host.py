import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.instagram_poster import _graph, GRAPH_URL, FB_GRAPH_URL


def test_fb_tokens_route_to_facebook_graph():
    assert _graph("EAASvLoe2XGUBSILUj7xxx") == FB_GRAPH_URL


def test_ig_tokens_route_to_instagram_graph():
    assert _graph("IGQVJcm8Urxxx") == GRAPH_URL
    assert _graph("") == GRAPH_URL
