"""
pipeline/errors.py
------------------
Central error types for all pipeline stages.

All stage errors derive from PipelineStageError so callers can catch at
the right granularity: specific subclass for targeted handling, or the
base class for catch-all error pages / CLI output.
"""

from __future__ import annotations

from typing import Optional


class PipelineStageError(Exception):
    """
    Raised when a pipeline stage fails in a non-retriable way.

    Attributes
    ----------
    stage : str
        Name of the stage that failed (e.g. 'extract_intent').
    detail : str
        Human-readable description of the failure.
    cause : Exception | None
        The underlying exception (e.g. a Pydantic ValidationError),
        preserved for programmatic inspection.
    """

    def __init__(self, stage: str, detail: str, cause: Optional[Exception] = None) -> None:
        self.stage = stage
        self.detail = detail
        self.cause = cause
        super().__init__(f"[{stage}] {detail}")
