"""Deterministic acceptance scenarios over the published API routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agents.client import MemoryClient
from agents.demo_memory import REVISION_ID, WORKSPACE_ID
from agents.operator import replace_passing_tests, submit_revision
from agents.scripts import RELEASE_QUERY, ScriptedReleaseReader
from agents.session import AgentSession
from agents.transport import AsgiTransport
from evaluation.baselines import NaiveNotes, SolverOnlyAblation
from evaluation.lab_store import LabSnapshotStore
from memopops.api import create_app
from memopops.formula import parse_formula


def _lab_client(store: LabSnapshotStore, role: str) -> MemoryClient:
    token = f"{role}-token"
    app = create_app(store)
    return MemoryClient(AsgiTransport(app), token, WORKSPACE_ID)


def run_acceptance(output_dir: Path) -> dict[str, Any]:
    """Exercise reader decisions and a correction path without FalkorDB."""
    os.environ["MEMOPOPS_AUTH_TOKENS"] = json.dumps(
        {
            "reader-token": {"workspace_id": WORKSPACE_ID, "role": "reader"},
            "writer-token": {"workspace_id": WORKSPACE_ID, "role": "writer"},
            "operator-token": {"workspace_id": WORKSPACE_ID, "role": "operator"},
        }
    )
    store = LabSnapshotStore()
    reader = _lab_client(store, "reader")
    operator = _lab_client(store, "operator")
    output_dir.mkdir(parents=True, exist_ok=True)

    reader_journal = output_dir / "reader-r1.json"
    session = AgentSession(
        client=reader,
        model=ScriptedReleaseReader(),
        role="reader",
        workspace_id=WORKSPACE_ID,
        mode="scripted_replay",
        journal_path=reader_journal,
    )
    first = session.run()
    decision_r1 = session.current_decision()
    assert decision_r1 is not None
    assert decision_r1["choice"] == "ship"
    assert decision_r1.get("persisted") is True

    status, committed = submit_revision(
        operator,
        expected_revision=REVISION_ID,
        idempotency_key="acceptance-correction",
        reason="Replace the passing test report with an explicit failure.",
        mutations=replace_passing_tests(),
    )
    assert status == 201 and committed.get("status") == "COMMITTED"
    rev2 = committed["revision_id"]

    resumed = AgentSession.resume(
        reader_journal,
        client=reader,
        model=ScriptedReleaseReader(prior_decision=decision_r1),
        role="reader",
        mode="scripted_replay",
    )
    second = resumed.run()
    decision_r2 = resumed.current_decision()
    assert decision_r2 is not None
    assert decision_r2["revision_id"] == rev2
    assert decision_r2["choice"] == "hold"

    snapshot = store.load_snapshot(WORKSPACE_ID, rev2)
    naive = NaiveNotes()
    naive.cache_answer("release_ready", "PROVED")
    stale = naive.query("release_ready")
    ablation = SolverOnlyAblation(
        [item.formula for item in snapshot.assertions],
        set(snapshot.atom_ids),
    )
    ablation_result = ablation.query(RELEASE_QUERY)
    parse_formula(RELEASE_QUERY, snapshot.atom_ids)

    report = {
        "mode": "scripted_replay",
        "workspace_id": WORKSPACE_ID,
        "cases": [
            {
                "id": "A01",
                "description": "Reader records PROCEED at r1 then BLOCK at r2 after correction",
                "passed": decision_r1["choice"] == "ship" and decision_r2["choice"] == "hold",
            },
            {
                "id": "baseline_naive_stale",
                "description": "Naive cache labels stale answer as current",
                "passed": stale["labeled_current"] and stale["result"] == "PROVED",
            },
            {
                "id": "baseline_solver_only",
                "description": "Solver-only ablation returns REFUTED at r2 without revision guard",
                "passed": ablation_result["result"] == "REFUTED",
            },
        ],
    }
    (output_dir / "sessions.json").write_text(
        json.dumps({"r1": first, "r2": second}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
