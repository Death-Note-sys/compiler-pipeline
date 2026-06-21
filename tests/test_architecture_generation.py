"""
tests/test_architecture_generation.py
--------------------------------------
Integration tests for pipeline/architecture.py (real Groq API calls).

Tests the full two-stage chain: extract_intent → design_architecture.
Skipped automatically when GROQ_API_KEY is not set.

Structural assertions only — no exact content checks (LLM output varies).
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

from schemas.architecture import ArchitectureModel, ArchEntity, ArchRole, EntityRelation, UserFlow
from schemas.intent import IntentModel
from pipeline.intent import extract_intent
from pipeline.architecture import design_architecture

# ---------------------------------------------------------------------------
# Reuse the same 3 prompts as test_intent_extraction.py
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

def _assert_arch_structure(arch: ArchitectureModel, description_id: str) -> None:
    """Assert structural invariants — no content checks."""
    assert isinstance(arch, ArchitectureModel), (
        f"[{description_id}] design_architecture must return ArchitectureModel"
    )

    # entities: at least 1, each with non-empty name and a list of attributes
    assert isinstance(arch.entities, list) and len(arch.entities) >= 1, (
        f"[{description_id}] must have at least 1 entity, got: {arch.entities}"
    )
    for ent in arch.entities:
        assert isinstance(ent, ArchEntity)
        assert isinstance(ent.name, str) and ent.name, "entity.name must be non-empty"
        assert isinstance(ent.attributes, list), "entity.attributes must be a list"

    # relations: may be empty, but if present must be valid EntityRelation objects
    assert isinstance(arch.relations, list), (
        f"[{description_id}] relations must be a list (may be empty)"
    )
    for rel in arch.relations:
        assert isinstance(rel, EntityRelation)
        assert rel.from_entity and rel.to_entity

    # roles: at least 1, each with a non-empty name
    assert isinstance(arch.roles, list) and len(arch.roles) >= 1, (
        f"[{description_id}] must have at least 1 role, got: {arch.roles}"
    )
    for role in arch.roles:
        assert isinstance(role, ArchRole)
        assert isinstance(role.name, str) and role.name, "role.name must be non-empty"

    # flows: may be empty, but if present must have name, actor, and steps
    assert isinstance(arch.flows, list), (
        f"[{description_id}] flows must be a list (may be empty)"
    )
    for flow in arch.flows:
        assert isinstance(flow, UserFlow)
        assert flow.name and flow.actor
        assert isinstance(flow.steps, list)


# ---------------------------------------------------------------------------
# Parametrised end-to-end chain tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("description_id,raw_text", APP_DESCRIPTIONS)
def test_two_stage_chain_returns_valid_architecture(description_id: str, raw_text: str):
    """
    Run the full extract_intent → design_architecture chain for each app
    description and assert the result is a structurally valid ArchitectureModel.
    """
    intent = extract_intent(raw_text)
    assert isinstance(intent, IntentModel), (
        f"[{description_id}] Stage 1 must return IntentModel"
    )

    arch = design_architecture(intent)
    _assert_arch_structure(arch, description_id)


@pytest.mark.parametrize("description_id,raw_text", APP_DESCRIPTIONS)
def test_arch_entity_names_are_pascal_case(description_id: str, raw_text: str):
    """Entity names must start with an uppercase letter (PascalCase convention)."""
    intent = extract_intent(raw_text)
    arch = design_architecture(intent)

    for ent in arch.entities:
        assert ent.name[0].isupper(), (
            f"[{description_id}] Entity name '{ent.name}' must start with uppercase (PascalCase)"
        )


@pytest.mark.parametrize("description_id,raw_text", APP_DESCRIPTIONS)
def test_arch_role_names_are_lowercase(description_id: str, raw_text: str):
    """Role names must be lowercase (contract from schema)."""
    intent = extract_intent(raw_text)
    arch = design_architecture(intent)

    for role in arch.roles:
        assert role.name == role.name.lower(), (
            f"[{description_id}] Role name '{role.name}' must be lowercase"
        )


@pytest.mark.parametrize("description_id,raw_text", APP_DESCRIPTIONS)
def test_arch_flow_actors_reference_defined_roles(description_id: str, raw_text: str):
    """Every flow's actor must match a defined role name."""
    intent = extract_intent(raw_text)
    arch = design_architecture(intent)

    role_names = {r.name for r in arch.roles}
    for flow in arch.flows:
        assert flow.actor in role_names, (
            f"[{description_id}] Flow '{flow.name}' actor '{flow.actor}' "
            f"not in defined roles {role_names}"
        )
