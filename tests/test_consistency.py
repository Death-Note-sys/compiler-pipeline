"""
tests/test_consistency.py
--------------------------
Tests for the cross-layer consistency rules in refine/consistency.py.

Uses the broken_crm_schemas fixture (from conftest.py) which synthetically
removes the 'email' column from the DB while the API still references it.
"""

from __future__ import annotations

import pytest

from refine.consistency import (
    check_rule_1_ui_fields_in_api,
    check_rule_2_api_fields_in_db,
    check_rule_3_gate_roles_in_auth,
    check_rule_4_foreign_keys_exist,
    check_rule_5_pattern_method,
    run_all_checks,
)


# ---------------------------------------------------------------------------
# Clean examples – all rules pass
# ---------------------------------------------------------------------------

class TestCleanCRM:
    def test_rule_1_passes(self, crm_schemas):
        _, _, ui, api, db, auth = crm_schemas
        assert check_rule_1_ui_fields_in_api(ui, api) == []

    def test_rule_2_passes(self, crm_schemas):
        _, _, ui, api, db, auth = crm_schemas
        assert check_rule_2_api_fields_in_db(api, db) == []

    def test_rule_3_passes(self, crm_schemas):
        _, _, ui, api, db, auth = crm_schemas
        assert check_rule_3_gate_roles_in_auth(ui, api, auth) == []

    def test_rule_4_passes(self, crm_schemas):
        _, _, ui, api, db, auth = crm_schemas
        assert check_rule_4_foreign_keys_exist(db) == []

    def test_rule_5_passes(self, crm_schemas):
        _, _, ui, api, db, auth = crm_schemas
        assert check_rule_5_pattern_method(api) == []

    def test_run_all_passes(self, crm_schemas):
        _, _, ui, api, db, auth = crm_schemas
        assert run_all_checks(ui=ui, api=api, db=db, auth=auth) == []


class TestCleanTodo:
    def test_all_rules_pass(self, todo_schemas):
        _, _, ui, api, db, auth = todo_schemas
        errors = run_all_checks(ui=ui, api=api, db=db, auth=auth)
        assert errors == [], f"Unexpected errors: {errors}"


# ---------------------------------------------------------------------------
# Broken fixture – Rule 2 must fire (email missing from DB)
# ---------------------------------------------------------------------------

class TestRule2Violation:
    def test_rule_2_catches_missing_db_column(self, broken_crm_schemas):
        """
        The broken fixture removes 'email' from contacts DB table.
        Rule 2 must return at least one error for the 'email' field,
        with rule_violated == 'rule_2' and layer == 'API→DB'.
        """
        _, _, ui, api, db, auth = broken_crm_schemas
        errors = check_rule_2_api_fields_in_db(api, db)

        assert len(errors) >= 1, "Expected at least one Rule 2 violation."

        email_errors = [e for e in errors if e.field == "email"]
        assert len(email_errors) >= 1, (
            f"Expected a Rule 2 error for field 'email'. Got: {errors}"
        )
        for e in email_errors:
            assert e.rule_violated == "rule_2"
            assert e.layer == "API→DB"
            assert "email" in e.message

    def test_rule_2_other_rules_still_pass(self, broken_crm_schemas):
        """
        Only Rule 2 should fire on the broken fixture;
        Rules 1, 3, 4, 5 must remain clean.
        """
        _, _, ui, api, db, auth = broken_crm_schemas
        assert check_rule_1_ui_fields_in_api(ui, api) == []
        assert check_rule_3_gate_roles_in_auth(ui, api, auth) == []
        assert check_rule_4_foreign_keys_exist(db) == []
        assert check_rule_5_pattern_method(api) == []

    def test_run_all_returns_rule_2_errors(self, broken_crm_schemas):
        """run_all_checks must surface the Rule 2 errors for the broken fixture."""
        _, _, ui, api, db, auth = broken_crm_schemas
        all_errors = run_all_checks(ui=ui, api=api, db=db, auth=auth)
        rule_2_errors = [e for e in all_errors if e.rule_violated == "rule_2"]
        assert len(rule_2_errors) >= 1


# ---------------------------------------------------------------------------
# Rule 3 – undefined role in gate
# ---------------------------------------------------------------------------

class TestRule3Violation:
    def test_undefined_role_in_api_gate(self, crm_schemas):
        """Inject a gate that references a non-existent role 'superuser'."""
        import copy
        from schemas.api import APISchema, APIEndpoint, HTTPMethod, APIPattern
        from schemas.ui import Gate, GateKind

        _, _, ui, api, db, auth = crm_schemas

        bad_endpoint = APIEndpoint(
            path="/contacts/admin-only",
            method=HTTPMethod.GET,
            pattern=APIPattern.crud_list,
            gate=Gate(kind=GateKind.role_gate, allowed_roles=["superuser"]),
        )
        bad_api = APISchema(endpoints=api.endpoints + [bad_endpoint])

        errors = check_rule_3_gate_roles_in_auth(ui, bad_api, auth)
        assert any(
            e.rule_violated == "rule_3" and e.field == "superuser"
            for e in errors
        ), f"Expected rule_3 for 'superuser', got: {errors}"


# ---------------------------------------------------------------------------
# Rule 4 – foreign key to non-existent table
# ---------------------------------------------------------------------------

class TestRule4Violation:
    def test_missing_fk_target_detected(self, crm_schemas):
        """Inject a FK column pointing to a non-existent table."""
        import copy
        from schemas.db import DBSchema, DBTable, DBColumn, ColumnType

        _, _, ui, api, db, auth = crm_schemas

        bad_db = DBSchema(tables=[
            DBTable(
                name="contacts",
                columns=[
                    DBColumn(name="id", type=ColumnType.uuid),
                    DBColumn(
                        name="company_id",
                        type=ColumnType.foreign_key,
                        foreign_key="companies.id",  # 'companies' table does not exist
                    ),
                ],
            )
        ])

        errors = check_rule_4_foreign_keys_exist(bad_db)
        assert any(e.rule_violated == "rule_4" for e in errors), (
            f"Expected rule_4 violation. Got: {errors}"
        )


# ---------------------------------------------------------------------------
# Rule 5 – wrong method for pattern
# ---------------------------------------------------------------------------

class TestRule5Violation:
    def test_wrong_method_for_crud_delete(self, crm_schemas):
        """
        crud_delete requires DELETE. Constructing with GET should raise at
        model level (Pydantic validator); consistency.py also catches it.
        """
        from pydantic import ValidationError as PydanticValidationError
        from schemas.api import APIEndpoint, HTTPMethod, APIPattern

        with pytest.raises(PydanticValidationError):
            APIEndpoint(
                path="/contacts/{id}",
                method=HTTPMethod.GET,   # wrong – should be DELETE
                pattern=APIPattern.crud_delete,
            )
