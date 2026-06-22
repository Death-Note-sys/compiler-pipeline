"""
eval/runner.py
--------------
Runs the full 4-stage pipeline against all 20 eval prompts and records
structured metrics.

Output files
------------
  eval/results.json   — full per-prompt metrics (all fields)
  eval/summary.csv    — one row per prompt (all metric fields as columns)

Usage
-----
  python -m eval.runner

Repair count
------------
Captured via a custom logging.Handler that counts log records whose
message contains "repair_needed=True".  This is accurate and requires
zero changes to pipeline code.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path
from typing import Any

from eval.prompts import ALL_PROMPTS
from pipeline.errors import PipelineStageError
from pipeline.stages import (
    design_architecture,
    extract_intent,
    generate_schemas,
    refine,
)

# Groq RateLimitError — import gracefully so runner works if groq not installed
try:
    from groq import RateLimitError as _GroqRateLimitError
except ImportError:  # pragma: no cover
    _GroqRateLimitError = None  # type: ignore[assignment,misc]


def _parse_retry_after(exc: Exception) -> float:
    """
    Parse "Please try again in Xm Y.Zs" from a Groq RateLimitError message.
    Returns the number of seconds to sleep (minimum 5, maximum 1200).
    """
    import re
    msg = str(exc)
    # Format: "try again in 10m34.272s" or "try again in 45.3s"
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", msg)
    if m:
        minutes = int(m.group(1) or 0)
        seconds = float(m.group(2) or 0)
        total = minutes * 60 + seconds + 5  # +5s buffer
        return min(total, 1200.0)  # cap at 20 minutes
    return 30.0  # fallback: 30 seconds

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EVAL_DIR = Path(__file__).parent
RESULTS_PATH = EVAL_DIR / "results.json"
SUMMARY_PATH = EVAL_DIR / "summary.csv"

# ---------------------------------------------------------------------------
# Repair counter — injected log handler
# ---------------------------------------------------------------------------

class _RepairCounter(logging.Handler):
    """Counts log records that signal a repair attempt."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "repair_needed=True" in self.getMessage():
            self.count += 1

    def getMessage(self) -> str:  # noqa: N802 — override matches stdlib spelling
        return ""  # unused; we call record.getMessage() in emit below

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            msg = record.getMessage()
        except Exception:
            msg = record.msg or ""
        if "repair_needed=True" in msg:
            self.count += 1

    def reset(self) -> None:
        self.count = 0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_SLEEP_BETWEEN = 3  # seconds between prompts to avoid RPM limits

CSV_FIELDS = [
    "id",
    "category",
    "edge_type",
    "success",
    "failed_stage",
    "error_type",
    "violation_count",
    "is_clean",
    "latency_seconds",
    "latency_extract_intent",
    "latency_design_architecture",
    "latency_generate_schemas",
    "latency_refine",
    "repair_count",
]


def _run_one(prompt_entry: dict, repair_counter: _RepairCounter) -> dict[str, Any]:
    """Run the full pipeline for one prompt and return the metrics dict."""
    repair_counter.reset()

    result: dict[str, Any] = {
        "id": prompt_entry["id"],
        "category": prompt_entry["category"],
        "edge_type": prompt_entry.get("edge_type"),
        "success": False,
        "failed_stage": None,
        "error_type": None,
        "violation_count": 0,
        "is_clean": None,
        "latency_seconds": 0.0,
        "stage_latencies": {
            "extract_intent": 0.0,
            "design_architecture": 0.0,
            "generate_schemas": 0.0,
            "refine": 0.0,
        },
        "repair_count": 0,
    }

    raw_text = prompt_entry["prompt"]
    total_start = time.perf_counter()
    current_stage = "extract_intent"  # updated as we progress

    try:
        # Stage 1
        current_stage = "extract_intent"
        t0 = time.perf_counter()
        intent = extract_intent(raw_text)
        result["stage_latencies"]["extract_intent"] = round(time.perf_counter() - t0, 2)

        # Stage 2
        current_stage = "design_architecture"
        t0 = time.perf_counter()
        arch = design_architecture(intent)
        result["stage_latencies"]["design_architecture"] = round(time.perf_counter() - t0, 2)

        # Stage 3
        current_stage = "generate_schemas"
        t0 = time.perf_counter()
        schemas = generate_schemas(arch)
        result["stage_latencies"]["generate_schemas"] = round(time.perf_counter() - t0, 2)

        # Stage 4
        current_stage = "refine"
        t0 = time.perf_counter()
        refinement = refine(schemas)
        result["stage_latencies"]["refine"] = round(time.perf_counter() - t0, 2)

        result["success"] = True
        result["violation_count"] = len(refinement.violations)
        result["is_clean"] = refinement.is_clean

    except PipelineStageError as exc:
        result["failed_stage"] = exc.stage
        result["error_type"] = "PipelineStageError"
        result["_raw_exc"] = exc

    except Exception as exc:  # noqa: BLE001
        result["failed_stage"] = current_stage
        if _GroqRateLimitError is not None and isinstance(exc, _GroqRateLimitError):
            result["error_type"] = "RateLimitError"
        else:
            result["error_type"] = type(exc).__name__
        result["_raw_exc"] = exc

    finally:
        result["latency_seconds"] = round(time.perf_counter() - total_start, 2)
        result["repair_count"] = repair_counter.count

    return result


def _progress_line(index: int, total: int, entry: dict, result: dict) -> str:
    pid = entry["id"]
    latency = result["latency_seconds"]
    if result["success"]:
        clean_label = "clean" if result["is_clean"] else f"{result['violation_count']} violations"
        return f"[{index}/{total}] {pid} OK {latency}s {clean_label}"
    else:
        stage = result.get("failed_stage", "unknown")
        etype = result.get("error_type", "Exception")
        return f"[{index}/{total}] {pid} FAIL {stage} {latency}s {etype}"


def run_eval() -> list[dict]:
    """Run all prompts and return the full results list."""

    # Attach the repair counter to the root logger so it sees all pipeline logs
    repair_counter = _RepairCounter()
    repair_counter.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.addHandler(repair_counter)

    results: list[dict] = []
    total = len(ALL_PROMPTS)

    for i, entry in enumerate(ALL_PROMPTS, start=1):
        result = _run_one(entry, repair_counter)

        # If we hit a rate limit, parse the retry-after time and retry once
        if (
            not result["success"]
            and result.get("error_type") == "RateLimitError"
        ):
            raw_exc = result.pop("_raw_exc", None)
            wait_secs = _parse_retry_after(raw_exc) if raw_exc is not None else 65.0
            print(
                f"  [rate-limit] sleeping {wait_secs:.0f}s before retry of {entry['id']}...",
                flush=True,
            )
            time.sleep(wait_secs)
            result = _run_one(entry, repair_counter)

        # Strip internal key before storing
        result.pop("_raw_exc", None)

        results.append(result)
        print(_progress_line(i, total, entry, result), flush=True)

        if i < total:
            time.sleep(_SLEEP_BETWEEN)

    # Detach the counter
    root_logger.removeHandler(repair_counter)
    return results


def _write_outputs(results: list[dict]) -> None:
    """Write results.json and summary.csv."""
    EVAL_DIR.mkdir(exist_ok=True)

    # results.json — full detail
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {RESULTS_PATH}")

    # summary.csv — flat row per prompt
    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = dict(r)
            # Flatten stage_latencies into top-level keys
            for stage, lat in r.get("stage_latencies", {}).items():
                row[f"latency_{stage}"] = lat
            writer.writerow(row)
    print(f"Wrote {SUMMARY_PATH}")


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,  # suppress INFO noise during eval run
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"Starting eval run — {len(ALL_PROMPTS)} prompts\n")
    t_start = time.perf_counter()

    results = run_eval()
    _write_outputs(results)

    elapsed = round(time.perf_counter() - t_start, 1)
    successes = sum(1 for r in results if r["success"])
    print(f"\nDone in {elapsed}s — {successes}/{len(results)} succeeded")


if __name__ == "__main__":
    main()
