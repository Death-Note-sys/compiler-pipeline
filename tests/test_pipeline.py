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
from schemas.ui import UISchema
from schemas.api import APISchema
from schemas.db import DBSchema
from schemas.auth import AuthSchema


RAW_TEXT = "Build a CRM where admins can manage contacts and viewers can read them."


# ---------------------------------------------------------------------------
# Stage 1 – extract_intent
# ---------------------------------------------------------------------------

class TestExtractIntent:
    def test_returns_intent_model(self):
        result = extract_intent(RAW_TEXT)
        assert isinstance(result, IntentModel)

    def test_raw_text_preserved(self):
        result = extract_intent(RAW_TEXT)
        assert result.raw_text == RAW_TEXT

    def test_has_entities(self):
        result = extract_intent(RAW_TEXT)
        assert len(result.entities) >= 1

    def test_has_roles(self):
        result = extract_intent(RAW_TEXT)
        assert len(result.roles) >= 1

    def test_has_features(self):
        result = extract_intent(RAW_TEXT)
        assert len(result.features) >= 1


# ---------------------------------------------------------------------------
# Stage 2 – design_architecture
# ---------------------------------------------------------------------------

class TestDesignArchitecture:
    def test_returns_architecture_model(self):
        intent = extract_intent(RAW_TEXT)
        result = design_architecture(intent)
        assert isinstance(result, ArchitectureModel)

    def test_has_entities_and_roles(self):
        intent = extract_intent(RAW_TEXT)
        arch = design_architecture(intent)
        assert len(arch.entities) >= 1
        assert len(arch.roles) >= 1

    def test_has_flows(self):
        intent = extract_intent(RAW_TEXT)
        arch = design_architecture(intent)
        assert len(arch.flows) >= 1


# ---------------------------------------------------------------------------
# Stage 3 – generate_schemas
# ---------------------------------------------------------------------------

class TestGenerateSchemas:
    def _run(self):
        intent = extract_intent(RAW_TEXT)
        arch = design_architecture(intent)
        return generate_schemas(arch)

    def test_returns_four_schemas(self):
        result = self._run()
        assert len(result) == 4

    def test_ui_is_correct_type(self):
        ui, api, db, auth = self._run()
        assert isinstance(ui, UISchema)

    def test_api_is_correct_type(self):
        ui, api, db, auth = self._run()
        assert isinstance(api, APISchema)

    def test_db_is_correct_type(self):
        ui, api, db, auth = self._run()
        assert isinstance(db, DBSchema)

    def test_auth_is_correct_type(self):
        ui, api, db, auth = self._run()
        assert isinstance(auth, AuthSchema)

    def test_schemas_have_content(self):
        ui, api, db, auth = self._run()
        assert len(ui.pages) >= 1
        assert len(api.endpoints) >= 1
        assert len(db.tables) >= 1
        assert len(auth.roles) >= 1


# ---------------------------------------------------------------------------
# Stage 4 – refine (end-to-end)
# ---------------------------------------------------------------------------

class TestRefine:
    def test_clean_schemas_pass_refine(self):
        """The placeholder schemas must pass all consistency checks."""
        intent = extract_intent(RAW_TEXT)
        arch = design_architecture(intent)
        ui, api, db, auth = generate_schemas(arch)
        # refine raises if any consistency errors are found
        result_ui, result_api, result_db, result_auth = refine(ui, api, db, auth)
        # Returned objects must be the correct types
        assert isinstance(result_ui, UISchema)
        assert isinstance(result_api, APISchema)
        assert isinstance(result_db, DBSchema)
        assert isinstance(result_auth, AuthSchema)

    def test_full_pipeline_end_to_end(self):
        """Run all four stages in sequence and confirm no exception is raised."""
        intent = extract_intent(RAW_TEXT)
        arch = design_architecture(intent)
        ui, api, db, auth = generate_schemas(arch)
        refine(ui, api, db, auth)   # must not raise
