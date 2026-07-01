"""
pipeline/results.py
-------------------
Shared result dataclasses for all pipeline stages.

Keeping result types in one module avoids circular imports and gives
consumers (tests, API, CLI) a single import location.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from schemas.db import DBSchema
    from schemas.api import APISchema
    from schemas.auth import AuthSchema
    from schemas.ui import UISchema
    from refine.consistency import ValidationError
    from pipeline.ddl import DDLValidationResult


@dataclass
class SchemasResult:
    """Container for the four generated sub-schemas and DDL validation."""
    db: "DBSchema"
    api: "APISchema"
    auth: "AuthSchema"
    ui: "UISchema"
    ddl: str = ""
    ddl_validation: Optional["DDLValidationResult"] = None


@dataclass
class RefinementResult:
    """
    Result from the refine stage.

    Attributes
    ----------
    violations : list[ValidationError]
        All consistency violations found across all 5 rules.
        Empty list means the schemas are clean.
    is_clean : bool
        True if violations is empty.
    summary : str
        Human-readable one-liner, e.g. "3 violations found" or "Clean".
    """
    violations: list["ValidationError"]
    is_clean: bool
    summary: str

    @classmethod
    def from_violations(cls, violations: list["ValidationError"]) -> "RefinementResult":
        """Factory: build a RefinementResult from a raw violations list."""
        is_clean = len(violations) == 0
        summary = "Clean" if is_clean else f"{len(violations)} violation(s) found"
        return cls(violations=violations, is_clean=is_clean, summary=summary)
