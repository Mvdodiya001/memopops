"""Run the scripted two-client release demo against a local or remote API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agents.client import MemoryClient
from agents.demo_memory import WORKSPACE_ID
from agents.operator import replace_passing_tests, submit_revision
from agents.scripts import ScriptedReleaseReader
from agents.session import AgentSession
from agents.transport import AsgiTransport, UrlTransport
from evaluation.acceptance import run_acceptance
from evaluation.lab_store import LabSnapshotStore
from memopops.api import create_app


def _tokens_from_env() -> dict[str, dict[str, str]]:
    raw = os.getenv("MEMOPOPS_AUTH_TOKENS", "{}")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise SystemExit("MEMOPOPS_AUTH_TOKENS must be a JSON object")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Scripted memopops agent replay.")
    parser.add_argument(
        "--mode",
        choices=["lab", "acceptance", "remote"],
        default="lab",
        help="lab uses in-memory API; acceptance runs the evaluation suite; remote needs API URL and tokens.",
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path(".artifacts/agent-demo"))
    parser.add_argument("--reader-token-name", default="reader-token")
    args = parser.parse_args()

    if args.mode == "acceptance":
        report = run_acceptance(args.output)
        print(json.dumps({"passed": sum(1 for c in report["cases"] if c["passed"]), "total": len(report["cases"])}, sort_keys=True))
        return

    tokens = _tokens_from_env()
    reader_entry = tokens.get(args.reader_token_name)
    if not isinstance(reader_entry, dict):
        raise SystemExit(f"missing token {args.reader_token_name} in MEMOPOPS_AUTH_TOKENS")

    if args.mode == "lab":
        os.environ.setdefault(
            "MEMOPOPS_AUTH_TOKENS",
            json.dumps(
                {
                    "reader-token": {"workspace_id": WORKSPACE_ID, "role": "reader"},
                    "operator-token": {"workspace_id": WORKSPACE_ID, "role": "operator"},
                }
            ),
        )
        store = LabSnapshotStore()
        app = create_app(store)
        reader = MemoryClient(AsgiTransport(app), "reader-token", WORKSPACE_ID)
        operator = MemoryClient(AsgiTransport(app), "operator-token", WORKSPACE_ID)
    else:
        reader = MemoryClient(UrlTransport(args.api_base), args.reader_token_name, reader_entry["workspace_id"])
        operator = MemoryClient(
            UrlTransport(args.api_base),
            "operator-token",
            reader_entry["workspace_id"],
        )

    args.output.mkdir(parents=True, exist_ok=True)
    journal = args.output / "reader.json"
    session = AgentSession(
        client=reader,
        model=ScriptedReleaseReader(),
        role="reader",
        workspace_id=WORKSPACE_ID if args.mode == "lab" else reader_entry["workspace_id"],
        mode="scripted_replay",
        journal_path=journal,
    )
    first = session.run()
    decision = session.current_decision()
    if args.mode == "lab" and decision:
        submit_revision(
            operator,
            expected_revision=decision["revision_id"],
            idempotency_key="demo-correction",
            reason="Operator replaces the passing test report after the reader decision.",
            mutations=replace_passing_tests(),
        )
        resumed = AgentSession.resume(
            journal,
            client=reader,
            model=ScriptedReleaseReader(prior_decision=decision),
            role="reader",
            mode="scripted_replay",
        )
        second = resumed.run()
        payload = {"first": first, "second": second}
    else:
        payload = {"first": first}
    (args.output / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"journal": str(journal), "stopped": first.get("stopped_reason")}, sort_keys=True))


if __name__ == "__main__":
    main()
