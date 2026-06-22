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
from fastapi.responses import JSONResponse
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
