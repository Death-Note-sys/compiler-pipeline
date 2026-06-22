"""
tests/test_pipeline.py
-----------------------
Tests that pipeline/stages.py's four stage functions return objects
that validate against the Pydantic schemas and flow correctly end-to-end.

Stage 1 (extract_intent) now makes real Groq API calls, so these tests are
skipped automatically when GROQ_API_KEY is not set.
"""

from __future__ import annotations

import os

import pytest

GROQ_API_KEY_PRESENT = bool(os.environ.get("GROQ_API_KEY"))

pytestmark = pytest.mark.skipif(
    not GROQ_API_KEY_PRESENT,
    reason="GROQ_API_KEY not set — skipping pipeline integration tests",
)

from pipeline.stages import extract_intent, design_architecture, generate_schemas, refine
from schemas.intent import IntentModel
from schemas.architecture import ArchitectureModel
from schemas.api import APISchema
from schemas.db import DBSchema
from schemas.auth import AuthSchema
from schemas.ui import UISchema

from pipeline.stages import (
    extract_intent,
    design_architecture,
    generate_schemas,
    refine,
)


GROQ_API_KEY_PRESENT = bool(os.environ.get("GROQ_API_KEY"))
pytestmark = pytest.mark.skipif(
    not GROQ_API_KEY_PRESENT,
    reason="GROQ_API_KEY not set — skipping live Groq integration tests",
)

RAW_TEXT = (
    "Build a CRM where admins can manage contacts (name, email, phone, company) "
    "and sales reps can view and update their assigned contacts. Include activity logging."
)

# ---------------------------------------------------------------------------
# Module-scoped fixtures to avoid redundant Groq API calls
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def intent_result() -> IntentModel:
    return extract_intent(RAW_TEXT)


@pytest.fixture(scope="module")
def arch_result(intent_result) -> ArchitectureModel:
    return design_architecture(intent_result)


@pytest.fixture(scope="module")
def schemas_result_tuple(arch_result) -> tuple[UISchema, APISchema, DBSchema, AuthSchema]:
    return generate_schemas(arch_result)


# ---------------------------------------------------------------------------
# Stage 1 – extract_intent
# ---------------------------------------------------------------------------

class TestExtractIntent:
    def test_returns_intent_model(self, intent_result):
        assert isinstance(intent_result, IntentModel)

    def test_raw_text_preserved(self, intent_result):
        assert intent_result.raw_text == RAW_TEXT

    def test_has_entities(self, intent_result):
        assert len(intent_result.entities) >= 1

    def test_has_roles(self, intent_result):
        assert len(intent_result.roles) >= 1

    def test_has_features(self, intent_result):
        assert len(intent_result.features) >= 1


# ---------------------------------------------------------------------------
# Stage 2 – design_architecture
# ---------------------------------------------------------------------------

class TestDesignArchitecture:
    def test_returns_architecture_model(self, arch_result):
        assert isinstance(arch_result, ArchitectureModel)

    def test_has_entities_and_roles(self, arch_result):
        assert len(arch_result.entities) >= 1
        assert len(arch_result.roles) >= 1

    def test_has_flows(self, arch_result):
        assert len(arch_result.flows) >= 1


# ---------------------------------------------------------------------------
# Stage 3 – generate_schemas
# ---------------------------------------------------------------------------

class TestGenerateSchemas:
    def test_returns_four_schemas(self, schemas_result_tuple):
        assert len(schemas_result_tuple) == 4

    def test_ui_is_correct_type(self, schemas_result_tuple):
        ui, api, db, auth = schemas_result_tuple
        assert isinstance(ui, UISchema)

    def test_api_is_correct_type(self, schemas_result_tuple):
        ui, api, db, auth = schemas_result_tuple
        assert isinstance(api, APISchema)

    def test_db_is_correct_type(self, schemas_result_tuple):
        ui, api, db, auth = schemas_result_tuple
        assert isinstance(db, DBSchema)

    def test_auth_is_correct_type(self, schemas_result_tuple):
        ui, api, db, auth = schemas_result_tuple
        assert isinstance(auth, AuthSchema)

    def test_schemas_have_content(self, schemas_result_tuple):
        ui, api, db, auth = schemas_result_tuple
        assert len(ui.pages) >= 1
        assert len(api.endpoints) >= 1
        assert len(db.tables) >= 1
        assert len(auth.roles) >= 1


# ---------------------------------------------------------------------------
# Stage 4 – refine (end-to-end)
# ---------------------------------------------------------------------------

class TestRefine:
    def test_clean_schemas_pass_refine(self, schemas_result_tuple):
        """The schemas must pass all consistency checks."""
        ui, api, db, auth = schemas_result_tuple
        # refine raises if any consistency errors are found
        result_ui, result_api, result_db, result_auth = refine(ui, api, db, auth)
        assert isinstance(result_ui, UISchema)
        assert isinstance(result_api, APISchema)
        assert isinstance(result_db, DBSchema)
        assert isinstance(result_auth, AuthSchema)

    def test_full_pipeline_end_to_end(self, intent_result, arch_result, schemas_result_tuple):
        """Spot check the overall end-to-end chain."""
        ui, api, db, auth = schemas_result_tuple
        
        # Intent has entities, Architecture has tables, DB has tables
        assert intent_result.entities
        assert arch_result.entities
        assert db.tables
        refine(ui, api, db, auth)   # must not raise
