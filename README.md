# NL-to-App Compiler Pipeline

> Convert a natural language app description into a validated,
> structured configuration — UI schema, API schema, DB schema,
> Auth rules, and Business logic — through a deterministic
> multi-stage pipeline.

**Live Demo:** [your-render-url]
**GitHub:** https://github.com/Death-Note-sys/compiler-pipeline

---

## What It Does

Users input open-ended descriptions like:

> "Build a CRM with login, contacts, dashboard, role-based access,
> and premium plan with payments. Admins can see analytics."

The system converts this into a strict, validated configuration
covering UI, API, database, auth, and business logic — ready to
power a runtime.

---

## Architecture

The pipeline has four stages, each isolated and independently
testable:

```text
Natural Language
       │
       ▼
┌─────────────────┐
│ 1. Intent       │  llama-3.1-8b-instant (Groq)
│    Extraction   │  Extracts entities, roles, features,
│                 │  ambiguities from raw text
└────────┬────────┘
         │ IntentModel
         ▼
┌─────────────────┐
│ 2. System       │  llama-3.3-70b-versatile (Groq)
│    Design       │  Entities → architecture, relations,
│                 │  role matrix, user flows
└────────┬────────┘
         │ ArchitectureModel
         ▼
┌─────────────────┐
│ 3. Schema       │  4 sequential LLM calls:
│    Generation   │  DB → API → Auth → UI
│                 │  Each call sees prior outputs
└────────┬────────┘
         │ SchemasResult
         ▼
┌─────────────────┐
│ 4. Refinement   │  Pure Python (zero LLM calls)
│                 │  5 cross-layer consistency rules
│                 │  Returns structured violations
└─────────────────┘
         │ RefinementResult
         ▼
    JSON Output
```

---

## Closed Vocabulary

All generated schemas use a fixed, enumerated vocabulary defined
in `.agents/skills/compiler-schema-contract/SKILL.md`. This is
the core mechanism for deterministic output — the LLM cannot
invent types outside this contract.

| Category | Values |
|---|---|
| Page types | list, detail, dashboard, form, settings, login, landing |
| Component types | table, card, chart, form_field, button, modal, nav_bar, sidebar, stat_widget, badge, avatar, alert |
| API patterns | crud_list, crud_detail, crud_create, crud_update, crud_delete, auth_login, auth_register, auth_logout, payment_checkout, payment_webhook, analytics_query |
| DB column types | string, text, integer, float, boolean, date, datetime, uuid, json, enum, foreign_key |
| Gate types | none, role_gate, plan_gate, both |

---

## Validation & Repair Engine

Every stage follows: **generate → validate → repair → fail hard**

- Pydantic v2 validates all output at parse time
- On validation failure: one targeted repair attempt using the
  specific field-level error, not a full retry
- On double failure: `PipelineStageError(stage, detail, cause)`
  with full context attached

### Normalizers (pre-validation, zero LLM cost)
Two deterministic normalizers catch known LLM quirks before
validation fires:

- `normalize_relation()` — maps `many_to_one → one_to_many`
  and swaps entity direction to preserve semantic meaning
- `normalize_endpoint()` — enforces the full `PATTERN_METHOD_MAP`
  (e.g. `crud_update → PUT`, `crud_delete → DELETE`) across all
  11 API patterns

### Cross-Layer Consistency Rules (Refinement stage)
Five rules checked in pure Python — no LLM calls:

1. Every UI field must exist in some API endpoint's fields
2. Every API field must exist as a DB column (or be marked computed)
3. Every gate must reference a role that exists in AuthSchema
4. Every foreign_key must point to an existing table.column
5. Every API pattern must use only its canonical HTTP method

Violations are returned as structured objects
`{layer, field, rule_violated, message}` — never free text.

---

## Provider Fallback

The pipeline uses Groq as primary provider and automatically
falls back to Cerebras when Groq's daily token limit (TPD) is
exhausted — detected via `_is_daily_limit_error()` which checks
specifically for "tokens per day" errors, not transient RPM hits.

```text
Groq (primary)
       │ on TPD exhaustion
       ▼
Cerebras (fallback)
model map: llama-3.3-70b-versatile → gpt-oss-120b
```

---

## Evaluation Results

Tested against 20 prompts: 10 real product descriptions +
10 edge cases (vague, conflicting, incomplete, contradictory,
overspecified, minimal).

| Metric | Result |
|---|---|
| Overall success rate | 19/20 (95%) |
| Real prompts | 10/10 (100%) |
| Edge prompts | 9/10 (90%) |
| Mean latency (Groq) | ~30s per run |
| Total repairs needed | 0 |
| Prompts with violations | 1/19 (ecommerce — 3 violations caught) |
| Single failure cause | edge_08 (overspecified: 47 fields/12 roles) hit provider RPM limit |

---

## Project Structure

```text
compiler-pipeline/
├── .agents/skills/compiler-schema-contract/SKILL.md
├── schemas/          # Pydantic models: intent, architecture, ui, api, db, auth
├── pipeline/         # Stage implementations + orchestration
│   ├── intent.py     # Stage 1: extract_intent
│   ├── architecture.py # Stage 2: design_architecture
│   ├── schema_gen.py # Stage 3: generate_schemas (4 sub-calls)
│   ├── refine.py     # Stage 4: refine (pure Python)
│   ├── stages.py     # Orchestrator — wires all 4 stages
│   ├── results.py    # SchemasResult + RefinementResult dataclasses
│   └── errors.py     # PipelineStageError
├── refine/
│   └── consistency.py # 5 cross-layer rules + run_all_checks()
├── llm/
│   └── groq_client.py # Thin wrapper: Groq primary + Cerebras fallback
├── eval/
│   ├── prompts.py    # 20 test prompts (10 real + 10 edge)
│   ├── runner.py     # Eval harness with metrics logging
│   └── report.py     # Summary report generator
├── api/
│   └── main.py       # FastAPI: GET / (UI) + POST /generate + GET /health
├── tests/            # 78 unit tests (0.8s, zero LLM calls) +
│                     # 36 live integration tests (auto-skip without key)
└── examples/
    ├── crm_app.json  # Reference pipeline output: CRM
    └── todo_app.json # Reference pipeline output: Todo
```

---

## Running Locally

```bash
git clone https://github.com/Death-Note-sys/compiler-pipeline
cd compiler-pipeline
pip install -r requirements.txt

# Add keys to .env
echo "GROQ_API_KEY=your_key" >> .env
echo "CEREBRAS_API_KEY=your_key" >> .env  # optional fallback

# Run the API
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Run a single prompt
python -m pipeline.run_pipeline "Build a todo app with auth"

# Run unit tests (instant, no API key needed)
python -m pytest tests/test_pipeline.py tests/test_schemas.py \
  tests/test_consistency.py tests/test_normalizers.py -q

# Run evaluation
python -m eval.runner
python -m eval.report
```

---

## Design Decisions & Tradeoffs

**Why sequential schema generation (DB→API→Auth→UI)?**
Each sub-schema sees previous outputs as context, so API fields
reference real DB columns, not hallucinated ones. A single large
call would produce four independent schemas with no cross-layer
coherence.

**Why a closed vocabulary instead of free-form generation?**
Free-form type fields produce non-deterministic output that breaks
downstream validation. A fixed enum vocabulary makes every type
field a classification problem — predictable, validatable,
repairable.

**Why normalizers instead of expanding the enum vocabulary?**
When the model uses `many_to_one` instead of `one_to_many`, the
correct fix is not to add `many_to_one` to the enum — that creates
two valid representations of the same relationship and breaks
de-duplication. The normalizer maps to one canonical form and logs
it as a distinct event, separate from repair.

**Why rule-based refinement instead of LLM cross-checking?**
Consistency rules are deterministic — either a field exists or it
doesn't. An LLM cross-checker would add latency, cost, and
non-determinism to a check that can be done with a Python dict
lookup in milliseconds.

**Cost vs latency tradeoff**
- Stage 1 (intent): llama-3.1-8b-instant — cheap, fast, low-stakes extraction
- Stages 2-3 (design + schemas): llama-3.3-70b-versatile — stronger reasoning for entity relationships and schema coherence
- Stage 4 (refinement): zero LLM cost — pure Python
- Repair attempts: targeted field-level re-prompts, not full stage retries
- Session-scoped test fixtures: 144 potential API calls reduced to 18 per full test run

---

## Built With

Python 3.14 · FastAPI · Pydantic v2 · Groq SDK · Cerebras (OpenAI-compatible) · pytest · python-dotenv
