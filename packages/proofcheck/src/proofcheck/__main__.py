"""Command line: python -m proofcheck CERTIFICATE [--expected-context MANIFEST]."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from proofcheck.check import CheckError, CheckReport, check_certificate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="proofcheck",
        description=(
            "Check a resolution certificate. Without --expected-context the result is "
            "provenance unverified and covers only the mathematics of the supplied snapshot."
        ),
    )
    parser.add_argument("certificate", help="Exported certificate JSON file")
    parser.add_argument(
        "--expected-context",
        help="Trusted context manifest obtained independently of the certificate",
    )
    args = parser.parse_args(argv)
    try:
        bundle = json.loads(Path(args.certificate).read_text(encoding="utf-8"))
        context = None
        if args.expected_context:
            context = json.loads(Path(args.expected_context).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        report = CheckReport(
            logical_valid=False,
            context_binding="UNVERIFIED",
            errors=(CheckError("malformed", "Certificate file could not be read as JSON."),),
            support_assertion_ids=(),
            message=(
                "Certificate is not valid. Provenance unverified. "
                "This report covers only the mathematics of the supplied snapshot."
            ),
        )
        _write(report)
        print(f"proofcheck: {exc}", file=sys.stderr)
        return 2
    report = check_certificate(bundle, context)
    _write(report)
    if report.logical_valid and report.context_binding in {"MATCHED", "UNVERIFIED"}:
        return 0
    return 1


def _write(report: CheckReport) -> None:
    json.dump(report.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
