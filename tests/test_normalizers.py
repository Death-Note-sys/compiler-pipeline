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
