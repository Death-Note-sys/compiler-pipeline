"""
pipeline/intent.py
------------------
Stage 1 – Intent Extraction (real Groq implementation).

Public API
----------
``extract_intent(raw_text: str) -> IntentModel``
    Calls Groq with a structured extraction prompt, validates the response
    against ``IntentModel``, and performs exactly one repair attempt if the
    first response fails validation.  If the repair also fails, raises
    ``PipelineStageError`` with the original ``ValidationError`` attached.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import ValidationError

from llm.groq_client import chat_json
from pipeline.errors import PipelineStageError
from schemas.intent import Ambiguity, EntityMention, IntentModel, RoleMention

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

_MODEL = "llama-3.1-8b-instant"
_TEMPERATURE = 0.0

# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert software requirements analyst.

Your job is to extract structured information from a natural-language app
description and return ONLY a single JSON object — no markdown, no code
fences, no extra keys.

The JSON object must have exactly these top-level keys:

{
  "raw_text": "<copy the user's input verbatim>",
  "entities": [
    {
      "name": "<PascalCase entity name, e.g. User, Invoice, Product>",
      "attributes": ["<snake_case attribute>", ...]
    }
  ],
  "roles": [
    { "name": "<lowercase role name, e.g. admin, viewer, customer>" }
  ],
  "features": ["<short feature label, e.g. auth, crud, dashboard, search, payments, notifications>"],
  "ambiguities": [
    {
      "field": "<the ambiguous concept or field name>",
      "message": "<one sentence describing what is unclear>"
    }
  ]
}

Rules:
- Extract ALL entities mentioned or strongly implied (e.g. User is always implied if auth is present).
- Extract ALL user roles (who can do what).
- List feature labels as short lowercase strings relevant to what the app does.
- List anything genuinely ambiguous that a developer would need to clarify.
- If there are no ambiguities, return an empty list for "ambiguities".
- Return ONLY the JSON object. Do not wrap it in markdown or add any explanation.
"""


def _build_messages(raw_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ]


def _build_repair_messages(
    raw_text: str,
    bad_output: str,
    validation_error: ValidationError,
) -> list[dict[str, str]]:
    """Build a repair prompt that includes the bad output and the exact Pydantic error."""
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
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
        {"role": "assistant", "content": bad_output},
        {"role": "user", "content": repair_instruction},
    ]


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def _parse_and_validate(raw_json: str) -> IntentModel:
    """
    Parse ``raw_json`` as JSON, then validate against ``IntentModel``.

    Raises
    ------
    json.JSONDecodeError
        If the response is not valid JSON.
    pydantic.ValidationError
        If the JSON doesn't match IntentModel's schema.
    """
    data: Any = json.loads(raw_json)
    return IntentModel.model_validate(data)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def extract_intent(raw_text: str) -> IntentModel:
    """
    Call Groq to extract intent from ``raw_text`` and return a validated
    ``IntentModel``.

    Behaviour
    ---------
    1. Send extraction prompt → parse + validate response.
    2. If validation fails, make ONE repair attempt with the error attached.
    3. If the repair also fails, raise ``PipelineStageError``.

    Logs (at INFO level):
    - Model and temperature used.
    - Call latency (handled inside ``chat_json``).
    - Whether a repair attempt was needed.
    """
    logger.info(
        "extract_intent | model=%s temperature=%s | text_length=%d chars",
        _MODEL,
        _TEMPERATURE,
        len(raw_text),
    )

    messages = _build_messages(raw_text)

    # ── First attempt ────────────────────────────────────────────────────────
    raw_response = chat_json(messages, model=_MODEL, temperature=_TEMPERATURE)

    try:
        intent = _parse_and_validate(raw_response)
        logger.info("extract_intent | first attempt succeeded | repair_needed=False")
        return intent

    except (json.JSONDecodeError, ValidationError) as first_error:
        logger.warning(
            "extract_intent | first attempt failed (%s: %s) — attempting repair",
            type(first_error).__name__,
            str(first_error)[:200],
        )

    # ── Repair attempt ───────────────────────────────────────────────────────
    if isinstance(first_error, ValidationError):
        repair_messages = _build_repair_messages(raw_text, raw_response, first_error)
    else:
        # JSON decode error: just retry with the original prompt
        repair_messages = messages

    repair_response = chat_json(repair_messages, model=_MODEL, temperature=_TEMPERATURE)
    logger.info("extract_intent | repair_needed=True")

    try:
        intent = _parse_and_validate(repair_response)
        logger.info("extract_intent | repair attempt succeeded")
        return intent

    except (json.JSONDecodeError, ValidationError) as repair_error:
        raise PipelineStageError(
            stage="extract_intent",
            detail=(
                f"Groq response failed validation after one repair attempt. "
                f"Final error: {repair_error}"
            ),
            cause=repair_error,
        ) from repair_error
