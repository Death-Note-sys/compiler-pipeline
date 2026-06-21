"""
tests/test_intent_extraction.py
-------------------------------
Integration tests for pipeline/intent.py (real Groq API calls).

Skipped automatically when GROQ_API_KEY is not set so the full suite
remains green on machines without a key (CI without secrets, etc.).

These tests assert STRUCTURE and TYPES only — never exact content,
because LLM output is non-deterministic.
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Guard: skip entire module if the API key is absent
# ---------------------------------------------------------------------------

GROQ_API_KEY_PRESENT = bool(os.environ.get("GROQ_API_KEY"))

pytestmark = pytest.mark.skipif(
    not GROQ_API_KEY_PRESENT,
    reason="GROQ_API_KEY not set — skipping live Groq integration tests",
)

# ---------------------------------------------------------------------------
# Imports (deferred so missing groq doesn't break the collection phase)
# ---------------------------------------------------------------------------

from schemas.intent import IntentModel, EntityMention, RoleMention  # noqa: E402
from pipeline.intent import extract_intent  # noqa: E402


# ---------------------------------------------------------------------------
# Test fixtures: varied app descriptions
# ---------------------------------------------------------------------------

APP_DESCRIPTIONS = [
    (
        "crm",
        "Build a CRM where admins can manage contacts (name, email, phone, company) "
        "and sales reps can view and update their assigned contacts. Include activity logging.",
    ),
    (
        "todo",
        "A simple personal todo list app. Users can create tasks with titles, "
        "due dates, and priority levels. Tasks can be marked complete or deleted.",
    ),
    (
        "ecommerce",
        "An e-commerce platform where customers can browse products, add items to a cart, "
        "and checkout. Admins manage inventory and view orders. Support discount codes.",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_intent_structure(intent: IntentModel, description_id: str) -> None:
    """Assert structural invariants on an IntentModel — no content checks."""
    assert isinstance(intent, IntentModel), (
        f"[{description_id}] extract_intent must return IntentModel, got {type(intent)}"
    )
    assert isinstance(intent.raw_text, str) and intent.raw_text, (
        f"[{description_id}] raw_text must be a non-empty string"
    )
    assert isinstance(intent.entities, list), (
        f"[{description_id}] entities must be a list"
    )
    assert len(intent.entities) >= 1, (
        f"[{description_id}] must extract at least one entity, got: {intent.entities}"
    )
    for ent in intent.entities:
        assert isinstance(ent, EntityMention)
        assert isinstance(ent.name, str) and ent.name, "entity.name must be non-empty"
        assert isinstance(ent.attributes, list), "entity.attributes must be a list"

    assert isinstance(intent.roles, list), (
        f"[{description_id}] roles must be a list"
    )
    assert len(intent.roles) >= 1, (
        f"[{description_id}] must extract at least one role, got: {intent.roles}"
    )
    for role in intent.roles:
        assert isinstance(role, RoleMention)
        assert isinstance(role.name, str) and role.name, "role.name must be non-empty"

    assert isinstance(intent.features, list), (
        f"[{description_id}] features must be a list"
    )
    assert len(intent.features) >= 1, (
        f"[{description_id}] must extract at least one feature, got: {intent.features}"
    )
    for f in intent.features:
        assert isinstance(f, str) and f, "each feature must be a non-empty string"

    assert isinstance(intent.ambiguities, list), (
        f"[{description_id}] ambiguities must be a list (may be empty)"
    )


# ---------------------------------------------------------------------------
# Parametrised integration test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("description_id,raw_text", APP_DESCRIPTIONS)
def test_extract_intent_returns_valid_structure(description_id: str, raw_text: str):
    """
    Call extract_intent with a real app description and assert the result
    is a valid, structurally correct IntentModel.

    No content assertions — LLM output is non-deterministic.
    """
    intent = extract_intent(raw_text)
    _assert_intent_structure(intent, description_id)


# ---------------------------------------------------------------------------
# Raw_text preservation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("description_id,raw_text", APP_DESCRIPTIONS)
def test_raw_text_is_preserved(description_id: str, raw_text: str):
    """The raw_text field must exactly match the input."""
    intent = extract_intent(raw_text)
    assert intent.raw_text == raw_text, (
        f"[{description_id}] raw_text was mutated by the model. "
        f"Expected:\n  {raw_text!r}\nGot:\n  {intent.raw_text!r}"
    )
