"""
tests/conftest.py
-----------------
Shared pytest fixtures.

Provides:
  - crm_data / todo_data   : raw dict loaded from examples/*.json
  - crm_schemas / todo_schemas : parsed Pydantic model 5-tuples
  - broken_crm_schemas     : CRM copy with one DB column removed to trigger Rule 2
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from schemas.intent import IntentModel
from schemas.architecture import ArchitectureModel
from schemas.ui import UISchema, UIComponent, FormFieldComponent
from schemas.api import APISchema
from schemas.db import DBSchema
from schemas.auth import AuthSchema

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


# ---------------------------------------------------------------------------
# Helper: parse a full pipeline JSON dict into model 5-tuple
# ---------------------------------------------------------------------------

def _parse_pipeline(data: dict):
    """Return (IntentModel, ArchitectureModel, UISchema, APISchema, DBSchema, AuthSchema)."""
    intent = IntentModel(**data["intent"])
    arch = ArchitectureModel(**data["architecture"])

    # UISchema pages contain a union of FormFieldComponent | UIComponent.
    # We parse via UISchema directly which handles the discriminated union.
    ui = UISchema(**data["ui"])
    api = APISchema(**data["api"])
    db = DBSchema(**data["db"])
    auth = AuthSchema(**data["auth"])
    return intent, arch, ui, api, db, auth


# ---------------------------------------------------------------------------
# Raw JSON fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def crm_data() -> dict:
    return json.loads((EXAMPLES_DIR / "crm_app.json").read_text())


@pytest.fixture(scope="session")
def todo_data() -> dict:
    return json.loads((EXAMPLES_DIR / "todo_app.json").read_text())


# ---------------------------------------------------------------------------
# Parsed schema fixtures (clean – all rules should pass)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def crm_schemas(crm_data):
    return _parse_pipeline(crm_data)


@pytest.fixture(scope="session")
def todo_schemas(todo_data):
    return _parse_pipeline(todo_data)


# ---------------------------------------------------------------------------
# Broken fixture: CRM copy with 'email' column removed from DB
# (the API still references 'email', so Rule 2 must fire)
# ---------------------------------------------------------------------------

@pytest.fixture
def broken_crm_schemas(crm_data):
    """
    Returns a mutated copy of the CRM pipeline where the 'email' column has
    been removed from the 'contacts' DB table.

    The API endpoints still reference 'email', so consistency Rule 2 should
    detect the violation.
    """
    data = copy.deepcopy(crm_data)

    # Remove the 'email' column from the contacts table
    contacts_table = data["db"]["tables"][0]
    contacts_table["columns"] = [
        col for col in contacts_table["columns"] if col["name"] != "email"
    ]

    return _parse_pipeline(data)
