"""
refine/consistency.py
---------------------
Cross-layer consistency rules from the compiler-schema-contract skill.

These are plain Python functions — no LLM calls.
Each function returns a (possibly empty) list of ValidationError objects.
The repair engine consumes these structured errors for targeted fixes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from schemas.api import APISchema
from schemas.auth import AuthSchema
from schemas.db import DBSchema
from schemas.ui import UISchema, UIComponent, FormFieldComponent


# ---------------------------------------------------------------------------
# Structured error type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationError:
    """
    A structured consistency violation.

    Attributes
    ----------
    layer : str
        The layer pair where the violation occurs (e.g. "UI→API").
    field : str
        The field / column / role name that caused the violation.
    rule_violated : str
        Short code for the rule (e.g. "rule_1", "rule_2", …).
    message : str
        Human-readable explanation consumed by the repair engine.
    """
    layer: str
    field: str
    rule_violated: str
    message: str


# ---------------------------------------------------------------------------
# Helper: collect all field names referenced by UI components
# ---------------------------------------------------------------------------

def _collect_ui_fields(ui: UISchema) -> List[str]:
    """
    Walk all pages → components (and nested children) and collect the field
    names that a UI component exposes (relevant to Rule 1).

    For ``FormFieldComponent`` items we use ``name``.
    For ``UIComponent`` items we use names from their ``fields`` list, plus
    recurse into ``children``.
    """
    names: List[str] = []

    def _walk(components):
        for comp in components:
            if isinstance(comp, FormFieldComponent):
                names.append(comp.name)
            elif isinstance(comp, UIComponent):
                names.extend(comp.fields)
                _walk(comp.children)

    for page in ui.pages:
        _walk(page.components)

    return names


# ---------------------------------------------------------------------------
# Helper: collect all field names exposed by all API endpoints
# ---------------------------------------------------------------------------

def _collect_api_fields(api: APISchema) -> set[str]:
    names: set[str] = set()
    for ep in api.endpoints:
        for f in ep.request_fields:
            names.add(f.name)
        for f in ep.response_fields:
            names.add(f.name)
    return names


# ---------------------------------------------------------------------------
# Rule 1 – Every UI field must exist in some API endpoint
# ---------------------------------------------------------------------------

def check_rule_1_ui_fields_in_api(ui: UISchema, api: APISchema) -> List[ValidationError]:
    """
    Rule 1: Every field referenced by a UI form/table component must exist
    in some API endpoint's request or response fields.
    """
    errors: List[ValidationError] = []
    api_field_names = _collect_api_fields(api)
    ui_field_names = _collect_ui_fields(ui)

    for field_name in ui_field_names:
        if field_name not in api_field_names:
            errors.append(ValidationError(
                layer="UI→API",
                field=field_name,
                rule_violated="rule_1",
                message=(
                    f"UI references field '{field_name}' but no API endpoint "
                    f"declares it in request_fields or response_fields."
                ),
            ))
    return errors


# ---------------------------------------------------------------------------
# Rule 2 – Every non-computed API field must exist as a DB column
# ---------------------------------------------------------------------------

def check_rule_2_api_fields_in_db(api: APISchema, db: DBSchema) -> List[ValidationError]:
    """
    Rule 2: Every field in an API endpoint's request/response must exist as a
    DB column (or be explicitly marked as computed/joined).
    """
    errors: List[ValidationError] = []

    # Build a flat set of all DB column names across all tables.
    db_column_names: set[str] = set()
    for table in db.tables:
        for col in table.columns:
            db_column_names.add(col.name)

    for ep in api.endpoints:
        for field in ep.request_fields + ep.response_fields:
            if not field.computed and field.name not in db_column_names:
                errors.append(ValidationError(
                    layer="API→DB",
                    field=field.name,
                    rule_violated="rule_2",
                    message=(
                        f"API endpoint '{ep.method.value} {ep.path}' references "
                        f"field '{field.name}' which has no matching DB column "
                        f"and is not marked as computed."
                    ),
                ))
    return errors


# ---------------------------------------------------------------------------
# Rule 3 – Every gate role must exist in AuthSchema
# ---------------------------------------------------------------------------

def check_rule_3_gate_roles_in_auth(
    ui: UISchema, api: APISchema, auth: AuthSchema
) -> List[ValidationError]:
    """
    Rule 3: Every gate referencing a role must reference a role that exists
    in AuthSchema.roles.
    """
    errors: List[ValidationError] = []
    defined_roles = set(auth.role_names())

    # Check API endpoint gates
    for ep in api.endpoints:
        for role_name in ep.gate.allowed_roles:
            if role_name not in defined_roles:
                errors.append(ValidationError(
                    layer="API→Auth",
                    field=role_name,
                    rule_violated="rule_3",
                    message=(
                        f"API endpoint '{ep.method.value} {ep.path}' gate "
                        f"references undefined role '{role_name}'."
                    ),
                ))

    # Check UI page gates
    for page in ui.pages:
        for role_name in page.gate.allowed_roles:
            if role_name not in defined_roles:
                errors.append(ValidationError(
                    layer="UI→Auth",
                    field=role_name,
                    rule_violated="rule_3",
                    message=(
                        f"UI page '{page.name}' gate references "
                        f"undefined role '{role_name}'."
                    ),
                ))

    return errors


# ---------------------------------------------------------------------------
# Rule 4 – Every foreign_key column must point to an existing table.column
# ---------------------------------------------------------------------------

def check_rule_4_foreign_keys_exist(db: DBSchema) -> List[ValidationError]:
    """
    Rule 4: Every foreign_key column must point to an existing table.column.
    """
    errors: List[ValidationError] = []

    # Build index: table.column → True
    valid_targets: set[str] = set()
    for table in db.tables:
        for col in table.columns:
            valid_targets.add(f"{table.name}.{col.name}")

    for table in db.tables:
        for col in table.columns:
            if col.col_type.value == "foreign_key":
                if not col.foreign_key:
                    errors.append(ValidationError(
                        layer="DB",
                        field=f"{table.name}.{col.name}",
                        rule_violated="rule_4",
                        message=(
                            f"Column '{table.name}.{col.name}' has type foreign_key "
                            f"but no 'foreign_key' target is specified."
                        ),
                    ))
                elif col.foreign_key not in valid_targets:
                    errors.append(ValidationError(
                        layer="DB",
                        field=f"{table.name}.{col.name}",
                        rule_violated="rule_4",
                        message=(
                            f"Column '{table.name}.{col.name}' references "
                            f"'{col.foreign_key}' which does not exist in any table."
                        ),
                    ))
    return errors


# ---------------------------------------------------------------------------
# Rule 5 – Every API pattern must use its allowed HTTP method
# ---------------------------------------------------------------------------

def check_rule_5_pattern_method(api: APISchema) -> List[ValidationError]:
    """
    Rule 5: Every API pattern must use only its allowed HTTP method
    (e.g. crud_delete → DELETE only).

    Note: this is also enforced by the Pydantic model_validator on
    APIEndpoint, so violations should only reach here if models were
    constructed in a bypass path.
    """
    from schemas.api import PATTERN_METHOD_MAP

    errors: List[ValidationError] = []
    for ep in api.endpoints:
        allowed = PATTERN_METHOD_MAP.get(ep.pattern)
        if allowed is not None and ep.method != allowed:
            errors.append(ValidationError(
                layer="API",
                field=f"{ep.method.value} {ep.path}",
                rule_violated="rule_5",
                message=(
                    f"Pattern '{ep.pattern.value}' requires method "
                    f"{allowed.value}, but endpoint uses {ep.method.value}."
                ),
            ))
    return errors


# ---------------------------------------------------------------------------
# Convenience: run all rules at once
# ---------------------------------------------------------------------------

def run_all_checks(
    ui: UISchema,
    api: APISchema,
    db: DBSchema,
    auth: AuthSchema,
) -> List[ValidationError]:
    """Run all 5 consistency rules and return the combined error list."""
    return (
        check_rule_1_ui_fields_in_api(ui, api)
        + check_rule_2_api_fields_in_db(api, db)
        + check_rule_3_gate_roles_in_auth(ui, api, auth)
        + check_rule_4_foreign_keys_exist(db)
        + check_rule_5_pattern_method(api)
    )
