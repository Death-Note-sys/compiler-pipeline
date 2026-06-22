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

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
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
</style>
</head>
<body>

<div class="container">
  <h1>NL-to-App Compiler</h1>
  <div>
    <textarea id="prompt">Build a CRM where admins manage contacts and sales reps view their assigned contacts. Include role-based access and activity logging.</textarea>
  </div>
  <div>
    <button id="generateBtn">Generate</button>
    <div id="loading" class="loading">Running pipeline... (~30s)</div>
  </div>

  <div id="errorBox" class="error-box"></div>
  <div id="results" style="display: none;">
    <details id="det-intent"><summary>Intent</summary><pre id="out-intent"></pre></details>
    <details id="det-arch"><summary>Architecture</summary><pre id="out-arch"></pre></details>
    <details id="det-db"><summary>DB Schema</summary><pre id="out-db"></pre></details>
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
document.getElementById('generateBtn').addEventListener('click', async () => {
  const btn = document.getElementById('generateBtn');
  const loading = document.getElementById('loading');
  const errorBox = document.getElementById('errorBox');
  const results = document.getElementById('results');
  const prompt = document.getElementById('prompt').value;

  btn.disabled = true;
  loading.style.display = 'block';
  errorBox.style.display = 'none';
  results.style.display = 'none';

  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      errorBox.style.display = 'block';
      errorBox.textContent = `Error ${res.status}: ${data.error || 'Unknown Error'} - ${data.detail || JSON.stringify(data)}`;
    } else {
      results.style.display = 'block';
      document.getElementById('out-intent').textContent = JSON.stringify(data.intent, null, 2);
      document.getElementById('out-arch').textContent = JSON.stringify(data.architecture, null, 2);
      document.getElementById('out-db').textContent = JSON.stringify(data.schemas.db, null, 2);
      document.getElementById('out-api').textContent = JSON.stringify(data.schemas.api, null, 2);
      document.getElementById('out-auth').textContent = JSON.stringify(data.schemas.auth, null, 2);
      document.getElementById('out-ui').textContent = JSON.stringify(data.schemas.ui, null, 2);
      
      const ref = data.refinement;
      const refBadge = document.getElementById('refine-badge');
      if (ref.is_clean) {
        refBadge.textContent = '✓ Clean';
        refBadge.className = 'badge success';
      } else {
        refBadge.textContent = ref.violation_count + ' Violations';
        refBadge.className = 'badge error';
      }
      document.getElementById('out-refine').textContent = JSON.stringify(ref, null, 2);
    }
  } catch (err) {
    errorBox.style.display = 'block';
    errorBox.textContent = 'Network or server error: ' + err.message;
  } finally {
    btn.disabled = false;
    loading.style.display = 'none';
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
    from pipeline.intent import extract_intent
    from pipeline.architecture import design_architecture
    from pipeline.schema_gen import generate_schemas
    from pipeline.refine import refine

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
