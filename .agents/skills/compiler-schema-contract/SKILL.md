---
name: compiler-schema-contract
description: Defines the closed vocabulary and Pydantic schema contracts for the NL-to-app compiler pipeline (Intent Extraction, System Design, Schema Generation, Refinement). Use whenever generating, editing, or validating intent models, architecture models, UI schema, API schema, DB schema, or Auth schema. Also use when implementing cross-layer consistency checks or the validation/repair engine.
---

# Compiler Schema Contract

This pipeline only ever describes apps using the closed vocabulary below.
Never invent new types outside this list - if a request needs something not
covered, add it here first, then use it everywhere.

## Page types
list, detail, dashboard, form, settings, login, landing

## Component types
table, card, chart, form_field, button, modal, nav_bar, sidebar, stat_widget, badge, avatar, alert

## Form field types
text, email, password, number, date, select, multiselect, checkbox, textarea, file

## API methods
GET, POST, PUT, PATCH, DELETE

## API patterns
crud_list, crud_detail, crud_create, crud_update, crud_delete,
auth_login, auth_register, auth_logout,
payment_checkout, payment_webhook, analytics_query

## DB column types
string, text, integer, float, boolean, date, datetime, uuid, json, enum, foreign_key

## Relation types
one_to_one, one_to_many, many_to_many

## Role/permission model
A Role is {name: str, permissions: list[Permission]}.
A Permission is {resource: str, action: one of [create, read, update, delete, manage]}.
"manage" implies all four.

## Gating
Every protected API endpoint and UI page declares a gate: one of
none, role_gate (list of allowed role names), plan_gate (e.g. "premium"), or both.

## Pydantic models - one file per layer, in schemas/
- schemas/intent.py -> IntentModel: raw_text, entities, roles, features, ambiguities
- schemas/architecture.py -> ArchitectureModel: entities, relations, roles, flows
- schemas/ui.py -> UISchema: pages (each has type + components list)
- schemas/api.py -> APISchema: endpoints (path, method, pattern, request_fields, response_fields, gate)
- schemas/db.py -> DBSchema: tables (each has columns: name, type, nullable, foreign_key target)
- schemas/auth.py -> AuthSchema: roles, permission_matrix

Every "type" field above must be a Python Enum - never a free-text string.

## Cross-layer consistency rules (Refinement layer - plain Python, NOT an LLM call)
1. Every field referenced by a UI form/table component must exist in some
   API endpoint's request or response fields.
2. Every field in an API endpoint's request/response must exist as a DB
   column (or be explicitly marked as computed/joined).
3. Every gate referencing a role must reference a role that exists in
   AuthSchema.roles.
4. Every foreign_key column must point to an existing table.column.
5. Every API pattern must use only its allowed HTTP method
   (e.g. crud_delete -> DELETE only).

Violations must be returned as structured objects:
{layer, field, rule_violated, message} - never a free-text error string.
This structured form is what the repair engine consumes for targeted fixes.
