"""
schemas/api.py
--------------
Layer 4 – API Schema output.

All HTTP methods, API patterns, and gate kinds are drawn exclusively from
the compiler-schema-contract skill vocabulary.

Rule 5 (pattern ↔ method) is enforced here as a Pydantic field_validator
so violations are caught at model construction time as well as by the
standalone refine/consistency.py check.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from schemas.ui import Gate  # reuse the Gate model


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class APIPattern(str, Enum):
    crud_list = "crud_list"
    crud_detail = "crud_detail"
    crud_create = "crud_create"
    crud_update = "crud_update"
    crud_delete = "crud_delete"
    auth_login = "auth_login"
    auth_register = "auth_register"
    auth_logout = "auth_logout"
    payment_checkout = "payment_checkout"
    payment_webhook = "payment_webhook"
    analytics_query = "analytics_query"


# ---------------------------------------------------------------------------
# Pattern → allowed HTTP methods (Rule 5)
# ---------------------------------------------------------------------------

PATTERN_METHOD_MAP: Dict[APIPattern, HTTPMethod] = {
    APIPattern.crud_list: HTTPMethod.GET,
    APIPattern.crud_detail: HTTPMethod.GET,
    APIPattern.crud_create: HTTPMethod.POST,
    APIPattern.crud_update: HTTPMethod.PUT,
    APIPattern.crud_delete: HTTPMethod.DELETE,
    APIPattern.auth_login: HTTPMethod.POST,
    APIPattern.auth_register: HTTPMethod.POST,
    APIPattern.auth_logout: HTTPMethod.POST,
    APIPattern.payment_checkout: HTTPMethod.POST,
    APIPattern.payment_webhook: HTTPMethod.POST,
    APIPattern.analytics_query: HTTPMethod.GET,
}


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class APIField(BaseModel):
    """A single field in a request or response payload."""
    name: str = Field(..., description="snake_case field name.")
    field_type: str = Field(..., description="Logical type label (mirrors DB column types).")
    required: bool = True
    computed: bool = Field(
        False,
        description=(
            "If True this field is computed/joined and does not need a matching "
            "DB column (Rule 2 exemption)."
        ),
    )


class APIEndpoint(BaseModel):
    """A single API endpoint declaration."""
    path: str = Field(..., description="URL path pattern (e.g. '/customers/{id}').")
    method: HTTPMethod
    pattern: APIPattern
    request_fields: List[APIField] = Field(default_factory=list)
    response_fields: List[APIField] = Field(default_factory=list)
    gate: Gate = Field(default_factory=Gate)

    @model_validator(mode="after")
    def _check_pattern_method(self) -> "APIEndpoint":
        """Rule 5 guard: pattern must use its canonical HTTP method."""
        allowed = PATTERN_METHOD_MAP.get(self.pattern)
        if allowed is not None and self.method != allowed:
            raise ValueError(
                f"Pattern '{self.pattern}' requires method {allowed.value}, "
                f"got {self.method.value}. (Rule 5)"
            )
        return self


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class APISchema(BaseModel):
    """Output of the API Schema Generation stage."""
    endpoints: List[APIEndpoint] = Field(default_factory=list)
