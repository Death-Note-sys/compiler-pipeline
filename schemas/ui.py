"""
schemas/ui.py
-------------
Layer 3 – UI Schema output.

All page types, component types, form field types, and gate kinds are drawn
exclusively from the compiler-schema-contract skill vocabulary.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

class PageType(str, Enum):
    list = "list"
    detail = "detail"
    dashboard = "dashboard"
    form = "form"
    settings = "settings"
    login = "login"
    landing = "landing"


class ComponentType(str, Enum):
    table = "table"
    card = "card"
    chart = "chart"
    form_field = "form_field"
    button = "button"
    modal = "modal"
    nav_bar = "nav_bar"
    sidebar = "sidebar"
    stat_widget = "stat_widget"
    badge = "badge"
    avatar = "avatar"
    alert = "alert"


class FormFieldType(str, Enum):
    text = "text"
    email = "email"
    password = "password"
    number = "number"
    date = "date"
    select = "select"
    multiselect = "multiselect"
    checkbox = "checkbox"
    textarea = "textarea"
    file = "file"


class GateKind(str, Enum):
    none = "none"
    role_gate = "role_gate"
    plan_gate = "plan_gate"
    both = "both"


# ---------------------------------------------------------------------------
# Gate model
# ---------------------------------------------------------------------------

class Gate(BaseModel):
    """Access gate for a page or component."""
    kind: GateKind = GateKind.none
    allowed_roles: List[str] = Field(
        default_factory=list,
        description="Role names allowed through a role_gate or both gate.",
    )
    plan: Optional[str] = Field(
        None,
        description="Plan name required for a plan_gate or both gate (e.g. 'premium').",
    )


# ---------------------------------------------------------------------------
# Component models
# ---------------------------------------------------------------------------

class FormFieldComponent(BaseModel):
    """A single input field rendered inside a form or modal."""
    component_type: ComponentType = ComponentType.form_field
    name: str = Field(..., description="Field identifier (snake_case). Must exist in an API endpoint.")
    field_type: FormFieldType
    label: Optional[str] = None
    required: bool = True


class UIComponent(BaseModel):
    """
    A generic UI component on a page.

    Use ``FormFieldComponent`` for form_field components so that
    ``field_type`` is always present and typed.
    """
    component_type: ComponentType
    name: str = Field(..., description="Component identifier (snake_case).")
    # Fields surfaced by table/card components (referenced against API responses)
    fields: List[str] = Field(
        default_factory=list,
        description="Field names exposed by this component (for consistency checks).",
    )
    gate: Gate = Field(default_factory=Gate)
    children: List[Union["FormFieldComponent", "UIComponent"]] = Field(
        default_factory=list,
        description="Nested components (e.g. form fields inside a modal).",
    )


UIComponent.model_rebuild()  # resolve forward refs


# ---------------------------------------------------------------------------
# Page model
# ---------------------------------------------------------------------------

class UIPage(BaseModel):
    """A single navigable page in the application."""
    name: str = Field(..., description="PascalCase page name (e.g. 'CustomerList').")
    page_type: PageType
    route: Optional[str] = Field(None, description="URL route pattern (e.g. '/customers').")
    gate: Gate = Field(default_factory=Gate)
    components: List[Union[FormFieldComponent, UIComponent]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------

class UISchema(BaseModel):
    """Output of the UI Schema Generation stage."""
    pages: List[UIPage] = Field(default_factory=list)
