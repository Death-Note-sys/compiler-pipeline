"""
schemas/auth.py
---------------
Layer 6 – Auth Schema output.

Role/permission vocabulary is drawn exclusively from the
compiler-schema-contract skill. "manage" implies all four CRUD actions.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

class PermissionAction(str, Enum):
    create = "create"
    read = "read"
    update = "update"
    delete = "delete"
    manage = "manage"   # implies all four


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class Permission(BaseModel):
    """A single permission entry: which resource and what action."""
    resource: str = Field(..., description="The resource name (usually an entity name).")
    action: PermissionAction


class Role(BaseModel):
    """A named access role with its list of permissions."""
    name: str = Field(..., description="Lowercase role name (e.g. 'admin', 'viewer').")
    permissions: List[Permission] = Field(default_factory=list)


class PermissionMatrixEntry(BaseModel):
    """One row in the permission matrix: a (role, resource, action) triple."""
    role: str
    resource: str
    action: PermissionAction


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class AuthSchema(BaseModel):
    """
    Output of the Auth Schema Generation stage.

    ``permission_matrix`` is a flattened view derived from the roles list,
    useful for quick look-up during consistency checks (Rule 3).
    """

    roles: List[Role] = Field(default_factory=list)
    permission_matrix: List[PermissionMatrixEntry] = Field(
        default_factory=list,
        description=(
            "Flat list of (role, resource, action) triples. "
            "Must be consistent with `roles`."
        ),
    )

    def role_names(self) -> List[str]:
        """Helper: return all defined role names (for Rule 3 checks)."""
        return [r.name for r in self.roles]
