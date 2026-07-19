"""Every writer agent sees what actually performed (spec 2.2/C)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import studio.copywriter as copywriter


class _Perf:
    def to_dict(self):
        return {}


class _Brief:
    def to_dict(self):
        return {"quote": "q", "audience": "a"}


def test_copywriter_appends_digest_to_user_message():
    seen = {}

    class Spy:
        def call(self, role, prefix, role_system, user, schema):
            seen["user"] = user
            return {"concepts": []}

    copywriter.draft(Spy(), _Perf(), _Brief(), n=1,
                     extra_context="Recent performance: X wins")
    assert "Recent performance: X wins" in seen["user"]


def test_empty_context_leaves_message_unchanged():
    seen = {}

    class Spy:
        def call(self, role, prefix, role_system, user, schema):
            seen["user"] = user
            return {"concepts": []}

    copywriter.draft(Spy(), _Perf(), _Brief(), n=1)
    assert seen["user"] == "Write the concepts now."
