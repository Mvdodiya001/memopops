"""Reproducible solver-only scaling benchmark for bounded implication chains."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
import platform
from pathlib import Path
import subprocess
import sys
from time import perf_counter_ns
from typing import Any

import z3

from memopops.formula import parse_formula
from memopops.solver import QueryStatus, classify


WORKLOAD_SIZES = (10, 50, 100, 256)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _workload(assertion_count: int):
    atom_ids = {f"p{index:03d}" for index in range(assertion_count)}

    def atom(atom_id: str) -> dict[str, str]:
        return {"op": "atom", "id": atom_id}

    premises = [parse_formula(atom("p000"), atom_ids)]
    premises.extend(
        parse_formula(
            {"op": "implies", "args": [atom(f"p{index:03d}"), atom(f"p{index + 1:03d}")]},
            atom_ids,
        )
        for index in range(assertion_count - 1)
    )
    query = parse_formula(atom(f"p{assertion_count - 1:03d}"), atom_ids)
    return tuple(premises), query


def _metadata() -> dict[str, Any]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    return {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_revision": revision,
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "logical_cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "z3": z3.get_version_string(),
        "scope": "Z3 classification only; excludes FalkorDB, HTTP/API, certificate generation, and independent checking.",
        "workload": "one asserted first atom followed by a chain of Boolean implications; query the final atom",
    }


def run(*, samples: int, runs: int, warmup: int) -> dict[str, Any]:
    results = []
    for assertion_count in WORKLOAD_SIZES:
        premises, query = _workload(assertion_count)
        run_results = []
        for run_index in range(1, runs + 1):
            for _ in range(warmup):
                evaluation = classify(premises, query)
                if evaluation.result != QueryStatus.PROVED:
                    raise RuntimeError(f"warm-up expected PROVED, received {evaluation.result}")

            elapsed_ms = []
            statuses: dict[str, int] = {}
            for _ in range(samples):
                started = perf_counter_ns()
                evaluation = classify(premises, query)
                duration = (perf_counter_ns() - started) / 1_000_000
                elapsed_ms.append(duration)
                status = evaluation.result.value
                statuses[status] = statuses.get(status, 0) + 1
                if evaluation.result != QueryStatus.PROVED:
                    raise RuntimeError(f"measurement expected PROVED, received {evaluation.result}")

            run_results.append({
                "run": run_index,
                "sample_count": samples,
                "statuses": statuses,
                "timeout_count": statuses.get(QueryStatus.SOLVER_UNKNOWN.value, 0),
                "latency_ms": {
                    "p50": round(_percentile(elapsed_ms, 0.50), 3),
                    "p95": round(_percentile(elapsed_ms, 0.95), 3),
                    "min": round(min(elapsed_ms), 3),
                    "max": round(max(elapsed_ms), 3),
                },
                "samples_ms": [round(value, 3) for value in elapsed_ms],
            })
        results.append({"assertion_count": assertion_count, "runs": run_results})

    return {
        "metadata": _metadata(),
        "protocol": {"warmup_per_run": warmup, "samples_per_run": samples, "independent_runs": runs},
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 1 or args.runs < 1 or args.warmup < 0:
        parser.error("samples and runs must be positive; warmup cannot be negative")

    payload = json.dumps(run(samples=args.samples, runs=args.runs, warmup=args.warmup), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
