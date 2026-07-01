"""
pipeline/stages.py
------------------
Pipeline stage gateway — the single import surface for all four stages.

All four stages now delegate to their own modules:
  1. extract_intent      → pipeline/intent.py        (Groq API)
  2. design_architecture → pipeline/architecture.py  (Groq API)
  3. generate_schemas    → pipeline/schema_gen.py     (Groq API)
  4. refine              → pipeline/refine.py         (pure Python, no LLM)
"""

from __future__ import annotations

from schemas.intent import IntentModel
from schemas.architecture import ArchitectureModel
from pipeline.results import SchemasResult, RefinementResult


# ---------------------------------------------------------------------------
# Stage 1 – Intent Extraction
# ---------------------------------------------------------------------------

def extract_intent(raw_text: str) -> IntentModel:
    """Real implementation in pipeline/intent.py (uses Groq API)."""
    from pipeline.intent import extract_intent as _real
    return _real(raw_text)


# ---------------------------------------------------------------------------
# Stage 2 – System Design
# ---------------------------------------------------------------------------

def design_architecture(intent: IntentModel) -> ArchitectureModel:
    """Real implementation in pipeline/architecture.py (uses Groq API)."""
    from pipeline.architecture import design_architecture as _real
    return _real(intent)


# ---------------------------------------------------------------------------
# Stage 3 – Schema Generation
# ---------------------------------------------------------------------------

def generate_schemas(arch: ArchitectureModel) -> SchemasResult:
    """
    Real implementation in pipeline/schema_gen.py (uses Groq API).

    Returns a SchemasResult with .db, .api, .auth, .ui attributes,
    plus the generated DDL and its validation result.
    """
    from pipeline.schema_gen import generate_schemas as _real
    from pipeline.ddl import generate_ddl, validate_ddl
    
    result = _real(arch)
    result.ddl = generate_ddl(result.db)
    result.ddl_validation = validate_ddl(result.ddl)
    return result

async def generate_schemas_parallel(arch: ArchitectureModel) -> SchemasResult:
    """
    Real implementation in pipeline/schema_gen.py (uses Groq API).

    Returns a SchemasResult with .db, .api, .auth, .ui attributes,
    plus the generated DDL and its validation result.
    """
    from pipeline.schema_gen import generate_schemas_parallel as _real
    from pipeline.ddl import generate_ddl, validate_ddl
    
    result = await _real(arch)
    result.ddl = generate_ddl(result.db)
    result.ddl_validation = validate_ddl(result.ddl)
    return result


# ---------------------------------------------------------------------------
# Stage 4 – Refine
# ---------------------------------------------------------------------------

def refine(schemas: SchemasResult) -> RefinementResult:
    """
    Real implementation in pipeline/refine.py (pure Python, no LLM calls).

    Runs all 5 consistency rules from refine/consistency.py and returns a
    RefinementResult with .violations, .is_clean, and .summary.
    """
    from pipeline.refine import refine as _real
    return _real(schemas)
