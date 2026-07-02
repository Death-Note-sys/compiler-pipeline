# NL-to-App Compiler Pipeline

> Convert a natural language app description into a validated,
> structured configuration — UI schema, API schema, DB schema,
> SQL DDL, Auth rules, and Business logic — through a deterministic
> multi-stage pipeline.

**Live Demo:** https://compiler-pipeline.onrender.com/
**GitHub:** https://github.com/Death-Note-sys/compiler-pipeline

---

## What It Does

Users input open-ended descriptions like:

> "Build a CRM with login, contacts, dashboard, role-based access,
> and premium plan with payments. Admins can see analytics."

The system converts this into a strict, validated configuration
covering UI, API, database, SQL DDL, auth, and business logic — ready
to power a runtime. When the input is vague or ambiguous, the pipeline
documents its assumptions as plain-English sentences in the output.

---

## Architecture

The pipeline has five stages, with parallel execution where
dependencies allow:

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
│                 │  role matrix, user flows, assumptions
└────────┬────────┘
         │ ArchitectureModel
         ▼
┌─────────────────┐
│ 3. Schema       │  DB first, then API + Auth in parallel,
│    Generation   │  then UI last. DDL generated from DB
│    (parallel)   │  schema with zero LLM calls.
└────────┬────────┘
         │ SchemasResult (DB + DDL + API + Auth + UI)
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

### Parallel Schema Generation

Stage 3 runs sub-schemas in parallel where dependencies allow:

```text
Round 1 (parallel):  DB + Auth  ─── run simultaneously
Round 2 (sequential): API       ─── needs DB columns
         DDL         ─── generated from DB (zero LLM calls)
Round 3 (sequential): UI        ─── needs DB + API + Auth
```

This saves ~12 seconds per run compared to fully sequential execution.

### SQL DDL Generation

After the DB schema is generated, the pipeline produces valid
`CREATE TABLE` statements with:

- **Topological ordering** — tables sorted by foreign key dependencies
  using Kahn's algorithm
- **SQLite validation** — DDL is executed against an in-memory SQLite
  database to prove correctness
- **Reserved keyword quoting** — table names like `order`, `group`,
  `user` are automatically double-quoted to avoid SQL syntax errors
- **Zero LLM calls** — pure Python code generation

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

### Assumptions Tracking

When the user's prompt is vague or ambiguous, the pipeline documents
every assumption it made in the `assumptions` field of the
`ArchitectureModel`. Examples:

- "Assumed authentication is required since no public access was specified."
- "Assumed workout plans are created by trainers, not uploaded by nutritionists."

These are surfaced in the web UI under the Architecture section.

---

## Provider Fallback & Rate Limit Handling

The pipeline uses Groq as primary provider with multi-layer
resilience:

```text
Groq call fails
  ├─ TPM (tokens per minute)?
  │    → parse "try again in 22s" from error
  │    → sleep exact duration
  │    → retry on Groq
  │    → if retry fails → fall through to Cerebras
  │
  ├─ TPD (tokens per day)?
  │    → immediate Cerebras fallback
  │
  └─ Other error → re-raise

Cerebras call fails
  ├─ TPM? → parse retry-after, sleep, retry once
  │         → if second failure → RuntimeError
  └─ Other → re-raise
```

| Function | Triggers on |
|---|---|
| `_is_daily_limit_error()` | Groq TPD — triggers provider switch |
| `_is_tpm_error()` | TPM hits — triggers sleep + retry on same provider |
| `_parse_retry_after()` | Extracts wait duration from error messages |

Model mapping: `llama-3.3-70b-versatile → gpt-oss-120b`

---

## Web UI

The single-page frontend (`api/main.py`) provides a real-time
streaming interface:

- **Example prompt chips** — 5 pre-built prompts (CRM, E-commerce,
  Gym, plus 2 edge cases) that pre-fill the textarea
- **Sticky progress bar** — fills as each of the 8 pipeline stages
  completes; turns red on error
- **Side dot navigation** — `IntersectionObserver`-powered dots that
  highlight the active section and smooth-scroll on click
- **Copy buttons** — one-click clipboard copy on every section
  (JSON/SQL), with "✓ Copied!" feedback
- **Dynamic badges** — real-time counts on each section header
  (e.g. "· 5 tables", "· 14 endpoints", "· ✓ Clean")
- **Animations** — fade-in slides for sections, pulse on Generate
  button, pop animation on validation badges
- **Assumptions display** — surfaced as 💡 callouts under Architecture
- **DDL validation badge** — "✓ Valid SQL" or "✗ Invalid" with
  table count
- **Back to top** button after scrolling

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
│   ├── architecture.py # Stage 2: design_architecture (+ assumptions)
│   ├── schema_gen.py # Stage 3: generate_schemas (parallel: DB+Auth, then API, then UI)
│   ├── ddl.py        # SQL DDL generation + SQLite validation (zero LLM calls)
│   ├── refine.py     # Stage 4: refine (pure Python)
│   ├── stages.py     # Orchestrator — wires all stages + DDL
│   ├── results.py    # SchemasResult + RefinementResult dataclasses
│   └── errors.py     # PipelineStageError
├── refine/
│   └── consistency.py # 5 cross-layer rules + run_all_checks()
├── llm/
│   └── groq_client.py # Groq primary + Cerebras fallback + TPM adaptive retry
├── eval/
│   ├── prompts.py    # 20 test prompts (10 real + 10 edge)
│   ├── runner.py     # Eval harness with metrics logging
│   └── report.py     # Summary report generator
├── api/
│   └── main.py       # FastAPI: GET / (UI) + POST /generate/stream + GET /health
├── tests/            # 93 unit tests (<2s, zero LLM calls) +
│                     # 37 live integration tests (auto-skip without key)
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

# Run full suite (includes live LLM tests — requires API keys)
python -m pytest tests/ -q

# Run evaluation
python -m eval.runner
python -m eval.report
```

---

## Design Decisions & Tradeoffs

**Why parallel schema generation (DB+Auth first, then API, then UI)?**
DB and Auth have no mutual dependencies, so they run simultaneously.
API needs DB columns to reference, and UI needs all three. This
dependency-aware parallelism saves ~12s per run while maintaining
cross-schema coherence.

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

**Why generate DDL with zero LLM calls?**
The DB schema already contains all the information needed — table
names, column types, foreign keys. A Python function with
topological sort produces deterministic, validated SQL every time,
with zero added latency or cost.

**Why adaptive sleep for TPM rate limits?**
The Groq/Cerebras SDK retries use exponential backoff, but TPM
cooldowns can be 20-60s — longer than the SDK's retry window.
Parsing the exact `"try again in Xs"` duration from the error
message and sleeping precisely avoids both under-waiting (retry
fails) and over-waiting (wasted time).

**Cost vs latency tradeoff**
- Stage 1 (intent): llama-3.1-8b-instant — cheap, fast, low-stakes extraction
- Stages 2-3 (design + schemas): llama-3.3-70b-versatile — stronger reasoning for entity relationships and schema coherence
- DDL generation: zero LLM cost — pure Python
- Stage 4 (refinement): zero LLM cost — pure Python
- Repair attempts: targeted field-level re-prompts, not full stage retries
- Session-scoped test fixtures: 144 potential API calls reduced to 18 per full test run

---

## Built With

Python 3.14 · FastAPI · Pydantic v2 · Groq SDK · Cerebras (OpenAI-compatible) · pytest · python-dotenv
