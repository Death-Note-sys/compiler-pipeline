"""
tests/test_schema_generation.py
-------------------------------
Integration tests for pipeline/schema_gen.py (real Groq API calls).

Tests the full three-stage chain:
  extract_intent → design_architecture → generate_schemas

Skipped automatically when GROQ_API_KEY is not set.
Structural assertions only — no exact content checks (LLM output varies).

EFFICIENCY: Each prompt runs the chain only once via session-scoped fixtures
(caches SchemasResult per prompt), keeping Groq token consumption minimal.
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

from schemas.db import DBSchema
from schemas.api import APISchema
from schemas.auth import AuthSchema
from schemas.ui import UISchema

from pipeline.intent import extract_intent
from pipeline.architecture import design_architecture
from pipeline.schema_gen import generate_schemas, SchemasResult


# ---------------------------------------------------------------------------
# Session-scoped fixtures — each prompt runs the chain only ONCE
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def crm_schemas_result() -> SchemasResult:
    raw = (
        "Build a CRM where admins can manage contacts (name, email, phone, company) "
        "and sales reps can view and update their assigned contacts. Include activity logging."
    )
    intent = extract_intent(raw)
    arch = design_architecture(intent)
    return generate_schemas(arch)


@pytest.fixture(scope="session")
def todo_schemas_result() -> SchemasResult:
    raw = (
        "A simple personal todo list app. Users can create tasks with titles, "
        "due dates, and priority levels. Tasks can be marked complete or deleted."
    )
    intent = extract_intent(raw)
    arch = design_architecture(intent)
    return generate_schemas(arch)


@pytest.fixture(scope="session")
def ecommerce_schemas_result() -> SchemasResult:
    raw = (
        "An e-commerce platform where customers can browse products, add items to a cart, "
        "and checkout. Admins manage inventory and view orders. Support discount codes."
    )
    intent = extract_intent(raw)
    arch = design_architecture(intent)
    return generate_schemas(arch)


ALL_RESULTS = ["crm_schemas_result", "todo_schemas_result", "ecommerce_schemas_result"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_all_api_field_names(api: APISchema) -> set[str]:
    """Collect all field names across all endpoints (request + response)."""
    names: set[str] = set()
    for ep in api.endpoints:
        for f in ep.request_fields:
            names.add(f.name)
        for f in ep.response_fields:
            names.add(f.name)
    return names


def _collect_all_db_column_names(db: DBSchema) -> set[str]:
    """Collect all column names across all tables."""
    names: set[str] = set()
    for table in db.tables:
        for col in table.columns:
            names.add(col.name)
    return names


# ---------------------------------------------------------------------------
# DB Schema assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_db_has_at_least_2_tables(fixture_name: str, request):
    result: SchemasResult = request.getfixturevalue(fixture_name)
    assert isinstance(result.db, DBSchema)
    assert len(result.db.tables) >= 2, (
        f"[{fixture_name}] Expected >= 2 tables, got {len(result.db.tables)}"
    )


@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_db_tables_have_columns(fixture_name: str, request):
    result: SchemasResult = request.getfixturevalue(fixture_name)
    for table in result.db.tables:
        assert len(table.columns) >= 1, (
            f"[{fixture_name}] Table '{table.name}' has no columns"
        )


# ---------------------------------------------------------------------------
# API Schema assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_api_has_at_least_3_endpoints(fixture_name: str, request):
    result: SchemasResult = request.getfixturevalue(fixture_name)
    assert isinstance(result.api, APISchema)
    assert len(result.api.endpoints) >= 3, (
        f"[{fixture_name}] Expected >= 3 endpoints, got {len(result.api.endpoints)}"
    )


@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_api_endpoints_have_valid_gates(fixture_name: str, request):
    result: SchemasResult = request.getfixturevalue(fixture_name)
    for ep in result.api.endpoints:
        assert ep.gate is not None, (
            f"[{fixture_name}] Endpoint {ep.method.value} {ep.path} has no gate"
        )
        assert ep.gate.kind is not None, (
            f"[{fixture_name}] Endpoint {ep.method.value} {ep.path} gate.kind is None"
        )


# ---------------------------------------------------------------------------
# Auth Schema assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_auth_has_at_least_1_role(fixture_name: str, request):
    result: SchemasResult = request.getfixturevalue(fixture_name)
    assert isinstance(result.auth, AuthSchema)
    assert len(result.auth.roles) >= 1, (
        f"[{fixture_name}] Expected >= 1 role, got {len(result.auth.roles)}"
    )


@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_auth_permission_matrix_non_empty(fixture_name: str, request):
    result: SchemasResult = request.getfixturevalue(fixture_name)
    assert len(result.auth.permission_matrix) >= 1, (
        f"[{fixture_name}] permission_matrix is empty"
    )


# ---------------------------------------------------------------------------
# UI Schema assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_ui_has_at_least_2_pages(fixture_name: str, request):
    result: SchemasResult = request.getfixturevalue(fixture_name)
    assert isinstance(result.ui, UISchema)
    assert len(result.ui.pages) >= 2, (
        f"[{fixture_name}] Expected >= 2 pages, got {len(result.ui.pages)}"
    )


@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_ui_pages_have_components(fixture_name: str, request):
    result: SchemasResult = request.getfixturevalue(fixture_name)
    for page in result.ui.pages:
        assert len(page.components) >= 1, (
            f"[{fixture_name}] Page '{page.name}' has no components"
        )


# ---------------------------------------------------------------------------
# Cross-reference spot check: API ↔ DB column overlap
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", ALL_RESULTS)
def test_api_fields_overlap_with_db_columns(fixture_name: str, request):
    """
    At least one API endpoint field name must match at least one DB column
    name.  This proves the sequential context passing worked (API generation
    saw the DB schema), not just 4 independent generations.
    """
    result: SchemasResult = request.getfixturevalue(fixture_name)
    api_names = _collect_all_api_field_names(result.api)
    db_names = _collect_all_db_column_names(result.db)
    overlap = api_names & db_names

    assert len(overlap) >= 1, (
        f"[{fixture_name}] No overlap between API field names and DB column names.\n"
        f"  API fields: {sorted(api_names)}\n"
        f"  DB columns: {sorted(db_names)}"
    )
