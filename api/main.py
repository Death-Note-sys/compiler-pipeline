"""
api/main.py
-----------
FastAPI application for the NL-to-app compiler pipeline.

Endpoints
---------
GET  /health    — returns model names and pipeline stage names
POST /generate  — runs the full 4-stage pipeline and returns structured JSON
"""

from __future__ import annotations

import asyncio
import json as _json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from pipeline.errors import PipelineStageError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="NL App Compiler Pipeline",
    description="Natural-language → app schema compiler. POST a prompt, get a full app spec.",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class PromptRequest(BaseModel):
    prompt: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NL-to-App Compiler</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {
    --background: #0f0f0f;
    --surface: #1a1a1a;
    --border: #2a2a2a;
    --accent: #6366f1;
    --text: #e5e5e5;
    --success: #22c55e;
    --error: #ef4444;
    --font-mono: 'JetBrains Mono', 'Faber', monospace;
    --font-sans: system-ui, sans-serif;
  }
  body {
    background-color: var(--background);
    color: var(--text);
    font-family: var(--font-sans);
    margin: 0;
    padding: 20px;
    display: flex;
    justify-content: center;
  }
  .container {
    max-width: 800px;
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  textarea {
    width: 100%;
    height: 120px;
    background-color: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    font-family: var(--font-sans);
    font-size: 16px;
    resize: vertical;
    box-sizing: border-box;
  }
  button {
    background-color: var(--accent);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 16px;
    cursor: pointer;
    font-weight: bold;
    align-self: flex-start;
  }
  button:hover { opacity: 0.9; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .loading {
    display: none;
    color: var(--accent);
    font-weight: bold;
    margin-top: 10px;
  }
  .error-box {
    display: none;
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error);
    color: var(--error);
    padding: 16px;
    border-radius: 8px;
    margin-top: 20px;
  }
  details {
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 10px;
    overflow: hidden;
  }
  summary {
    padding: 16px;
    font-weight: bold;
    cursor: pointer;
    display: flex;
    align-items: center;
    user-select: none;
  }
  summary:hover { background-color: rgba(255, 255, 255, 0.05); }
  pre {
    background-color: #111;
    margin: 0;
    padding: 16px;
    font-family: var(--font-mono);
    font-size: 14px;
    overflow-x: auto;
    border-top: 1px solid var(--border);
  }
  .badge {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 12px;
    margin-left: auto;
    font-weight: bold;
  }
  .badge.success { background-color: rgba(34, 197, 94, 0.2); color: var(--success); border: 1px solid var(--success); }
  .badge.error { background-color: rgba(239, 68, 68, 0.2); color: var(--error); border: 1px solid var(--error); }
  .examples-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-top: -10px;
    margin-bottom: 10px;
  }
  .examples-label {
    font-size: 12px;
    color: #999;
  }
  .chip {
    padding: 6px 12px;
    border-radius: 16px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid #2a2a2a;
    background-color: #1a1a1a;
    color: #999;
    transition: filter 0.2s;
    user-select: none;
  }
  .chip:hover {
    filter: brightness(1.2);
  }
  .chip.edge-case {
    border: 1px solid #92400e;
    background-color: #1c1200;
    color: #d97706;
  }
</style>
</head>
<body>

<div class="container">
  <h1>NL-to-App Compiler</h1>
  <div>
    <textarea id="prompt">Build a CRM where admins manage contacts and sales reps view their assigned contacts. Include role-based access and activity logging.</textarea>
  </div>
  <div class="examples-row">
    <span class="examples-label">Try an example:</span>
    <div class="chip" data-prompt="Build a CRM where admins manage contacts and sales reps view their assigned contacts. Include role-based access and activity logging.">CRM</div>
    <div class="chip" data-prompt="An e-commerce platform where customers browse products, add to cart, and checkout. Admins manage inventory and view orders. Support discount codes.">E-commerce</div>
    <div class="chip" data-prompt="Build a gym management system where trainers manage workout plans, members book classes, administrators manage memberships, and nutritionists upload diet plans.">Gym</div>
    <div class="chip edge-case" data-prompt="Build me an app.">Vague (edge case)</div>
    <div class="chip edge-case" data-prompt="All users are both admins and regular users with full access but also restricted access at the same time.">Conflicting (edge case)</div>
  </div>
  <div>
    <button id="generateBtn">Generate</button>
    <div id="loading" class="loading">Running pipeline... (~30s)</div>
  </div>

  <div id="errorBox" class="error-box"></div>
  <div id="results" style="display: none;">
    <details id="det-intent"><summary>Intent</summary><pre id="out-intent"></pre></details>
    <details id="det-arch">
      <summary>Architecture</summary>
      <div id="arch-assumptions" style="display: none; padding: 12px 16px; background-color: rgba(255,255,255,0.05); border-bottom: 1px solid var(--border); font-size: 14px; line-height: 1.5; color: #a3a3a3;"></div>
      <pre id="out-arch"></pre>
    </details>
    <details id="det-db"><summary>DB Schema</summary><pre id="out-db"></pre></details>
    <details id="det-ddl"><summary>SQL DDL <span id="ddl-badge" class="badge"></span></summary><pre id="out-ddl"></pre></details>
    <details id="det-api"><summary>API Schema</summary><pre id="out-api"></pre></details>
    <details id="det-auth"><summary>Auth Schema</summary><pre id="out-auth"></pre></details>
    <details id="det-ui"><summary>UI Schema</summary><pre id="out-ui"></pre></details>
    <details id="det-refine" open>
      <summary>Refinement <span id="refine-badge" class="badge"></span></summary>
      <pre id="out-refine"></pre>
    </details>
  </div>
</div>

<script>
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.getElementById('prompt').value = chip.dataset.prompt;
  });
});

document.getElementById('generateBtn').addEventListener('click', async () => {
  const btn = document.getElementById('generateBtn');
  const loading = document.getElementById('loading');
  const errorBox = document.getElementById('errorBox');
  const results = document.getElementById('results');
  const prompt = document.getElementById('prompt').value;

  btn.disabled = true;
  loading.style.display = 'block';
  loading.textContent = '⟳ Starting pipeline...';
  errorBox.style.display = 'none';
  results.style.display = 'block';

  // Reset all sections to collapsed and clear content
  ['intent','arch','db','ddl','api','auth','ui','refine'].forEach(id => {
    const det = document.getElementById('det-' + id);
    if (det) det.removeAttribute('open');
  });

  try {
    const response = await fetch('/generate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });

    if (!response.ok) {
      const text = await response.text();
      if (text.includes('DOCTYPE')) {
        throw new Error('Server is waking up \u2014 please wait 30 seconds and try again.');
      }
      const errData = JSON.parse(text);
      throw new Error(errData.detail || 'Pipeline failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Split on SSE double-newline boundaries
      const SSE_SEP = String.fromCharCode(10, 10);
      const parts = buffer.split(SSE_SEP);
      buffer = parts.pop(); // keep incomplete trailing chunk

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data: ')) continue;
        let event;
        try { event = JSON.parse(line.slice(6)); } catch { continue; }

        const stage = event.stage;
        const data = event.data;

        if (stage === 'intent') {
          loading.textContent = '⟳ Running: Architecture...';
          document.getElementById('out-intent').textContent = JSON.stringify(data, null, 2);
          document.getElementById('det-intent').setAttribute('open', '');
        } else if (stage === 'architecture') {
          loading.textContent = '⟳ Running: DB Schema...';
          document.getElementById('out-arch').textContent = JSON.stringify(data, null, 2);
          const assumptionsBox = document.getElementById('arch-assumptions');
          if (data.assumptions && data.assumptions.length > 0) {
            assumptionsBox.style.display = 'block';
            
            // safely build elements instead of innerHTML to avoid XSS
            assumptionsBox.textContent = '';
            const strong = document.createElement('strong');
            strong.textContent = 'Assumptions made:';
            strong.style.color = 'var(--text)';
            assumptionsBox.appendChild(strong);
            
            data.assumptions.forEach(a => {
              const div = document.createElement('div');
              div.textContent = '💡 ' + a;
              div.style.marginTop = '4px';
              assumptionsBox.appendChild(div);
            });
          } else {
            assumptionsBox.style.display = 'none';
          }
          document.getElementById('det-arch').setAttribute('open', '');
        } else if (stage === 'db_schema') {
          loading.textContent = '⟳ Running: SQL DDL...';
          document.getElementById('out-db').textContent = JSON.stringify(data, null, 2);
          document.getElementById('det-db').setAttribute('open', '');
        } else if (stage === 'ddl') {
          loading.textContent = '⟳ Running: API Schema...';
          const ddlBadge = document.getElementById('ddl-badge');
          if (data.valid) {
            ddlBadge.textContent = '✓ Valid SQL';
            ddlBadge.className = 'badge success';
          } else {
            ddlBadge.textContent = '✗ Invalid';
            ddlBadge.className = 'badge error';
          }
          let outText = data.sql;
          if (data.error) {
            outText += String.fromCharCode(10, 10) + 'Error: ' + data.error;
          }
          document.getElementById('out-ddl').textContent = outText;
          document.getElementById('det-ddl').setAttribute('open', '');
        } else if (stage === 'api_schema') {
          loading.textContent = '⟳ Running: Auth Schema...';
          document.getElementById('out-api').textContent = JSON.stringify(data, null, 2);
          document.getElementById('det-api').setAttribute('open', '');
        } else if (stage === 'auth_schema') {
          loading.textContent = '⟳ Running: UI Schema...';
          document.getElementById('out-auth').textContent = JSON.stringify(data, null, 2);
          document.getElementById('det-auth').setAttribute('open', '');
        } else if (stage === 'ui_schema') {
          loading.textContent = '⟳ Running: Refinement...';
          document.getElementById('out-ui').textContent = JSON.stringify(data, null, 2);
          document.getElementById('det-ui').setAttribute('open', '');
        } else if (stage === 'refinement') {
          const ref = data;
          const refBadge = document.getElementById('refine-badge');
          if (ref.is_clean) {
            refBadge.textContent = '\u2713 Clean';
            refBadge.className = 'badge success';
          } else {
            refBadge.textContent = ref.violation_count + ' Violations';
            refBadge.className = 'badge error';
          }
          document.getElementById('out-refine').textContent = JSON.stringify(ref, null, 2);
          document.getElementById('det-refine').setAttribute('open', '');
        } else if (stage === 'done') {
          loading.style.display = 'none';
        } else if (stage === 'error') {
          errorBox.style.display = 'block';
          errorBox.textContent = 'Pipeline error at ' + (event.failed_stage || 'unknown') + ': ' + (event.detail || 'Unknown error');
          loading.style.display = 'none';
        }
      }
    }
  } catch (err) {
    errorBox.style.display = 'block';
    errorBox.textContent = 'Network or server error: ' + err.message;
    loading.style.display = 'none';
  } finally {
    btn.disabled = false;
  }
});
</script>
</body>
</html>"""

@app.get("/")
def index():
    """Serve the single-page HTML interface."""
    return HTMLResponse(content=HTML_CONTENT)


@app.get("/health")
def health():
    """System awareness endpoint — returns model names and pipeline stage names."""
    return {
        "status": "ok",
        "pipeline_stages": [
            "extract_intent",
            "design_architecture",
            "generate_schemas",
            "refine",
        ],
        "llm_models": {
            "intent": "llama-3.3-70b-versatile",
            "architecture": "llama-3.3-70b-versatile",
            "schema_generation": "llama-3.3-70b-versatile",
        },
        "consistency_rules": [
            "rule_1: UI fields must exist in API",
            "rule_2: API fields must exist in DB",
            "rule_3: Gate roles must exist in Auth",
            "rule_4: Foreign keys must point to valid table.column",
            "rule_5: API pattern must use correct HTTP method",
        ],
    }


@app.post("/generate")
def generate(req: PromptRequest):
    """
    Run the full 4-stage compiler pipeline on a natural-language prompt.

    Returns a JSON object with intent, architecture, schemas, and refinement results.
    Returns HTTP 422 if any pipeline stage raises a PipelineStageError.
    """
    from pipeline.stages import extract_intent, design_architecture, generate_schemas, refine

    try:
        # Stage 1
        intent = extract_intent(req.prompt)

        # Stage 2
        arch = design_architecture(intent)

        # Stage 3
        schemas = generate_schemas(arch)

        # Stage 4
        refinement = refine(schemas)

    except PipelineStageError as exc:
        logger.error("Pipeline stage error: %s — %s", exc.stage, exc.detail)
        return JSONResponse(
            status_code=422,
            content={"error": exc.stage, "detail": exc.detail},
        )

    return {
        "intent": intent.model_dump(),
        "architecture": arch.model_dump(),
        "schemas": {
            "db": schemas.db.model_dump(by_alias=True),
            "api": schemas.api.model_dump(),
            "auth": schemas.auth.model_dump(),
            "ui": schemas.ui.model_dump(),
        },
        "ddl": {
            "sql": schemas.ddl,
            "valid": schemas.ddl_validation.success if schemas.ddl_validation else False,
            "table_count": schemas.ddl_validation.table_count if schemas.ddl_validation else 0,
            "error": schemas.ddl_validation.error if schemas.ddl_validation else None
        },
        "refinement": {
            "is_clean": refinement.is_clean,
            "violation_count": len(refinement.violations),
            "violations": [
                {
                    "layer": v.layer,
                    "field": v.field,
                    "rule_violated": v.rule_violated,
                    "message": v.message,
                }
                for v in refinement.violations
            ],
        },
    }


@app.post("/generate/stream")
async def generate_stream(req: PromptRequest):
    """
    Stream the 4-stage pipeline results as Server-Sent Events.

    Each pipeline stage result is emitted immediately after it completes.
    Schema generation emits 4 separate events (one per sub-schema) with
    real latency gaps between them.

    Event format: ``data: {"stage": "<name>", "data": <payload>}\\n\\n``
    Terminal event: ``data: {"stage": "done"}\\n\\n``
    Error event:   ``data: {"stage": "error", "failed_stage": "...", "detail": "..."}\\n\\n``
    """
    from pipeline.intent import extract_intent
    from pipeline.architecture import design_architecture
    from pipeline.schema_gen import generate_schemas_streaming
    from pipeline.refine import refine
    from pipeline.results import SchemasResult

    def _sse(payload: dict) -> str:
        return f"data: {_json.dumps(payload)}\n\n"

    async def event_generator():
        loop = asyncio.get_event_loop()

        try:
            # Stage 1: Intent (blocking — run in thread)
            intent = await loop.run_in_executor(None, extract_intent, req.prompt)
            yield _sse({"stage": "intent", "data": intent.model_dump()})
            logger.info("SSE | emitted intent")

            # Stage 2: Architecture (blocking — run in thread)
            arch = await loop.run_in_executor(None, design_architecture, intent)
            yield _sse({"stage": "architecture", "data": arch.model_dump()})
            logger.info("SSE | emitted architecture")

            # Stage 3: Schema generation — parallel async streaming variant
            # generate_schemas_streaming is now an async generator; iterate it directly.
            # It runs DB solo (Round 1), then API+Auth in parallel (Round 2), then UI (Round 3).
            from pipeline.ddl import generate_ddl, validate_ddl
            db = api = auth = ui = None
            async for stage_name, schema_obj in generate_schemas_streaming(arch):
                if stage_name == "db_schema":
                    db = schema_obj
                    yield _sse({"stage": "db_schema", "data": schema_obj.model_dump(by_alias=True)})
                    logger.info("SSE | emitted db_schema")
                    
                    # Intercept and generate DDL
                    ddl_sql = await loop.run_in_executor(None, generate_ddl, db)
                    ddl_val = await loop.run_in_executor(None, validate_ddl, ddl_sql)
                    yield _sse({
                        "stage": "ddl",
                        "data": {
                            "sql": ddl_sql,
                            "valid": ddl_val.success,
                            "table_count": ddl_val.table_count,
                            "error": ddl_val.error
                        }
                    })
                    logger.info("SSE | emitted ddl")
                elif stage_name == "api_schema":
                    api = schema_obj
                    yield _sse({"stage": "api_schema", "data": schema_obj.model_dump()})
                elif stage_name == "auth_schema":
                    auth = schema_obj
                    yield _sse({"stage": "auth_schema", "data": schema_obj.model_dump()})
                elif stage_name == "ui_schema":
                    ui = schema_obj
                    yield _sse({"stage": "ui_schema", "data": schema_obj.model_dump()})
                if stage_name != "db_schema":
                    logger.info("SSE | emitted %s", stage_name)

            # Stage 4: Refine (pure Python, near-instant)
            schemas = SchemasResult(db=db, api=api, auth=auth, ui=ui)
            refinement = await loop.run_in_executor(None, refine, schemas)
            ref_payload = {
                "is_clean": refinement.is_clean,
                "violation_count": len(refinement.violations),
                "violations": [
                    {
                        "layer": v.layer,
                        "field": v.field,
                        "rule_violated": v.rule_violated,
                        "message": v.message,
                    }
                    for v in refinement.violations
                ],
                "summary": refinement.summary,
            }
            yield _sse({"stage": "refinement", "data": ref_payload})
            logger.info("SSE | emitted refinement")

            yield _sse({"stage": "done"})
            logger.info("SSE | stream complete")

        except PipelineStageError as exc:
            logger.error("SSE | pipeline error at %s: %s", exc.stage, exc.detail)
            yield _sse({"stage": "error", "failed_stage": exc.stage, "detail": exc.detail})

        except Exception as exc:
            logger.error("SSE | unexpected error: %s", exc)
            yield _sse({"stage": "error", "failed_stage": "unknown", "detail": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering for SSE
        },
    )
