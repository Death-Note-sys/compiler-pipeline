"""
pipeline/run_intent.py
-----------------------
Manual test entry point for the extract_intent stage.

Usage
-----
  # From the project root:
  python -m pipeline.run_intent "Build a CRM where admins manage contacts"

  # Or pipe from stdin:
  echo "Build a todo app with tags and due dates" | python -m pipeline.run_intent
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

from pipeline.intent import extract_intent  # noqa: E402 (after basicConfig)


def main() -> None:
    if len(sys.argv) > 1:
        raw_text = " ".join(sys.argv[1:])
    else:
        print("Reading raw text from stdin (Ctrl+D / Ctrl+Z to finish)…", file=sys.stderr)
        raw_text = sys.stdin.read().strip()

    if not raw_text:
        print("Error: no input provided.", file=sys.stderr)
        sys.exit(1)

    intent = extract_intent(raw_text)
    print(json.dumps(intent.model_dump(), indent=2))


if __name__ == "__main__":
    main()
