"""
schemas/db.py
-------------
Layer 5 – Database Schema output.

All column types and relation types are drawn exclusively from the
compiler-schema-contract skill vocabulary.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

class ColumnType(str, Enum):
    string = "string"
    text = "text"
    integer = "integer"
    float_ = "float"          # 'float' is a Python builtin; alias with underscore
    boolean = "boolean"
    date = "date"
    datetime = "datetime"
    uuid = "uuid"
    json = "json"
    enum = "enum"
    foreign_key = "foreign_key"

    # Override value so JSON representation stays "float" (not "float_")
    @property
    def value(self) -> str:
        return super().value.rstrip("_")


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class DBColumn(BaseModel):
    """A single column in a database table."""
    name: str = Field(..., description="snake_case column name.")
    col_type: ColumnType = Field(..., alias="type")
    nullable: bool = False
    foreign_key: Optional[str] = Field(
        None,
        description=(
            "Target in 'table.column' notation, required when col_type is "
            "foreign_key. Used by Rule 4 consistency check."
        ),
    )

    model_config = {"populate_by_name": True}


class DBTable(BaseModel):
    """A single database table."""
    name: str = Field(..., description="snake_case table name.")
    columns: List[DBColumn] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class DBSchema(BaseModel):
    """Output of the DB Schema Generation stage."""
    tables: List[DBTable] = Field(default_factory=list)
