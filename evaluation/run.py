"""CLI entry for evaluation suites."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.acceptance import run_acceptance


def main() -> None:
    parser = argparse.ArgumentParser(description="Run memopops evaluation suites.")
    parser.add_argument("--suite", choices=["acceptance"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.suite == "acceptance":
        report = run_acceptance(args.output)
    else:
        raise SystemExit(f"unsupported suite: {args.suite}")

    passed = sum(1 for item in report["cases"] if item.get("passed"))
    total = len(report["cases"])
    print(json.dumps({"suite": args.suite, "passed": passed, "total": total}, sort_keys=True))


if __name__ == "__main__":
    main()
