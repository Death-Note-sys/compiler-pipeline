"""
tests/test_schemas.py
---------------------
Validate that both JSON examples parse cleanly through all six Pydantic
schema models without raising ValidationError.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.intent import IntentModel
from schemas.architecture import ArchitectureModel
from schemas.ui import UISchema
from schemas.api import APISchema
from schemas.db import DBSchema
from schemas.auth import AuthSchema


# ---------------------------------------------------------------------------
# CRM example – all 6 layers
# ---------------------------------------------------------------------------

class TestCRMSchemas:
    def test_intent_parses(self, crm_data):
        m = IntentModel(**crm_data["intent"])
        assert m.raw_text
        assert any(e.name == "Contact" for e in m.entities)

    def test_architecture_parses(self, crm_data):
        m = ArchitectureModel(**crm_data["architecture"])
        assert any(e.name == "Contact" for e in m.entities)
        assert {r.name for r in m.roles} == {"admin", "viewer"}

    def test_ui_parses(self, crm_data):
        m = UISchema(**crm_data["ui"])
        page_names = {p.name for p in m.pages}
        assert "ContactList" in page_names
        assert "ContactForm" in page_names

    def test_api_parses(self, crm_data):
        m = APISchema(**crm_data["api"])
        methods = {ep.method.value for ep in m.endpoints}
        assert "GET" in methods
        assert "POST" in methods

    def test_db_parses(self, crm_data):
        m = DBSchema(**crm_data["db"])
        tables = {t.name for t in m.tables}
        assert "contacts" in tables

    def test_auth_parses(self, crm_data):
        m = AuthSchema(**crm_data["auth"])
        role_names = {r.name for r in m.roles}
        assert role_names == {"admin", "viewer"}


# ---------------------------------------------------------------------------
# Todo example – all 6 layers
# ---------------------------------------------------------------------------

class TestTodoSchemas:
    def test_intent_parses(self, todo_data):
        m = IntentModel(**todo_data["intent"])
        assert m.raw_text
        assert any(e.name == "Task" for e in m.entities)
        assert len(m.ambiguities) >= 1

    def test_architecture_parses(self, todo_data):
        m = ArchitectureModel(**todo_data["architecture"])
        assert any(e.name == "Task" for e in m.entities)
        assert any(r.name == "user" for r in m.roles)

    def test_ui_parses(self, todo_data):
        m = UISchema(**todo_data["ui"])
        page_names = {p.name for p in m.pages}
        assert "TaskList" in page_names
        assert "TaskForm" in page_names

    def test_api_parses(self, todo_data):
        m = APISchema(**todo_data["api"])
        patterns = {ep.pattern.value for ep in m.endpoints}
        assert "crud_list" in patterns
        assert "crud_create" in patterns
        assert "crud_update" in patterns   # uses PUT per contract (not PATCH)
        assert "crud_delete" in patterns

    def test_db_parses(self, todo_data):
        m = DBSchema(**todo_data["db"])
        col_names = {col.name for col in m.tables[0].columns}
        assert {"id", "title", "completed", "due_date", "created_at", "owner_id"} == col_names

    def test_auth_parses(self, todo_data):
        m = AuthSchema(**todo_data["auth"])
        assert any(r.name == "user" for r in m.roles)


# ---------------------------------------------------------------------------
# Enum guard – reject unknown types at parse time
# ---------------------------------------------------------------------------

class TestEnumRejection:
    def test_invalid_page_type_rejected(self, crm_data):
        """A page_type not in the closed vocabulary must raise ValidationError."""
        import copy
        bad = copy.deepcopy(crm_data)
        bad["ui"]["pages"][0]["page_type"] = "wizard"   # not in PageType enum
        with pytest.raises(ValidationError):
            UISchema(**bad["ui"])

    def test_invalid_api_method_rejected(self, crm_data):
        """An HTTP method outside the closed enum must raise ValidationError."""
        import copy
        bad = copy.deepcopy(crm_data)
        bad["api"]["endpoints"][0]["method"] = "CONNECT"
        with pytest.raises(ValidationError):
            APISchema(**bad["api"])

    def test_invalid_col_type_rejected(self, crm_data):
        """A DB column type not in ColumnType must raise ValidationError."""
        import copy
        bad = copy.deepcopy(crm_data)
        bad["db"]["tables"][0]["columns"][0]["type"] = "blob"
        with pytest.raises(ValidationError):
            DBSchema(**bad["db"])
