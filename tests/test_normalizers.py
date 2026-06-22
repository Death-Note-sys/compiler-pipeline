"""
tests/test_normalizers.py
--------------------------
Unit tests for deterministic normalization functions.

These require NO Groq API key — they are pure Python functions over
known inputs.  They run in all environments, including CI without secrets.
"""

from __future__ import annotations

import pytest

from pipeline.architecture import normalize_relation


# ---------------------------------------------------------------------------
# normalize_relation — many_to_one → one_to_many with entity swap
# ---------------------------------------------------------------------------

class TestNormalizeRelation:
    def test_many_to_one_becomes_one_to_many(self):
        """relation_type must be rewritten to the canonical value."""
        raw = {
            "from_entity": "OrderItem",
            "to_entity": "Order",
            "relation_type": "many_to_one",
        }
        result = normalize_relation(raw)
        assert result["relation_type"] == "one_to_many"

    def test_many_to_one_swaps_entity_fields(self):
        """
        Entity fields must be swapped so the semantic direction is preserved:
        original  → OrderItem many_to_one Order  (many items belong to one order)
        canonical → Order one_to_many OrderItem  (one order has many items)
        """
        raw = {
            "from_entity": "OrderItem",
            "to_entity": "Order",
            "relation_type": "many_to_one",
        }
        result = normalize_relation(raw)
        assert result["from_entity"] == "Order"
        assert result["to_entity"] == "OrderItem"

    def test_original_dict_is_not_mutated(self):
        """normalize_relation must return a copy — caller's dict unchanged."""
        raw = {
            "from_entity": "OrderItem",
            "to_entity": "Order",
            "relation_type": "many_to_one",
        }
        original_from = raw["from_entity"]
        normalize_relation(raw)
        assert raw["from_entity"] == original_from, (
            "normalize_relation must not mutate its input dict"
        )

    def test_canonical_types_pass_through_unchanged(self):
        """Already-canonical relation types must not be modified."""
        for rt in ("one_to_one", "one_to_many", "many_to_many"):
            raw = {"from_entity": "A", "to_entity": "B", "relation_type": rt}
            result = normalize_relation(raw)
            assert result["relation_type"] == rt
            assert result["from_entity"] == "A"
            assert result["to_entity"] == "B"

    def test_unknown_type_passes_through_unchanged(self):
        """Completely unknown relation types are returned as-is (Pydantic catches them)."""
        raw = {"from_entity": "A", "to_entity": "B", "relation_type": "some_future_type"}
        result = normalize_relation(raw)
        assert result["relation_type"] == "some_future_type"

    def test_missing_relation_type_passes_through(self):
        """A dict with no relation_type key must be returned unchanged."""
        raw = {"from_entity": "A", "to_entity": "B"}
        result = normalize_relation(raw)
        assert "relation_type" not in result

    def test_non_string_relation_type_passes_through(self):
        """A non-string relation_type must be returned unchanged (Pydantic catches it)."""
        raw = {"from_entity": "A", "to_entity": "B", "relation_type": 42}
        result = normalize_relation(raw)
        assert result["relation_type"] == 42


# ---------------------------------------------------------------------------
# normalize_endpoint — enforces full PATTERN_METHOD_MAP
# ---------------------------------------------------------------------------

from pipeline.schema_gen import normalize_endpoint


class TestNormalizeEndpoint:
    def test_crud_update_patch_corrected_to_put(self):
        """crud_update with PATCH must be corrected to PUT."""
        raw = {"path": "/contacts/{id}", "method": "PATCH", "pattern": "crud_update"}
        result = normalize_endpoint(raw)
        assert result["method"] == "PUT"

    def test_crud_delete_post_corrected_to_delete(self):
        """crud_delete with POST must be corrected to DELETE."""
        raw = {"path": "/contacts/{id}", "method": "POST", "pattern": "crud_delete"}
        result = normalize_endpoint(raw)
        assert result["method"] == "DELETE"

    def test_crud_list_post_corrected_to_get(self):
        """crud_list with POST must be corrected to GET."""
        raw = {"path": "/contacts", "method": "POST", "pattern": "crud_list"}
        result = normalize_endpoint(raw)
        assert result["method"] == "GET"

    def test_crud_create_get_corrected_to_post(self):
        """crud_create with GET must be corrected to POST."""
        raw = {"path": "/contacts", "method": "GET", "pattern": "crud_create"}
        result = normalize_endpoint(raw)
        assert result["method"] == "POST"

    def test_auth_login_get_corrected_to_post(self):
        """auth_login with GET must be corrected to POST."""
        raw = {"path": "/auth/login", "method": "GET", "pattern": "auth_login"}
        result = normalize_endpoint(raw)
        assert result["method"] == "POST"

    @pytest.mark.parametrize("pattern,expected_method", [
        ("crud_list", "GET"),
        ("crud_detail", "GET"),
        ("crud_create", "POST"),
        ("crud_update", "PUT"),
        ("crud_delete", "DELETE"),
        ("auth_login", "POST"),
        ("auth_register", "POST"),
        ("auth_logout", "POST"),
        ("payment_checkout", "POST"),
        ("payment_webhook", "POST"),
        ("analytics_query", "GET"),
    ])
    def test_correct_pattern_method_passes_through(self, pattern, expected_method):
        """Already-correct pattern/method pairs must not be modified."""
        raw = {"path": "/test", "method": expected_method, "pattern": pattern}
        result = normalize_endpoint(raw)
        assert result["method"] == expected_method
        # Should return the same dict object (no copy needed)
        assert result is raw

    def test_original_dict_is_not_mutated(self):
        """normalize_endpoint must return a copy when correcting — caller's dict unchanged."""
        raw = {"path": "/x", "method": "PATCH", "pattern": "crud_update"}
        original_method = raw["method"]
        normalize_endpoint(raw)
        assert raw["method"] == original_method, (
            "normalize_endpoint must not mutate its input dict"
        )

    def test_unknown_pattern_passes_through(self):
        """Unknown patterns are returned as-is (Pydantic catches them)."""
        raw = {"path": "/x", "method": "POST", "pattern": "some_future_pattern"}
        result = normalize_endpoint(raw)
        assert result["method"] == "POST"

    def test_missing_pattern_passes_through(self):
        """A dict with no pattern key must be returned unchanged."""
        raw = {"path": "/x", "method": "GET"}
        result = normalize_endpoint(raw)
        assert result is raw

    def test_missing_method_passes_through(self):
        """A dict with no method key must be returned unchanged."""
        raw = {"path": "/x", "pattern": "crud_list"}
        result = normalize_endpoint(raw)
        assert result is raw

    def test_non_string_method_passes_through(self):
        """A non-string method must be returned unchanged (Pydantic catches it)."""
        raw = {"path": "/x", "method": 42, "pattern": "crud_list"}
        result = normalize_endpoint(raw)
        assert result["method"] == 42

