"""
schemas/intent.py
-----------------
Layer 1 – Intent Extraction output.

Vocabulary is closed: every Literal / Enum value is drawn exclusively from
the compiler-schema-contract skill. Do not add types outside that contract.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field



# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class EntityMention(BaseModel):
    """A domain entity named in the raw text (e.g. 'Customer', 'Invoice')."""
    name: str = Field(..., description="Singular PascalCase entity name.")
    attributes: List[str] = Field(
        default_factory=list,
        description="Raw attribute names mentioned alongside this entity.",
    )


class RoleMention(BaseModel):
    """An access role inferred from the raw text (e.g. 'admin', 'viewer')."""
    name: str = Field(..., description="Lowercase role name as mentioned.")


class Ambiguity(BaseModel):
    """A question the pipeline cannot resolve without human clarification."""
    field: str = Field(..., description="The field or concept that is ambiguous.")
    message: str = Field(..., description="Human-readable description of the ambiguity.")


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class IntentModel(BaseModel):
    """
    Output of the Intent Extraction stage.

    Captures everything the NL-to-app compiler understands (and does *not*
    yet understand) from the user's raw request.
    """

    raw_text: str = Field(..., description="The original natural-language input, unchanged.")
    entities: List[EntityMention] = Field(
        default_factory=list,
        description="Domain entities recognised in the raw text.",
    )
    roles: List[RoleMention] = Field(
        default_factory=list,
        description="Access roles inferred from the raw text.",
    )
    features: List[str] = Field(
        default_factory=list,
        description=(
            "High-level feature labels extracted from the raw text (free-text strings). "
            "Closed-vocabulary enforcement happens at the Schema Generation layer, "
            "not here."
        ),
    )
    ambiguities: List[Ambiguity] = Field(
        default_factory=list,
        description="Open questions that need clarification before proceeding.",
    )
