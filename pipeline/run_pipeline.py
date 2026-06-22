"""
pipeline/run_pipeline.py
------------------------
Manual entry point for the full 4-stage pipeline chain:
  extract_intent → design_architecture → generate_schemas → refine

Usage
-----
  python -m pipeline.run_pipeline "Build a simple todo app with auth"

Output sections (in order):
  === Intent ===
  === Architecture ===
  === DB Schema ===
  === API Schema ===
  === Auth Schema ===
  === UI Schema ===
  === Refinement ===
"""

from __future__ import annotations

import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from pipeline.intent import extract_intent              # noqa: E402
from pipeline.architecture import design_architecture   # noqa: E402
from pipeline.schema_gen import generate_schemas        # noqa: E402
from pipeline.refine import refine                      # noqa: E402


def main() -> None:
    if len(sys.argv) > 1:
        raw_text = " ".join(sys.argv[1:])
    else:
        print("Reading raw text from stdin (Ctrl+D / Ctrl+Z to finish)…", file=sys.stderr)
        raw_text = sys.stdin.read().strip()

    if not raw_text:
        print("Error: no input provided.", file=sys.stderr)
        sys.exit(1)

    # Stage 1
    intent = extract_intent(raw_text)
    print("\n=== Intent ===")
    print(json.dumps(intent.model_dump(), indent=2))

    # Stage 2
    arch = design_architecture(intent)
    print("\n=== Architecture ===")
    print(json.dumps(arch.model_dump(), indent=2))

    # Stage 3
    schemas = generate_schemas(arch)

    print("\n=== DB Schema ===")
    print(json.dumps(schemas.db.model_dump(by_alias=True), indent=2))

    print("\n=== API Schema ===")
    print(json.dumps(schemas.api.model_dump(), indent=2))

    print("\n=== Auth Schema ===")
    print(json.dumps(schemas.auth.model_dump(), indent=2))

    print("\n=== UI Schema ===")
    print(json.dumps(schemas.ui.model_dump(), indent=2))

    # Stage 4
    refinement = refine(schemas)

    print("\n=== Refinement ===")
    refinement_output = {
        "is_clean": refinement.is_clean,
        "summary": refinement.summary,
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
    }
    print(json.dumps(refinement_output, indent=2))

    if not refinement.is_clean:
        print(
            f"\n⚠  {len(refinement.violations)} violation(s) detected — "
            "see above for details.",
            file=sys.stderr,
        )
    else:
        print("\n✓  All consistency checks passed.", file=sys.stderr)


if __name__ == "__main__":
    main()
