"""Copywriter agent — drafts N concepts and revises one on Director feedback."""
import json

from studio import settings
from studio.strategist import shared_prefix
from studio.types import Concept, CONCEPTS_SCHEMA, CONCEPT_SCHEMA

_DRAFT_ROLE = (
    "You are the Copywriter. Brief:\n{brief}\n"
    "Write {n} distinct concepts, each a different angle on this brief. "
    "Each concept: a <=60-char scroll-stopping hook (Reel scene 1 / image "
    "headline), a full caption (curiosity-gap first line, payoff, share/save CTA), "
    "a one-line cta, reel_scenes (on-screen text per scene; [] if not a reel), and "
    "5-8 hashtags. Do NOT change the quote text. Output {{\"concepts\": [...]}} as "
    "JSON only."
)
_REVISE_ROLE = (
    "You are the Copywriter. Brief:\n{brief}\nConcept to revise:\n{concept}\n"
    "Creative Director feedback: {feedback}\n"
    "Return one improved concept (same id) as JSON only."
)


def draft(client, perf, brief, n=settings.N_CONCEPTS):
    role = _DRAFT_ROLE.format(brief=json.dumps(brief.to_dict(), indent=2), n=n)
    data = client.call("copywriter", shared_prefix(perf), role,
                       "Write the concepts now.", CONCEPTS_SCHEMA)
    return [Concept.from_dict(c) for c in data["concepts"]]


def revise(client, perf, brief, concept, feedback):
    role = _REVISE_ROLE.format(
        brief=json.dumps(brief.to_dict(), indent=2),
        concept=json.dumps(concept.to_dict(), indent=2), feedback=feedback)
    data = client.call("copywriter", shared_prefix(perf), role,
                       "Revise the concept now.", CONCEPT_SCHEMA)
    return Concept.from_dict(data)
