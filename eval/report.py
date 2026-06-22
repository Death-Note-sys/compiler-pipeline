"""
eval/report.py
--------------
Reads eval/results.json and prints a formatted summary report.

Usage
-----
  python -m eval.report
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "results.json"

# ANSI colours omitted for Windows cp1252 compatibility
_BOLD  = ""
_GREEN = ""
_RED   = ""
_CYAN  = ""
_RESET = ""


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{100 * n / total:.1f}%"


def _bar(value: float, max_value: float, width: int = 20) -> str:
    filled = int(width * value / max_value) if max_value else 0
    return "#" * filled + "-" * (width - filled)


def main() -> None:
    if not RESULTS_PATH.exists():
        print(f"No results found at {RESULTS_PATH}. Run eval/runner.py first.")
        return

    results: list[dict] = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    total = len(results)
    successes = [r for r in results if r["success"]]
    failures  = [r for r in results if not r["success"]]

    print(f"\n{_BOLD}{'='*60}{_RESET}")
    print(f"{_BOLD}  NL-to-App Compiler Pipeline — Evaluation Report{_RESET}")
    print(f"{_BOLD}{'='*60}{_RESET}\n")

    # ── Overall ──────────────────────────────────────────────────
    latencies = [r["latency_seconds"] for r in results]
    mean_lat  = statistics.mean(latencies) if latencies else 0.0
    total_repairs = sum(r.get("repair_count", 0) for r in results)

    print(f"{_BOLD}Overall{_RESET}")
    print(f"  Prompts run    : {total}")
    print(f"  Succeeded      : {_GREEN}{len(successes)}{_RESET} ({_pct(len(successes), total)})")
    print(f"  Failed         : {_RED}{len(failures)}{_RESET} ({_pct(len(failures), total)})")
    print(f"  Mean latency   : {mean_lat:.1f}s")
    print(f"  Total repairs  : {total_repairs}")

    # ── By category ──────────────────────────────────────────────
    print(f"\n{_BOLD}By Category{_RESET}")
    for cat in ("real", "edge"):
        cat_results  = [r for r in results if r["category"] == cat]
        cat_success  = sum(1 for r in cat_results if r["success"])
        cat_total    = len(cat_results)
        cat_lat      = [r["latency_seconds"] for r in cat_results]
        cat_mean_lat = statistics.mean(cat_lat) if cat_lat else 0.0
        label = "Real prompts" if cat == "real" else "Edge prompts"
        print(
            f"  {label:<16}: {cat_success}/{cat_total} "
            f"({_pct(cat_success, cat_total)}) — mean {cat_mean_lat:.1f}s"
        )

    # ── Edge type breakdown ───────────────────────────────────────
    edge_results = [r for r in results if r["category"] == "edge"]
    if edge_results:
        print(f"\n{_BOLD}Edge Prompt Results by Type{_RESET}")
        edge_entries = {r["id"]: r for r in edge_results}
        # pull edge_type from results dict (stored as-is from prompts)
        from eval.prompts import EDGE_PROMPTS
        type_map: dict[str, list] = {}
        for ep in EDGE_PROMPTS:
            et = ep.get("edge_type", "unknown")
            r = edge_entries.get(ep["id"])
            if r:
                type_map.setdefault(et, []).append(r)
        for et, rs in sorted(type_map.items()):
            ok = sum(1 for r in rs if r["success"])
            print(f"  {et:<20}: {ok}/{len(rs)} succeeded")

    # ── Failure breakdown ─────────────────────────────────────────
    if failures:
        print(f"\n{_BOLD}Failure Breakdown{_RESET}")

        stage_counts: dict[str, int] = {}
        etype_counts: dict[str, int] = {}
        for r in failures:
            stage = r.get("failed_stage") or "unknown"
            etype = r.get("error_type") or "Unknown"
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            etype_counts[etype] = etype_counts.get(etype, 0) + 1

        print("  Failed stages:")
        for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
            print(f"    {stage:<30}: {count}")

        print("  Error types:")
        for etype, count in sorted(etype_counts.items(), key=lambda x: -x[1]):
            print(f"    {etype:<30}: {count}")

        print("  Failed prompts:")
        for r in failures:
            print(f"    {r['id']:<20} stage={r.get('failed_stage')} err={r.get('error_type')}")
    else:
        print(f"\n{_GREEN}No failures!{_RESET}")

    # ── Violation summary ─────────────────────────────────────────
    print(f"\n{_BOLD}Violation Summary (successful runs){_RESET}")
    clean    = [r for r in successes if r.get("is_clean")]
    unclean  = [r for r in successes if not r.get("is_clean")]
    all_viol = sum(r.get("violation_count", 0) for r in successes)
    print(f"  Clean outputs  : {len(clean)}/{len(successes)}")
    print(f"  With violations: {len(unclean)}/{len(successes)}")
    print(f"  Total violations: {all_viol}")
    if unclean:
        print("  Prompts with violations:")
        for r in sorted(unclean, key=lambda x: -x.get("violation_count", 0)):
            print(f"    {r['id']:<20}: {r['violation_count']} violation(s)")

    # ── Repair summary ────────────────────────────────────────────
    print(f"\n{_BOLD}Repair Summary{_RESET}")
    repair_counts = [(r["id"], r.get("repair_count", 0)) for r in results]
    repaired = [(pid, c) for pid, c in repair_counts if c > 0]
    print(f"  Prompts needing repair: {len(repaired)}/{total}")
    print(f"  Total repair attempts : {total_repairs}")
    if repaired:
        print("  Repaired prompts:")
        for pid, cnt in sorted(repaired, key=lambda x: -x[1]):
            print(f"    {pid:<20}: {cnt} repair(s)")

    # ── Top 3 slowest ─────────────────────────────────────────────
    print(f"\n{_BOLD}Top 3 Slowest Prompts{_RESET}")
    slowest = sorted(results, key=lambda r: r["latency_seconds"], reverse=True)[:3]
    for rank, r in enumerate(slowest, start=1):
        bar = _bar(r["latency_seconds"], slowest[0]["latency_seconds"])
        print(f"  #{rank} {r['id']:<20} {r['latency_seconds']:.1f}s  {_CYAN}{bar}{_RESET}")

    # ── Stage latency breakdown ───────────────────────────────────
    print(f"\n{_BOLD}Mean Stage Latencies (successful runs){_RESET}")
    stage_names = ["extract_intent", "design_architecture", "generate_schemas", "refine"]
    for stage in stage_names:
        lats = [
            r["stage_latencies"][stage]
            for r in successes
            if isinstance(r.get("stage_latencies"), dict) and stage in r["stage_latencies"]
        ]
        if lats:
            mean = statistics.mean(lats)
            bar = _bar(mean, max(
                statistics.mean([
                    r["stage_latencies"][s]
                    for r in successes
                    if isinstance(r.get("stage_latencies"), dict) and s in r["stage_latencies"]
                ] or [1])
                for s in stage_names
            ), width=15)
            print(f"  {stage:<30}: {mean:.1f}s  {_CYAN}{bar}{_RESET}")

    print(f"\n{_BOLD}{'='*60}{_RESET}\n")


if __name__ == "__main__":
    main()
