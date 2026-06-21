"""
schemas/architecture.py
-----------------------
Layer 2 – System Design output.

All vocabulary is drawn from the compiler-schema-contract skill.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

class RelationType(str, Enum):
    one_to_one = "one_to_one"
    one_to_many = "one_to_many"
    many_to_many = "many_to_many"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class ArchEntity(BaseModel):
    """A first-class domain entity in the system design."""
    name: str = Field(..., description="Singular PascalCase entity name.")
    attributes: List[str] = Field(
        default_factory=list,
        description="Attribute names owned by this entity.",
    )


class EntityRelation(BaseModel):
    """A directed relationship between two entities."""
    from_entity: str = Field(..., description="Source entity name.")
    to_entity: str = Field(..., description="Target entity name.")
    relation_type: RelationType


class ArchRole(BaseModel):
    """An actor role in the system (maps to AuthSchema roles later)."""
    name: str = Field(..., description="Lowercase role name.")
    description: Optional[str] = Field(None)


class UserFlow(BaseModel):
    """
    A named sequence of steps describing how a role accomplishes a goal.

    Steps are free-form at this stage; they become concrete API calls in
    later layers.
    """
    name: str = Field(..., description="Short camelCase identifier for this flow.")
    actor: str = Field(..., description="Role name that initiates the flow.")
    steps: List[str] = Field(
        default_factory=list,
        description="Ordered human-readable description of each step.",
    )


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class ArchitectureModel(BaseModel):
    """
    Output of the System Design stage.

    Describes *what* the system contains without specifying implementation
    details (DB tables, API routes, UI pages are handled in later layers).
    """

    entities: List[ArchEntity] = Field(default_factory=list)
    relations: List[EntityRelation] = Field(default_factory=list)
    roles: List[ArchRole] = Field(default_factory=list)
    flows: List[UserFlow] = Field(default_factory=list)
