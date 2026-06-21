"""
pipeline/architecture.py
------------------------
Stage 2 – System Design (real Groq implementation).

Public API
----------
``design_architecture(intent: IntentModel) -> ArchitectureModel``
    Receives a validated IntentModel (the real output of extract_intent),
    calls Groq with a structured system-design prompt, validates the response
    against ArchitectureModel, and performs exactly one repair attempt if
    validation fails.  If the repair also fails, raises PipelineStageError.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from llm.groq_client import chat_json
from pipeline.errors import PipelineStageError
from schemas.architecture import ArchitectureModel
from schemas.intent import IntentModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

_MODEL = "llama-3.3-70b-versatile"
_TEMPERATURE = 0.0

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert software architect.

You will receive a structured JSON object describing a user's app intent
(entities, roles, features, ambiguities).  Your job is to convert it into
a coherent system architecture and return ONLY a single JSON object — no
markdown, no code fences, no extra keys.

The JSON object must have exactly these top-level keys:

{
  "entities": [
    {
      "name": "<Singular PascalCase entity name, e.g. User, Invoice, Product>",
      "attributes": ["<snake_case attribute names this entity owns>"]
    }
  ],
  "relations": [
    {
      "from_entity": "<PascalCase source entity name>",
      "to_entity":   "<PascalCase target entity name>",
      "relation_type": "<one of: one_to_one | one_to_many | many_to_many>"
    }
  ],
  "roles": [
    {
      "name": "<lowercase role name, e.g. admin, viewer, customer>",
      "description": "<one sentence: what this role can do in the system>"
    }
  ],
  "flows": [
    {
      "name": "<short camelCase identifier, e.g. createContact, viewDashboard>",
      "actor": "<role name that initiates this flow>",
      "steps": ["<ordered, human-readable description of each step>"]
    }
  ]
}

Rules:
- Include every entity from the intent, plus any strongly implied supporting
  entities (e.g. if auth is a feature, include a User entity if not already present).
- Always include a standard "id" attribute and timestamps ("created_at") on each entity.
- Model every meaningful relationship between entities as an EntityRelation.
- Define one UserFlow per major action each role can perform.
- relation_type MUST be one of the three allowed values: one_to_one, one_to_many, many_to_many.
- Return ONLY the JSON object. Do not wrap it in markdown or add any explanation.
"""


def _build_messages(intent: IntentModel) -> list[dict[str, str]]:
    intent_json = json.dumps(intent.model_dump(), indent=2)
    user_content = (
        "Here is the extracted app intent. "
        "Design the system architecture for it:\n\n"
        f"{intent_json}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _build_repair_messages(
    intent: IntentModel,
    bad_output: str,
    validation_error: ValidationError,
) -> list[dict[str, str]]:
    """Repair prompt: original intent + bad output + exact Pydantic error."""
    error_summary = validation_error.json(indent=2)
    repair_instruction = (
        "The JSON you returned failed Pydantic validation. "
        "Here is the exact error:\n\n"
        f"{error_summary}\n\n"
        "Here is the JSON you returned:\n\n"
        f"{bad_output}\n\n"
        "Return a corrected JSON object that satisfies the schema. "
        "Return ONLY the corrected JSON object — no markdown, no explanation."
    )
    base_messages = _build_messages(intent)
    return base_messages + [
        {"role": "assistant", "content": bad_output},
        {"role": "user", "content": repair_instruction},
    ]


# ---------------------------------------------------------------------------
# Relation normalization (pure, deterministic, no LLM call)
# ---------------------------------------------------------------------------
#
# Models occasionally use valid-but-non-canonical synonyms for relation types.
# Normalizing these before Pydantic validation prevents wasting a repair call
# on a deterministic, code-fixable deviation.
#
# Design: normalize_relation() is a standalone, independently-testable function
# (not inline logic) so it is easy to extend with new rules as they are
# discovered.  Normalization events are logged distinctly from repair events
# because they are different categories of self-correction:
#   "normalized" = free, deterministic, code-only correction
#   "repair"     = costly, non-deterministic LLM re-prompt

# Maps a non-canonical relation_type to the canonical form.  When the type is
# an inverted synonym (e.g. many_to_one ≡ one_to_many read backwards) the
# from_entity / to_entity fields must also be swapped to preserve meaning.
_INVERTED_ALIASES: frozenset[str] = frozenset({"many_to_one"})
_CANONICAL_MAP: dict[str, str] = {
    "many_to_one": "one_to_many",
}


def normalize_relation(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a single raw relation dict before Pydantic validation.

    If ``relation_type`` is a non-canonical synonym:
    - Replace it with the canonical value.
    - If it is an inverted synonym (e.g. ``many_to_one``), swap
      ``from_entity`` and ``to_entity`` so the real-world meaning is
      preserved rather than inverted.

    Parameters
    ----------
    raw : dict
        A raw relation dict as parsed from the model JSON response.

    Returns
    -------
    dict
        The (possibly mutated) relation dict with canonical values.
    """
    rt = raw.get("relation_type")
    if not isinstance(rt, str) or rt not in _CANONICAL_MAP:
        return raw

    canonical = _CANONICAL_MAP[rt]
    result = dict(raw)          # shallow copy — don't mutate caller's data
    result["relation_type"] = canonical

    if rt in _INVERTED_ALIASES:
        # Swap entity references so the direction stays correct.
        result["from_entity"], result["to_entity"] = (
            raw.get("to_entity"),
            raw.get("from_entity"),
        )
        logger.info(
            "normalized | relation_type %r -> %r, swapped from_entity=%r to_entity=%r",
            rt, canonical,
            result["from_entity"], result["to_entity"],
        )
    else:
        logger.info(
            "normalized | relation_type %r -> %r (no entity swap needed)",
            rt, canonical,
        )

    return result


def _normalize_relations_list(data: dict[str, Any]) -> dict[str, Any]:
    """Apply normalize_relation() to every relation in the parsed response."""
    relations = data.get("relations")
    if not isinstance(relations, list):
        return data
    data["relations"] = [
        normalize_relation(rel) if isinstance(rel, dict) else rel
        for rel in relations
    ]
    return data


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def _parse_and_validate(raw_json: str) -> ArchitectureModel:
    """Parse raw JSON, apply deterministic normalization, then validate."""
    data: Any = json.loads(raw_json)
    if isinstance(data, dict):
        data = _normalize_relations_list(data)
    return ArchitectureModel.model_validate(data)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def design_architecture(intent: IntentModel) -> ArchitectureModel:
    """
    Call Groq to convert an IntentModel into a validated ArchitectureModel.

    Behaviour
    ---------
    1. Serialise the intent as JSON → send to Groq → parse + validate.
    2. If validation fails, make ONE repair attempt with the exact error.
    3. If the repair also fails, raise PipelineStageError.

    Logs (at INFO level):
    - Model, temperature, and intent entity count.
    - Call latency (handled inside chat_json).
    - Whether a repair attempt was needed.
    """
    logger.info(
        "design_architecture | model=%s temperature=%s | entities=%d roles=%d",
        _MODEL,
        _TEMPERATURE,
        len(intent.entities),
        len(intent.roles),
    )

    messages = _build_messages(intent)

    # ── First attempt ────────────────────────────────────────────────────────
    raw_response = chat_json(messages, model=_MODEL, temperature=_TEMPERATURE)

    first_error: json.JSONDecodeError | ValidationError | None = None
    try:
        arch = _parse_and_validate(raw_response)
        logger.info("design_architecture | first attempt succeeded | repair_needed=False")
        return arch

    except (json.JSONDecodeError, ValidationError) as exc:
        first_error = exc          # capture before Python deletes the as-binding
        logger.warning(
            "design_architecture | first attempt failed (%s: %s) — attempting repair",
            type(exc).__name__,
            str(exc)[:200],
        )

    # ── Repair attempt ───────────────────────────────────────────────────────
    assert first_error is not None  # always true here; satisfies type checkers
    if isinstance(first_error, ValidationError):
        repair_messages = _build_repair_messages(intent, raw_response, first_error)
    else:
        repair_messages = _build_messages(intent)   # JSON decode: retry fresh

    repair_response = chat_json(repair_messages, model=_MODEL, temperature=_TEMPERATURE)
    logger.info("design_architecture | repair_needed=True")

    try:
        arch = _parse_and_validate(repair_response)
        logger.info("design_architecture | repair attempt succeeded")
        return arch

    except (json.JSONDecodeError, ValidationError) as repair_error:
        raise PipelineStageError(
            stage="design_architecture",
            detail=(
                "Groq response failed validation after one repair attempt. "
                f"Final error: {repair_error}"
            ),
            cause=repair_error,
        ) from repair_error
