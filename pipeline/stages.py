"""
pipeline/stages.py
------------------
Pipeline stage gateway — the single import surface for all four stages.

Stages 1–3 (extract_intent, design_architecture, generate_schemas) delegate
to their own modules which make real Groq calls.  Stage 4 (refine) remains
as a hardcoded placeholder until its pipeline module is implemented.
"""

from __future__ import annotations

from schemas.intent import IntentModel
from schemas.architecture import ArchitectureModel
from schemas.ui import (
    UISchema, UIPage, UIComponent, FormFieldComponent,
    PageType, ComponentType, FormFieldType, Gate, GateKind,
)
from schemas.api import APISchema, APIEndpoint, APIField, HTTPMethod, APIPattern
from schemas.db import DBSchema, DBTable, DBColumn, ColumnType
from schemas.auth import AuthSchema, Role, Permission, PermissionAction, PermissionMatrixEntry


# ---------------------------------------------------------------------------
# Stage 1 – Intent Extraction
# ---------------------------------------------------------------------------

def extract_intent(raw_text: str) -> IntentModel:
    """
    Real implementation lives in pipeline/intent.py (uses Groq API).

    This thin wrapper imports and delegates to it, keeping stages.py as
    the single import surface for the rest of the pipeline.
    """
    from pipeline.intent import extract_intent as _real_extract_intent
    return _real_extract_intent(raw_text)


# ---------------------------------------------------------------------------
# Stage 2 – System Design
# ---------------------------------------------------------------------------

def design_architecture(intent: IntentModel) -> ArchitectureModel:
    """
    Real implementation lives in pipeline/architecture.py (uses Groq API).

    This thin wrapper imports and delegates to it, keeping stages.py as
    the single import surface for the rest of the pipeline.
    """
    from pipeline.architecture import design_architecture as _real_design_architecture
    return _real_design_architecture(intent)


# ---------------------------------------------------------------------------
# Stage 3 – Schema Generation
# ---------------------------------------------------------------------------

def generate_schemas(arch: ArchitectureModel) -> tuple[UISchema, APISchema, DBSchema, AuthSchema]:
    """
    Real implementation lives in pipeline/schema_gen.py (uses Groq API).

    Returns a 4-tuple (ui, api, db, auth) for backward compatibility with
    existing callers.  Internally uses SchemasResult with named attributes.
    """
    from pipeline.schema_gen import generate_schemas as _real_generate_schemas
    result = _real_generate_schemas(arch)
    return result.ui, result.api, result.db, result.auth


# ---------------------------------------------------------------------------
# Stage 4 – Refine
# ---------------------------------------------------------------------------

def refine(
    ui: UISchema,
    api: APISchema,
    db: DBSchema,
    auth: AuthSchema,
) -> tuple[UISchema, APISchema, DBSchema, AuthSchema]:
    """
    Placeholder: run consistency checks and (in production) repair violations.

    For now just returns the schemas unchanged; the actual checks live in
    refine/consistency.py and are exercised by the test suite.
    """
    from refine.consistency import run_all_checks
    errors = run_all_checks(ui=ui, api=api, db=db, auth=auth)
    if errors:
        # In production the repair engine would fix these.
        # For now we raise so integration tests surface violations immediately.
        raise ValueError(
            f"Consistency check failed with {len(errors)} error(s):\n"
            + "\n".join(f"  [{e.rule_violated}] {e.layer} | {e.field}: {e.message}" for e in errors)
        )
    return ui, api, db, auth
