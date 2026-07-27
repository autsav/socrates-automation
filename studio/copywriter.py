"""Copywriter agent — drafts N concepts and revises one on Director feedback."""
import json

from studio import settings, playbooks
from studio.strategist import shared_prefix
from studio.types import Concept, CONCEPTS_SCHEMA, CONCEPT_SCHEMA
from src.optimizer import prompt_store

_DRAFT_ROLE_DEFAULT = (
    "You are the Copywriter. Brief:\n{brief}\n"
    "Write {n} distinct concepts, each a different angle on this brief. "
    "Apply the TEMPORAL SCRIPTING FORMULA on every concept's reel_scenes:\n"
    "  HOOK (0-3s): <=12 words. A STATEMENT, not a question. Calls the viewer "
    "out (uses 'you'/'your'). Sets up a curiosity loop about THEIR life. "
    "  DEVELOPMENT (3-40s): short staccato sentences (<=12 words each). "
    "Pivot every 8-10 seconds — a new beat, a new image, a new micro-revelation. "
    "Do not resolve loops early; do not use 'lesson'/'secret'/'answer' vocabulary.\n"
    "  CLOSE (40-45s): CTA scene. MUST be a debate prompt ('Agree or disagree: ...') "
    "OR a DM-share prompt ('Send this to the friend who...') OR a checklist save "
    "('Save this if you need the 3-step framework'). NEVER 'Follow for more' or "
    "other generic engagement bait.\n"
    "Each concept also needs: a full caption (controversial first line that "
    "sparks debate, then the payoff, then the same CTA echoed), reel_scenes "
    "(on-screen text per scene with the timing above; [] if not a reel), and "
    "3-5 non-generic hashtags. CTAs and emphatic beats may carry ElevenLabs "
    "emotion tags: [calmly] [emphatic] [dryly] [pause] [sighs] [sarcastically]. "
    "Do NOT change the quote text. Output {{\"concepts\": [...]}} as JSON only.\n"
    + playbooks.COPY_CRAFT
    + "\nBefore answering: draft internally, critique against the copy craft "
    "rules, fix every weakness, output ONLY the improved final JSON.\n"
    "\nWrite captions in first person — a mentor speaking to one reader.\n"
)
_REVISE_ROLE_DEFAULT = (
    "You are the Copywriter. Brief:\n{brief}\nConcept to revise:\n{concept}\n"
    "Creative Director feedback: {feedback}\n"
    "Re-apply the Temporal Scripting Formula (Hook <=12 words / Dev pivots "
    "every 8-10s / Close = debate or DM-share or checklist — never generic). "
    "Return one improved concept (same id) as JSON only."
)

# Backward-compat aliases.
_DRAFT_ROLE = _DRAFT_ROLE_DEFAULT
_REVISE_ROLE = _REVISE_ROLE_DEFAULT


def draft(client, perf, brief, n=settings.N_CONCEPTS, extra_context=""):
    tmpl = prompt_store.get("prompt.copywriter.draft", _DRAFT_ROLE_DEFAULT)
    role = tmpl.format(brief=json.dumps(brief.to_dict(), indent=2), n=n)
    user = "Write the concepts now."
    if extra_context:
        user += f"\n{extra_context}"
    data = client.call("copywriter", shared_prefix(perf), role,
                       user, CONCEPTS_SCHEMA)
    return [Concept.from_dict(c) for c in data["concepts"]]


def revise(client, perf, brief, concept, feedback):
    tmpl = prompt_store.get("prompt.copywriter.revise", _REVISE_ROLE_DEFAULT)
    role = tmpl.format(
        brief=json.dumps(brief.to_dict(), indent=2),
        concept=json.dumps(concept.to_dict(), indent=2), feedback=feedback)
    data = client.call("copywriter", shared_prefix(perf), role,
                       "Revise the concept now.", CONCEPT_SCHEMA)
    return Concept.from_dict(data)
