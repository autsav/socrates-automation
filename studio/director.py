"""Creative Director agent — scores concepts, runs <=1 revision, emits visual direction."""
import json

from studio import copywriter
from studio.strategist import shared_prefix
from studio.types import Decision, DECISION_SCHEMA

_ROLE = (
    "You are the Creative Director — the quality gate. Brief:\n{brief}\n"
    "Concepts:\n{concepts}\n"
    "Score each concept 0-10 against the brief and what the data says lands. Pick "
    "top_pick and alt_pick. If the top pick is weak (<8) and fixable, set "
    "revision.requested=true with the concept_id and specific feedback; otherwise "
    "requested=false. Emit visual_direction (mood MUST be one of the allowed enum "
    "values; a full flux_prompt for the background; typography and palette hints). "
    "Write a short rationale for the human reviewer. JSON only."
)


def build_prompt(perf, brief, concepts):
    role = _ROLE.format(
        brief=json.dumps(brief.to_dict(), indent=2),
        concepts=json.dumps([c.to_dict() for c in concepts], indent=2))
    return shared_prefix(perf), role


def parse_response(d):
    return Decision.from_dict(d)


def _score(client, perf, brief, concepts):
    prefix, role = build_prompt(perf, brief, concepts)
    return parse_response(client.call("director", prefix, role,
                                      "Review the concepts now.", DECISION_SCHEMA))


def review(client, perf, brief, concepts):
    decision = _score(client, perf, brief, concepts)
    rev = decision.revision or {}
    if rev.get("requested"):
        target = next((c for c in concepts if c.id == rev.get("concept_id")), None)
        if target is not None:
            improved = copywriter.revise(client, perf, brief, target,
                                         rev.get("feedback", ""))
            concepts = [improved if c.id == improved.id else c for c in concepts]
            decision = _score(client, perf, brief, concepts)
    return decision
