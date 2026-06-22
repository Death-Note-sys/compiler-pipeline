"""
pipeline/refine.py
------------------
Stage 4 of the compiler pipeline: consistency refinement.

Calls all 5 cross-layer consistency rules from refine/consistency.py and
returns a structured RefinementResult — no LLM calls, no mutations.

Usage
-----
    from pipeline.refine import refine
    from pipeline.results import SchemasResult

    result = refine(schemas)   # schemas is a SchemasResult
    if not result.is_clean:
        for v in result.violations:
            print(v.layer, v.field, v.rule_violated, v.message)
"""

from __future__ import annotations

import logging

from pipeline.results import SchemasResult, RefinementResult
from refine.consistency import run_all_checks

logger = logging.getLogger(__name__)


def refine(schemas: SchemasResult) -> RefinementResult:
    """
    Run all 5 consistency rules against *schemas* and return a RefinementResult.

    No LLM calls are made. No schemas are mutated. This is a pure
    read-only audit pass — the repair engine (future work) would consume
    the returned violations list.

    Parameters
    ----------
    schemas : SchemasResult
        The four validated schemas produced by generate_schemas.

    Returns
    -------
    RefinementResult
        violations  — list of ValidationError objects (empty if clean)
        is_clean    — True when violations is empty
        summary     — human-readable one-liner
    """
    violations = run_all_checks(
        ui=schemas.ui,
        api=schemas.api,
        db=schemas.db,
        auth=schemas.auth,
    )

    result = RefinementResult.from_violations(violations)

    if result.is_clean:
        logger.info("Refinement clean — all 5 consistency rules passed.")
    else:
        for v in result.violations:
            logger.warning(
                "violation | %s | field=%s | rule=%s | %s",
                v.layer, v.field, v.rule_violated, v.message,
            )

    return result
