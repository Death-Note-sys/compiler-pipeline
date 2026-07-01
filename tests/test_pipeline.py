"""
tests/test_pipeline.py
-----------------------
Tests that pipeline/stages.py's four stage functions return correctly typed
objects and flow end-to-end.

All tests in this file use static fixtures from conftest.py (JSON files on
disk) — zero LLM calls, runs in under a second.
"""

from __future__ import annotations

import copy

import pytest

from pipeline.stages import refine
from pipeline.results import SchemasResult, RefinementResult
from schemas.intent import IntentModel
from schemas.architecture import ArchitectureModel
from schemas.api import APISchema, APIField
from schemas.db import DBSchema
from schemas.auth import AuthSchema
from schemas.ui import UISchema


RAW_TEXT = "Build a CRM where admins can manage contacts (name, email, phone) and viewers can read them."

# ---------------------------------------------------------------------------
# Local fixtures: map crm_schemas tuple → named fixtures (zero LLM calls)
# ---------------------------------------------------------------------------

@pytest.fixture
def intent_result(crm_schemas) -> IntentModel:
    return crm_schemas[0]


@pytest.fixture
def arch_result(crm_schemas) -> ArchitectureModel:
    return crm_schemas[1]


@pytest.fixture
def schemas_tuple(crm_schemas) -> tuple[UISchema, APISchema, DBSchema, AuthSchema]:
    """(ui, api, db, auth) — matches crm_schemas index order."""
    return crm_schemas[2], crm_schemas[3], crm_schemas[4], crm_schemas[5]


@pytest.fixture
def schemas_result(crm_schemas) -> SchemasResult:
    """SchemasResult wrapping the static CRM schemas."""
    ui, api, db, auth = crm_schemas[2], crm_schemas[3], crm_schemas[4], crm_schemas[5]
    return SchemasResult(db=db, api=api, auth=auth, ui=ui)


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
# Stage 3 – generate_schemas (static)
# ---------------------------------------------------------------------------

class TestGenerateSchemas:
    def test_ui_is_correct_type(self, schemas_tuple):
        ui, api, db, auth = schemas_tuple
        assert isinstance(ui, UISchema)

    def test_api_is_correct_type(self, schemas_tuple):
        ui, api, db, auth = schemas_tuple
        assert isinstance(api, APISchema)

    def test_db_is_correct_type(self, schemas_tuple):
        ui, api, db, auth = schemas_tuple
        assert isinstance(db, DBSchema)

    def test_auth_is_correct_type(self, schemas_tuple):
        ui, api, db, auth = schemas_tuple
        assert isinstance(auth, AuthSchema)

    def test_schemas_have_content(self, schemas_tuple):
        ui, api, db, auth = schemas_tuple
        assert len(ui.pages) >= 1
        assert len(api.endpoints) >= 1
        assert len(db.tables) >= 1
        assert len(auth.roles) >= 1


# ---------------------------------------------------------------------------
# Stage 4 – refine (static, zero LLM calls)
# ---------------------------------------------------------------------------

class TestRefineStatic:
    def test_returns_refinement_result(self, schemas_result):
        """refine() must return a RefinementResult, not raise."""
        result = refine(schemas_result)
        assert isinstance(result, RefinementResult)

    def test_clean_schemas_have_is_clean_true(self, schemas_result):
        """The static CRM example schemas are internally consistent."""
        result = refine(schemas_result)
        assert result.is_clean is True

    def test_clean_schemas_have_empty_violations(self, schemas_result):
        result = refine(schemas_result)
        assert result.violations == []

    def test_clean_schemas_summary_is_clean(self, schemas_result):
        result = refine(schemas_result)
        assert result.summary == "Clean"

    def test_broken_schemas_return_is_clean_false(self, crm_schemas):
        """Removing a DB column that an API field references must trigger a violation."""
        ui, api, db, auth = crm_schemas[2], crm_schemas[3], crm_schemas[4], crm_schemas[5]

        # Deep-copy the DB and strip 'email' from the contacts table
        import copy as _copy
        db_data = db.model_dump(by_alias=True)
        db_data_copy = _copy.deepcopy(db_data)
        for table in db_data_copy["tables"]:
            table["columns"] = [c for c in table["columns"] if c["name"] != "email"]
        broken_db = DBSchema(**db_data_copy)

        broken = SchemasResult(db=broken_db, api=api, auth=auth, ui=ui)
        result = refine(broken)
        assert result.is_clean is False

    def test_broken_schemas_have_at_least_one_violation(self, crm_schemas):
        ui, api, db, auth = crm_schemas[2], crm_schemas[3], crm_schemas[4], crm_schemas[5]

        import copy as _copy
        db_data = _copy.deepcopy(db.model_dump(by_alias=True))
        for table in db_data["tables"]:
            table["columns"] = [c for c in table["columns"] if c["name"] != "email"]
        broken_db = DBSchema(**db_data)

        broken = SchemasResult(db=broken_db, api=api, auth=auth, ui=ui)
        result = refine(broken)
        assert len(result.violations) >= 1

    def test_violation_has_required_fields(self, crm_schemas):
        """Each violation must have layer, field, rule_violated, message."""
        ui, api, db, auth = crm_schemas[2], crm_schemas[3], crm_schemas[4], crm_schemas[5]

        import copy as _copy
        db_data = _copy.deepcopy(db.model_dump(by_alias=True))
        for table in db_data["tables"]:
            table["columns"] = [c for c in table["columns"] if c["name"] != "email"]
        broken_db = DBSchema(**db_data)

        broken = SchemasResult(db=broken_db, api=api, auth=auth, ui=ui)
        result = refine(broken)

        for v in result.violations:
            assert hasattr(v, "layer"), "violation missing .layer"
            assert hasattr(v, "field"), "violation missing .field"
            assert hasattr(v, "rule_violated"), "violation missing .rule_violated"
            assert hasattr(v, "message"), "violation missing .message"
            assert isinstance(v.layer, str) and v.layer
            assert isinstance(v.field, str) and v.field
            assert isinstance(v.rule_violated, str) and v.rule_violated
            assert isinstance(v.message, str) and v.message


# ---------------------------------------------------------------------------
# Legacy TestRefine — kept for backward compatibility with CI history
# ---------------------------------------------------------------------------

class TestRefine:
    def test_clean_schemas_pass_refine(self, schemas_result):
        result = refine(schemas_result)
        assert result.is_clean

    def test_full_pipeline_end_to_end(self, intent_result, arch_result, schemas_result):
        assert intent_result.entities
        assert arch_result.entities
        assert schemas_result.db.tables
        result = refine(schemas_result)
        assert isinstance(result, RefinementResult)

# ---------------------------------------------------------------------------
# Stage DDL - SQL Generation and Validation
# ---------------------------------------------------------------------------

from pipeline.ddl import generate_ddl, validate_ddl, DDLValidationResult
from schemas.db import DBSchema, DBTable, DBColumn, ColumnType

class TestDDLGeneration:
    def test_generate_ddl(self, schemas_result):
        ddl = generate_ddl(schemas_result.db)
        assert isinstance(ddl, str)
        assert "CREATE TABLE" in ddl
        assert "PRAGMA foreign_keys = ON;" in ddl

    def test_validate_ddl_success(self, schemas_result):
        ddl = generate_ddl(schemas_result.db)
        val = validate_ddl(ddl)
        assert val.success is True
        assert val.error is None
        assert val.table_count == len(schemas_result.db.tables)

    def test_validate_ddl_failure(self):
        bad_ddl = "CREATE TABLE foo (bar INT" # Syntax error
        val = validate_ddl(bad_ddl)
        assert val.success is False
        assert val.error is not None
        assert val.table_count == 0

    def test_table_ordering(self):
        # Table A references Table B
        # Expected order: Table B, then Table A
        col_b = DBColumn(name="id", type="uuid")
        table_b = DBTable(name="table_b", columns=[col_b])
        
        col_a = DBColumn(name="b_id", type="foreign_key", foreign_key="table_b.id")
        table_a = DBTable(name="table_a", columns=[col_a])
        
        # Pass them in wrong order
        db = DBSchema(tables=[table_a, table_b])
        ddl = generate_ddl(db)
        
        pos_b = ddl.find("CREATE TABLE table_b")
        pos_a = ddl.find("CREATE TABLE table_a")
        
        assert pos_b != -1
        assert pos_a != -1
        assert pos_b < pos_a # B must be created before A
