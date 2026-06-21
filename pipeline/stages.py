"""
pipeline/stages.py
------------------
Four placeholder pipeline stage functions.

None of these make LLM calls.  They construct and return hardcoded example
instances of the Pydantic models to prove end-to-end data flow.

The example domain is a minimal CRM: Contacts managed by admins.
"""

from __future__ import annotations

from schemas.intent import IntentModel, EntityMention, RoleMention, FeatureFlag, Ambiguity
from schemas.architecture import (
    ArchitectureModel, ArchEntity, EntityRelation, ArchRole,
    UserFlow, RelationType,
)
from schemas.ui import (
    UISchema, UIPage, UIComponent, FormFieldComponent,
    PageType, ComponentType, FormFieldType, Gate, GateKind,
)
from schemas.api import APISchema, APIEndpoint, APIField, HTTPMethod, APIPattern
from schemas.db import DBSchema, DBTable, DBColumn, ColumnType
from schemas.auth import AuthSchema, Role, Permission, PermissionAction, PermissionMatrixEntry


# ---------------------------------------------------------------------------
# Stage 1 – Intent Extraction
# ---------------------------------------------------------------------------

def extract_intent(raw_text: str) -> IntentModel:
    """
    Placeholder: parse the user's raw NL request into an IntentModel.

    In production this will call an LLM.  For now it returns a fixed
    example derived from a simple CRM prompt.
    """
    return IntentModel(
        raw_text=raw_text,
        entities=[
            EntityMention(name="Contact", attributes=["name", "email", "phone"]),
        ],
        roles=[
            RoleMention(name="admin"),
            RoleMention(name="viewer"),
        ],
        features=[FeatureFlag.auth, FeatureFlag.crud, FeatureFlag.roles],
        ambiguities=[
            Ambiguity(
                field="company",
                message="Should Contact have a related Company entity, or just a string field?",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Stage 2 – System Design
# ---------------------------------------------------------------------------

def design_architecture(intent: IntentModel) -> ArchitectureModel:
    """
    Placeholder: translate an IntentModel into an ArchitectureModel.

    Resolves entity relationships and defines user flows.
    """
    return ArchitectureModel(
        entities=[
            ArchEntity(name="Contact", attributes=["id", "name", "email", "phone", "created_at"]),
        ],
        relations=[],
        roles=[
            ArchRole(name="admin", description="Full control over contacts."),
            ArchRole(name="viewer", description="Read-only access to contacts."),
        ],
        flows=[
            UserFlow(
                name="createContact",
                actor="admin",
                steps=[
                    "Navigate to /contacts",
                    "Click 'New Contact'",
                    "Fill in name, email, phone",
                    "Submit form → POST /contacts",
                ],
            ),
            UserFlow(
                name="viewContacts",
                actor="viewer",
                steps=[
                    "Navigate to /contacts",
                    "View contact list → GET /contacts",
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Stage 3 – Schema Generation
# ---------------------------------------------------------------------------

def generate_schemas(arch: ArchitectureModel) -> tuple[UISchema, APISchema, DBSchema, AuthSchema]:
    """
    Placeholder: generate all four schemas from the ArchitectureModel.

    Returns a 4-tuple: (UISchema, APISchema, DBSchema, AuthSchema).
    """
    # ── UI ──────────────────────────────────────────────────────────────────
    ui = UISchema(
        pages=[
            UIPage(
                name="ContactList",
                page_type=PageType.list,
                route="/contacts",
                gate=Gate(kind=GateKind.role_gate, allowed_roles=["admin", "viewer"]),
                components=[
                    UIComponent(
                        component_type=ComponentType.nav_bar,
                        name="main_nav",
                    ),
                    UIComponent(
                        component_type=ComponentType.table,
                        name="contacts_table",
                        fields=["id", "name", "email", "phone"],
                    ),
                ],
            ),
            UIPage(
                name="ContactForm",
                page_type=PageType.form,
                route="/contacts/new",
                gate=Gate(kind=GateKind.role_gate, allowed_roles=["admin"]),
                components=[
                    FormFieldComponent(name="name", field_type=FormFieldType.text, label="Full Name"),
                    FormFieldComponent(name="email", field_type=FormFieldType.email, label="Email"),
                    FormFieldComponent(name="phone", field_type=FormFieldType.text, label="Phone"),
                ],
            ),
        ]
    )

    # ── API ─────────────────────────────────────────────────────────────────
    api = APISchema(
        endpoints=[
            APIEndpoint(
                path="/contacts",
                method=HTTPMethod.GET,
                pattern=APIPattern.crud_list,
                response_fields=[
                    APIField(name="id", field_type="uuid"),
                    APIField(name="name", field_type="string"),
                    APIField(name="email", field_type="string"),
                    APIField(name="phone", field_type="string"),
                ],
                gate=Gate(kind=GateKind.role_gate, allowed_roles=["admin", "viewer"]),
            ),
            APIEndpoint(
                path="/contacts",
                method=HTTPMethod.POST,
                pattern=APIPattern.crud_create,
                request_fields=[
                    APIField(name="name", field_type="string"),
                    APIField(name="email", field_type="string"),
                    APIField(name="phone", field_type="string"),
                ],
                response_fields=[
                    APIField(name="id", field_type="uuid"),
                    APIField(name="name", field_type="string"),
                    APIField(name="email", field_type="string"),
                    APIField(name="phone", field_type="string"),
                    APIField(name="created_at", field_type="datetime"),
                ],
                gate=Gate(kind=GateKind.role_gate, allowed_roles=["admin"]),
            ),
        ]
    )

    # ── DB ──────────────────────────────────────────────────────────────────
    db = DBSchema(
        tables=[
            DBTable(
                name="contacts",
                columns=[
                    DBColumn(name="id", type=ColumnType.uuid, nullable=False),
                    DBColumn(name="name", type=ColumnType.string, nullable=False),
                    DBColumn(name="email", type=ColumnType.string, nullable=False),
                    DBColumn(name="phone", type=ColumnType.string, nullable=True),
                    DBColumn(name="created_at", type=ColumnType.datetime, nullable=False),
                ],
            )
        ]
    )

    # ── Auth ─────────────────────────────────────────────────────────────────
    auth = AuthSchema(
        roles=[
            Role(
                name="admin",
                permissions=[
                    Permission(resource="Contact", action=PermissionAction.manage),
                ],
            ),
            Role(
                name="viewer",
                permissions=[
                    Permission(resource="Contact", action=PermissionAction.read),
                ],
            ),
        ],
        permission_matrix=[
            PermissionMatrixEntry(role="admin", resource="Contact", action=PermissionAction.manage),
            PermissionMatrixEntry(role="viewer", resource="Contact", action=PermissionAction.read),
        ],
    )

    return ui, api, db, auth


# ---------------------------------------------------------------------------
# Stage 4 – Refine
# ---------------------------------------------------------------------------

def refine(
    ui: UISchema,
    api: APISchema,
    db: DBSchema,
    auth: AuthSchema,
) -> tuple[UISchema, APISchema, DBSchema, AuthSchema]:
    """
    Placeholder: run consistency checks and (in production) repair violations.

    For now just returns the schemas unchanged; the actual checks live in
    refine/consistency.py and are exercised by the test suite.
    """
    from refine.consistency import run_all_checks
    errors = run_all_checks(ui=ui, api=api, db=db, auth=auth)
    if errors:
        # In production the repair engine would fix these.
        # For now we raise so integration tests surface violations immediately.
        raise ValueError(
            f"Consistency check failed with {len(errors)} error(s):\n"
            + "\n".join(f"  [{e.rule_violated}] {e.layer} | {e.field}: {e.message}" for e in errors)
        )
    return ui, api, db, auth
