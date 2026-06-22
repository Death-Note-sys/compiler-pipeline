"""
pipeline/schema_gen.py
-----------------------
Stage 3 – Schema Generation (real Groq implementation).

Public API
----------
``generate_schemas(arch: ArchitectureModel) -> SchemasResult``
    Performs four sequential LLM calls, each building on the previous results:
      1. DBSchema   (most fundamental — tables and columns)
      2. APISchema  (sees DBSchema — endpoints reference real columns)
      3. AuthSchema (sees DB + API — roles and permission matrix)
      4. UISchema   (sees all three — pages/components reference real fields)

    Returns a ``SchemasResult`` dataclass with ``.db``, ``.api``,
    ``.auth``, ``.ui`` attributes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from llm.groq_client import chat_json
from pipeline.errors import PipelineStageError
from pipeline.results import SchemasResult  # canonical definition
from schemas.api import APISchema, PATTERN_METHOD_MAP
from schemas.architecture import ArchitectureModel
from schemas.auth import AuthSchema
from schemas.db import DBSchema
from schemas.ui import UISchema

# Re-export so existing "from pipeline.schema_gen import SchemasResult" callers keep working
__all__ = ["generate_schemas", "SchemasResult"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

_MODEL = "llama-3.3-70b-versatile"
_TEMPERATURE = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS (one per sub-schema call)
# ═══════════════════════════════════════════════════════════════════════════════

# ---------------------------------------------------------------------------
# 1. DB Schema
# ---------------------------------------------------------------------------

_DB_SYSTEM_PROMPT = """\
You are an expert database architect.

Given a system architecture (entities, relations, roles, flows), design
the database schema and return ONLY a single JSON object — no markdown,
no code fences, no extra keys.

The JSON must have this exact shape:

{
  "tables": [
    {
      "name": "<snake_case table name, e.g. contacts, orders>",
      "columns": [
        {
          "name": "<snake_case column name>",
          "type": "<one of: string | text | integer | float | boolean | date | datetime | uuid | json | enum | foreign_key>",
          "nullable": <true | false>,
          "foreign_key": "<target in 'table.column' notation, or null if not a foreign key>"
        }
      ]
    }
  ]
}

Rules:
- Create one table per entity in the architecture, plus any join tables needed for many_to_many relations.
- Every table MUST have an "id" column of type "uuid" and a "created_at" column of type "datetime".
- For one_to_many relations, the "many" side table gets a foreign_key column.
- For many_to_many relations, create a join table with two foreign_key columns.
- Column type MUST be one of the allowed values listed above — do not invent types.
- Return ONLY the JSON object.
"""

# ---------------------------------------------------------------------------
# 2. API Schema
# ---------------------------------------------------------------------------

_API_SYSTEM_PROMPT = """\
You are an expert API designer.

Given a system architecture and the already-generated database schema,
design the API endpoints and return ONLY a single JSON object — no
markdown, no code fences, no extra keys.

The JSON must have this exact shape:

{
  "endpoints": [
    {
      "path": "<URL path pattern, e.g. '/contacts', '/contacts/{id}'>",
      "method": "<one of: GET | POST | PUT | DELETE>",
      "pattern": "<one of: crud_list | crud_detail | crud_create | crud_update | crud_delete | auth_login | auth_register | auth_logout | payment_checkout | payment_webhook | analytics_query>",
      "request_fields": [
        {"name": "<snake_case>", "field_type": "<type label matching DB column types>", "required": true, "computed": false}
      ],
      "response_fields": [
        {"name": "<snake_case>", "field_type": "<type label>", "required": true, "computed": false}
      ],
      "gate": {
        "kind": "<one of: none | role_gate | plan_gate | both>",
        "allowed_roles": ["<role names if role_gate or both>"],
        "plan": null
      }
    }
  ]
}

CRITICAL pattern-to-method rules (violations will fail validation):
- crud_list    → GET
- crud_detail  → GET
- crud_create  → POST
- crud_update  → PUT  (NOT PATCH)
- crud_delete  → DELETE
- auth_login   → POST
- auth_register → POST
- auth_logout  → POST
- payment_checkout → POST
- payment_webhook  → POST
- analytics_query  → GET

Rules:
- All request_fields and response_fields names MUST exist as columns in the provided DB schema tables.
- Set "computed": true only for fields that are derived/joined and don't have a direct DB column.
- method MUST match the pattern exactly per the rules above.
- Return ONLY the JSON object.
"""

# ---------------------------------------------------------------------------
# 3. Auth Schema
# ---------------------------------------------------------------------------

_AUTH_SYSTEM_PROMPT = """\
You are an expert in application security and access control.

Given a system architecture plus the already-generated DB and API schemas,
design the auth schema and return ONLY a single JSON object — no markdown,
no code fences, no extra keys.

The JSON must have this exact shape:

{
  "roles": [
    {
      "name": "<lowercase role name, e.g. admin, viewer>",
      "permissions": [
        {
          "resource": "<entity name the permission applies to, e.g. Contact, Order>",
          "action": "<one of: create | read | update | delete | manage>"
        }
      ]
    }
  ],
  "permission_matrix": [
    {
      "role": "<role name>",
      "resource": "<entity name>",
      "action": "<one of: create | read | update | delete | manage>"
    }
  ]
}

Rules:
- "manage" means all four CRUD actions (create + read + update + delete).
- The permission_matrix MUST be a flat list consistent with the roles list.
- Every role referenced in the API gate's allowed_roles must be defined here.
- action MUST be one of the five allowed values listed above.
- Return ONLY the JSON object.
"""

# ---------------------------------------------------------------------------
# 4. UI Schema
# ---------------------------------------------------------------------------

_UI_SYSTEM_PROMPT = """\
You are an expert frontend architect.

Given a system architecture plus the already-generated DB, API, and Auth
schemas, design the UI schema and return ONLY a single JSON object — no
markdown, no code fences, no extra keys.

The JSON must have this exact shape:

{
  "pages": [
    {
      "name": "<PascalCase page name, e.g. ContactList, OrderDetail>",
      "page_type": "<one of: list | detail | dashboard | form | settings | login | landing>",
      "route": "<URL route pattern, e.g. '/contacts'>",
      "gate": {
        "kind": "<one of: none | role_gate | plan_gate | both>",
        "allowed_roles": ["<role names if role_gate or both>"],
        "plan": null
      },
      "components": [
        {
          "component_type": "<one of: table | card | chart | form_field | button | modal | nav_bar | sidebar | stat_widget | badge | avatar | alert>",
          "name": "<snake_case component identifier>",
          "fields": ["<field names for table/card components — must exist in API endpoints>"],
          "gate": {"kind": "none", "allowed_roles": [], "plan": null},
          "children": []
        }
      ]
    }
  ]
}

For form_field components, use this shape instead:
{
  "component_type": "form_field",
  "name": "<snake_case field name — must exist in an API endpoint>",
  "field_type": "<one of: text | email | password | number | date | select | multiselect | checkbox | textarea | file>",
  "label": "<human-readable label>",
  "required": true
}

Rules:
- page_type MUST be one of the seven allowed values.
- component_type MUST be one of the twelve allowed values.
- form_field field_type MUST be one of the ten allowed values.
- gate kind MUST be one of the four allowed values.
- All field names in table/card component "fields" arrays must exist in API endpoint response_fields.
- All form_field "name" values must exist in API endpoint request_fields.
- All allowed_roles in gates must be defined in the Auth schema.
- Return ONLY the JSON object.
"""


# ---------------------------------------------------------------------------
# Build a string→string lookup from PATTERN_METHOD_MAP for pre-validation use.
# PATTERN_METHOD_MAP uses enum keys/values; we need raw strings since the
# normalizer runs before Pydantic coerces enums.
# ---------------------------------------------------------------------------
_PATTERN_TO_METHOD: dict[str, str] = {
    p.value: m.value for p, m in PATTERN_METHOD_MAP.items()
}


def normalize_endpoint(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a single API endpoint dict before Pydantic validation.

    If the endpoint's ``method`` contradicts its ``pattern`` per the
    canonical ``PATTERN_METHOD_MAP``, the method is corrected to match
    the map and the event is logged as a normalization (distinct from a
    repair — this is free, deterministic, code-only correction).

    Parameters
    ----------
    raw : dict
        A raw endpoint dict as parsed from the model JSON response.

    Returns
    -------
    dict
        The (possibly corrected) endpoint dict.  Returns a shallow copy
        when a correction is made; returns the original dict when no
        change is needed.
    """
    pattern = raw.get("pattern")
    method = raw.get("method")

    if not isinstance(pattern, str) or not isinstance(method, str):
        return raw

    expected_method = _PATTERN_TO_METHOD.get(pattern)
    if expected_method is None:
        # Unknown pattern — let Pydantic catch it
        return raw

    if method == expected_method:
        return raw

    # Mismatch → correct the method
    result = dict(raw)
    result["method"] = expected_method
    logger.info(
        "normalized | generate_schemas.api | pattern %r requires method %s, "
        "got %s — corrected",
        pattern, expected_method, method,
    )
    return result


def _normalize_api_data(data: dict[str, Any]) -> dict[str, Any]:
    """Apply normalize_endpoint() to every endpoint in the parsed response."""
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list):
        return data
    data["endpoints"] = [
        normalize_endpoint(ep) if isinstance(ep, dict) else ep
        for ep in endpoints
    ]
    return data



# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_db_messages(arch: ArchitectureModel) -> list[dict[str, str]]:
    arch_json = json.dumps(arch.model_dump(), indent=2)
    return [
        {"role": "system", "content": _DB_SYSTEM_PROMPT},
        {"role": "user", "content": f"Here is the system architecture. Design the database schema:\n\n{arch_json}"},
    ]


def _build_api_messages(arch: ArchitectureModel, db: DBSchema) -> list[dict[str, str]]:
    arch_json = json.dumps(arch.model_dump(), indent=2)
    db_json = json.dumps(db.model_dump(by_alias=True), indent=2)
    return [
        {"role": "system", "content": _API_SYSTEM_PROMPT},
        {"role": "user", "content": (
            "Here is the system architecture and the generated DB schema. "
            "Design the API endpoints. All fields you reference must exist "
            "in the provided DB schema.\n\n"
            f"=== Architecture ===\n{arch_json}\n\n"
            f"=== DB Schema ===\n{db_json}"
        )},
    ]


def _build_auth_messages(arch: ArchitectureModel, db: DBSchema, api: APISchema) -> list[dict[str, str]]:
    arch_json = json.dumps(arch.model_dump(), indent=2)
    db_json = json.dumps(db.model_dump(by_alias=True), indent=2)
    api_json = json.dumps(api.model_dump(), indent=2)
    return [
        {"role": "system", "content": _AUTH_SYSTEM_PROMPT},
        {"role": "user", "content": (
            "Here is the system architecture and the generated schemas so far. "
            "Design the auth schema. All roles you reference must exist in the "
            "architecture and API gates.\n\n"
            f"=== Architecture ===\n{arch_json}\n\n"
            f"=== DB Schema ===\n{db_json}\n\n"
            f"=== API Schema ===\n{api_json}"
        )},
    ]


def _build_ui_messages(
    arch: ArchitectureModel,
    db: DBSchema,
    api: APISchema,
    auth: AuthSchema,
) -> list[dict[str, str]]:
    arch_json = json.dumps(arch.model_dump(), indent=2)
    db_json = json.dumps(db.model_dump(by_alias=True), indent=2)
    api_json = json.dumps(api.model_dump(), indent=2)
    auth_json = json.dumps(auth.model_dump(), indent=2)
    return [
        {"role": "system", "content": _UI_SYSTEM_PROMPT},
        {"role": "user", "content": (
            "Here is the system architecture and all generated schemas so far. "
            "Design the UI schema. All fields you reference must exist in the "
            "provided context schemas.\n\n"
            f"=== Architecture ===\n{arch_json}\n\n"
            f"=== DB Schema ===\n{db_json}\n\n"
            f"=== API Schema ===\n{api_json}\n\n"
            f"=== Auth Schema ===\n{auth_json}"
        )},
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# REPAIR MESSAGE BUILDER (generic)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_repair_messages(
    original_messages: list[dict[str, str]],
    bad_output: str,
    validation_error: ValidationError,
) -> list[dict[str, str]]:
    """Build a repair prompt from any sub-schema's original messages."""
    error_summary = validation_error.json(indent=2)
    repair_instruction = (
        "The JSON you returned failed Pydantic validation. "
        "Here is the exact error:\n\n"
        f"{error_summary}\n\n"
        "Here is the JSON you returned:\n\n"
        f"{bad_output}\n\n"
        "Return a corrected JSON object that satisfies the schema. "
        "Return ONLY the corrected JSON object — no markdown, no explanation."
    )
    return original_messages + [
        {"role": "assistant", "content": bad_output},
        {"role": "user", "content": repair_instruction},
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# GENERIC CALL + VALIDATE + REPAIR RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def _call_and_validate(
    stage_tag: str,
    messages: list[dict[str, str]],
    model_class: type,
    *,
    pre_normalize: Any | None = None,
) -> Any:
    """
    Send messages to Groq, validate against ``model_class``, one repair attempt.

    Parameters
    ----------
    stage_tag : str
        Human-readable tag for logging (e.g. "generate_schemas.db").
    messages : list
        The initial message list (system + user).
    model_class : type
        Pydantic model to validate against.
    pre_normalize : callable | None
        Optional function to apply to the parsed dict before Pydantic
        validation (e.g. ``_normalize_api_data``).

    Returns
    -------
    Validated Pydantic model instance.

    Raises
    ------
    PipelineStageError
        If both the first attempt and repair fail validation.
    """
    logger.info("%s | model=%s temperature=%s", stage_tag, _MODEL, _TEMPERATURE)

    raw_response = chat_json(messages, model=_MODEL, temperature=_TEMPERATURE)

    first_error: json.JSONDecodeError | ValidationError | None = None
    try:
        data: Any = json.loads(raw_response)
        if pre_normalize and isinstance(data, dict):
            data = pre_normalize(data)
        result = model_class.model_validate(data)
        logger.info("%s | first attempt succeeded | repair_needed=False", stage_tag)
        return result

    except (json.JSONDecodeError, ValidationError) as exc:
        first_error = exc
        logger.warning(
            "%s | first attempt failed (%s: %s) — attempting repair",
            stage_tag,
            type(exc).__name__,
            str(exc)[:300],
        )

    # ── Repair attempt ───────────────────────────────────────────────────────
    assert first_error is not None
    if isinstance(first_error, ValidationError):
        repair_msgs = _build_repair_messages(messages, raw_response, first_error)
    else:
        repair_msgs = messages  # JSON decode error: retry fresh

    repair_response = chat_json(repair_msgs, model=_MODEL, temperature=_TEMPERATURE)
    logger.info("%s | repair_needed=True", stage_tag)

    try:
        data = json.loads(repair_response)
        if pre_normalize and isinstance(data, dict):
            data = pre_normalize(data)
        result = model_class.model_validate(data)
        logger.info("%s | repair attempt succeeded", stage_tag)
        return result

    except (json.JSONDecodeError, ValidationError) as repair_error:
        raise PipelineStageError(
            stage=stage_tag,
            detail=(
                "Groq response failed validation after one repair attempt. "
                f"Final error: {repair_error}"
            ),
            cause=repair_error,
        ) from repair_error


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_schemas(arch: ArchitectureModel) -> SchemasResult:
    """
    Generate all four sub-schemas via sequential Groq calls.

    Call order: DB → API → Auth → UI.  Each call sees the architecture plus
    all previously generated sub-schemas so later schemas can reference
    earlier ones correctly.

    Returns a ``SchemasResult`` dataclass with ``.db``, ``.api``,
    ``.auth``, ``.ui`` attributes.
    """
    logger.info(
        "generate_schemas | starting | entities=%d roles=%d",
        len(arch.entities),
        len(arch.roles),
    )

    # 1. DB
    db_messages = _build_db_messages(arch)
    db: DBSchema = _call_and_validate("generate_schemas.db", db_messages, DBSchema)

    # 2. API (sees DB)
    api_messages = _build_api_messages(arch, db)
    api: APISchema = _call_and_validate(
        "generate_schemas.api", api_messages, APISchema,
        pre_normalize=_normalize_api_data,
    )

    # 3. Auth (sees DB + API)
    auth_messages = _build_auth_messages(arch, db, api)
    auth: AuthSchema = _call_and_validate("generate_schemas.auth", auth_messages, AuthSchema)

    # 4. UI (sees all three)
    ui_messages = _build_ui_messages(arch, db, api, auth)
    ui: UISchema = _call_and_validate("generate_schemas.ui", ui_messages, UISchema)

    logger.info(
        "generate_schemas | complete | tables=%d endpoints=%d roles=%d pages=%d",
        len(db.tables),
        len(api.endpoints),
        len(auth.roles),
        len(ui.pages),
    )

    return SchemasResult(db=db, api=api, auth=auth, ui=ui)
